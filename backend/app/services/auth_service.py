import asyncio
import math
import hashlib
import hmac
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import case, desc, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.otp import OtpCode
from backend.app.schemas.otp import OtpTokenResponse
from backend.app.services.email_service import email_service
from backend.app.core.config import settings
from backend.app.core.exceptions import AuthenticationError, MirrageException
from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.schemas.user import UserOut
from backend.app.services.vpn_service import vpn_service
from backend.app.services.otp_abuse import otp_abuse_limiter
from backend.app.services.email_service import EmailDeliveryError, EmailDispatchResult
from backend.app.services.email_health import email_health


def _utc(value):
    """SQLite returns naive values; PostgreSQL returns aware TIMESTAMPTZ values."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _code_hash(otp):
    return hmac.new(settings.OTP_HMAC_SECRET.encode(), otp.encode(), hashlib.sha256).hexdigest()


class AuthService:
    def __init__(self):
        self._otp_request_lock = asyncio.Lock()

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch user by ID."""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def request_otp(self, db: AsyncSession, email: str, *, is_resend: bool = False, client_address=None) -> int:
        email = email.lower().strip()
        if client_address is not None:
            await otp_abuse_limiter.consume_ip(db, client_address)
        async with self._otp_transaction(db, email):
            otp, resend_after = await self._issue_otp(db, email, is_resend=is_resend)
        # Slow email delivery must not hold the database lock or block verification.
        await self._dispatch_otp(db, email, otp)
        return resend_after

    async def _dispatch_otp(self, db, email, otp):
        error, status, outcome = None, None, "unknown"
        try:
            attempt_id = await email_health.begin(db, email_service.provider)
        except Exception:
            await db.rollback()
            raise MirrageException(503, "OTP email is temporarily unavailable", "OTP_EMAIL_UNAVAILABLE") from None
        try:
            result = await email_service.send_otp(email, otp)
            simulation = settings.ENVIRONMENT == "testing" or (settings.ENVIRONMENT == "development" and settings.OTP_DEV_MODE)
            if isinstance(result, EmailDispatchResult) and (result.outcome == "accepted"
                    or (result.outcome == "simulated" and simulation)):
                outcome, status = result.outcome, result.http_status
            elif settings.ENVIRONMENT == "testing":
                outcome = "simulated"  # Existing mock providers deliberately perform no I/O.
            else:
                error = "PROVIDER_RESPONSE_INVALID"
        except EmailDeliveryError as failure:
            error, outcome, status = failure.code, failure.outcome, failure.http_status
        except Exception:
            error = "PROVIDER_INTERNAL_ERROR"  # Never log exception text or provider data.
        # Cancellation intentionally leaves durable pending intent. Health derives
        # an unknown outcome after the timeout/grace, rather than claiming failure.
        try:
            await email_health.finish(db, attempt_id, outcome, error, status)
        except Exception:
            await db.rollback()
            raise MirrageException(503, "OTP email is temporarily unavailable", "OTP_EMAIL_UNAVAILABLE") from None
        if error:
            raise MirrageException(503, "OTP email is temporarily unavailable", "OTP_EMAIL_UNAVAILABLE") from None

    @asynccontextmanager
    async def _otp_transaction(self, db, email):
        """One serialization key for issue/resend/verify, including unknown emails."""
        async with self._otp_request_lock:
            try:
                if db.bind and db.bind.dialect.name == "postgresql":
                    lock_id = int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big", signed=True)
                    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
                elif db.bind and db.bind.dialect.name == "sqlite":
                    # Acquire SQLite's writer lock before reading, including when
                    # no OTP row exists yet. Independent local test workers must
                    # not both issue a first code or read a stale attempt count.
                    await db.execute(update(OtpCode).where(OtpCode.email == email).values(
                        attempts=OtpCode.attempts,
                    ).execution_options(synchronize_session=False))
                yield
            except BaseException:
                # Expected rejection paths commit attempt/consumption first.
                # Release the transaction lock on every other error/cancellation.
                await db.rollback()
                raise

    async def _issue_otp(self, db: AsyncSession, email: str, *, is_resend: bool) -> tuple[str, int]:
        """Commit issuance under the shared lock; delivery happens afterward."""
        email = email.lower().strip()
        now = datetime.now(timezone.utc)
        
        # Check rate limiting
        window_start = now - timedelta(minutes=settings.OTP_RATE_LIMIT_WINDOW_MINUTES)
        query = select(OtpCode).where(
            OtpCode.email == email,
            OtpCode.created_at >= window_start
        )
        result = await db.execute(query.execution_options(populate_existing=True))
        recent_requests = result.scalars().all()
        
        if len(recent_requests) >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
            raise MirrageException(
                status_code=429,
                detail="Too many OTP requests. Please try again later.",
                code="OTP_RATE_LIMIT",
                headers={"Retry-After": str(max(1, math.ceil((min(_utc(row.created_at) for row in recent_requests) + timedelta(minutes=settings.OTP_RATE_LIMIT_WINDOW_MINUTES) - now).total_seconds())))},
            )
            
        # One immediate resend per rate-limit window; all subsequent sends wait.
        if recent_requests:
            latest = max(recent_requests, key=lambda row: _utc(row.created_at))
            remaining = math.ceil(settings.OTP_RESEND_COOLDOWN_SECONDS - (now - _utc(latest.created_at)).total_seconds())
            immediate_resend = is_resend and len(recent_requests) == 1 and not latest.is_used and _utc(latest.expires_at) > now
            if remaining > 0 and not immediate_resend:
                raise MirrageException(
                    status_code=429,
                    detail=f"Please wait {remaining} seconds before requesting a new code.",
                    code="OTP_COOLDOWN", headers={"Retry-After": str(remaining)},
                )

        # Invalidate any existing unused OTPs
        query = select(OtpCode).where(
            OtpCode.email == email,
            OtpCode.is_used == False,
        )
        result = await db.execute(query.execution_options(populate_existing=True))
        superseded = result.scalars().all()
        for old_otp in superseded:
            old_otp.is_used = True
            
        # Generate cryptographically secure 6-digit OTP
        # A resend must not accidentally reuse a recently superseded numeric code.
        recent_hashes = {record.code_hash for record in [*recent_requests, *superseded]}
        for _ in range(10):
            otp = f"{secrets.randbelow(1000000):06d}"
            code_hash = _code_hash(otp)
            if code_hash not in recent_hashes:
                break
        else:
            raise MirrageException(503, "Cannot issue a verification code", "OTP_GENERATION_FAILED")
        
        # Find if user exists to populate user_id
        user_query = select(User).where(User.email == email)
        user_result = await db.execute(user_query)
        existing_user = user_result.scalars().first()
        
        # Create OtpCode record
        new_otp = OtpCode(
            email=email,
            user_id=existing_user.id if existing_user else None,
            code_hash=code_hash,
            expires_at=now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
            # Strict ordering also handles two issues sharing a timestamp.
            created_at=max([now, *(_utc(record.created_at) + timedelta(microseconds=1)
                                  for record in recent_requests)]),
        )
        db.add(new_otp)
        await otp_abuse_limiter.reserve_delivery(db)
        await db.commit()
        
        return otp, settings.OTP_RESEND_COOLDOWN_SECONDS if recent_requests or is_resend else 0

    async def verify_otp(self, db: AsyncSession, email: str, otp: str) -> OtpTokenResponse:
        """Verify OTP and authenticate/create user."""
        email = email.lower().strip()
        async with self._otp_transaction(db, email):
            user, is_new_user = await self._consume_otp(db, email, otp)
        # External provisioning happens only after consumption/account commit;
        # it can never roll back the OTP or make it reusable.
        if is_new_user:
            await vpn_service.generate_or_get_profile(db, user)
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_str = create_access_token(
            subject=user.id, expires_delta=access_token_expires,
            extra_claims={"username": user.username, "is_admin": user.is_admin},
        )
        return OtpTokenResponse(
            access_token=token_str, token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            is_new_user=is_new_user, user=UserOut.model_validate(user),
        )

    async def _consume_otp(self, db, email, otp):
        # Time is sampled after acquiring the lock: an OTP expiring while waiting
        # must not authenticate using the request's earlier arrival time.
        query = select(OtpCode).where(
            OtpCode.email == email,
        ).order_by(desc(OtpCode.created_at), desc(OtpCode.id)).limit(1).with_for_update()
        
        result = await db.execute(query.execution_options(populate_existing=True))
        otp_record = result.scalars().first()
        now = datetime.now(timezone.utc)
        
        if not otp_record or _utc(otp_record.expires_at) <= now:
            raise AuthenticationError(detail="Invalid or expired OTP")
            
        if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise AuthenticationError(detail="Too many failed attempts. Please request a new OTP.")
        if otp_record.is_used:
            raise AuthenticationError(detail="Invalid or expired OTP")
        matches = hmac.compare_digest(otp_record.code_hash, _code_hash(otp))
        # The guard also protects against a stale ORM instance/another writer.
        # Increment in SQL; never overwrite a concurrent attempt count.
        claimed = (await db.execute(update(OtpCode).where(
            OtpCode.id == otp_record.id, OtpCode.is_used == False,
            OtpCode.expires_at > now, OtpCode.attempts < settings.OTP_MAX_ATTEMPTS,
        ).values(
            attempts=OtpCode.attempts + 1,
            is_used=True if matches else case(
                (OtpCode.attempts + 1 >= settings.OTP_MAX_ATTEMPTS, True), else_=False,
            ),
        ).execution_options(synchronize_session="fetch").returning(OtpCode.id))).scalar_one_or_none()
        if claimed is None:
            raise AuthenticationError(detail="Invalid or expired OTP")
        if not matches:
            await db.commit()
            raise AuthenticationError(detail="Invalid OTP")
            
        user_query = select(User).where(User.email == email).with_for_update().execution_options(populate_existing=True)
        user_result = await db.execute(user_query)
        user = user_result.scalars().first()
        
        if user and not user.is_active:
            await db.commit()  # Correct codes for disabled accounts are consumed too.
            raise AuthenticationError(detail="Account is currently deactivated")

        is_new_user = False
        if not user:
            is_new_user = True
            username = f"player_{str(uuid.uuid4())[:8]}"
            user = User(
                email=email,
                username=username,
                hashed_password=None,
                email_verified=True,
                is_active=True,
                is_admin=False,
            )
            db.add(user)
        else:
            user.email_verified = True
        await db.flush()
        otp_record.user_id = user.id
        await db.commit()
        return user, is_new_user

    async def resend_otp(self, db: AsyncSession, email: str, *, client_address=None) -> int:
        """Allow one immediate resend, then enforce the normal cooldown."""
        return await self.request_otp(db, email, is_resend=True, client_address=client_address)


auth_service = AuthService()
