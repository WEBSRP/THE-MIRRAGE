import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import desc, select
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


class AuthService:
    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch user by ID."""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def request_otp(self, db: AsyncSession, email: str) -> None:
        """Generate and send OTP for the given email."""
        email = email.lower().strip()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Check rate limiting
        window_start = now - timedelta(minutes=settings.OTP_RATE_LIMIT_WINDOW_MINUTES)
        query = select(OtpCode).where(
            OtpCode.email == email,
            OtpCode.created_at >= window_start
        )
        result = await db.execute(query)
        recent_requests = result.scalars().all()
        
        if len(recent_requests) >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
            raise MirrageException(
                status_code=429,
                detail="Too many OTP requests. Please try again later.",
                code="OTP_RATE_LIMIT"
            )
            
        # Invalidate any existing unused OTPs
        query = select(OtpCode).where(
            OtpCode.email == email,
            OtpCode.is_used == False,
            OtpCode.expires_at > now
        )
        result = await db.execute(query)
        for old_otp in result.scalars().all():
            old_otp.is_used = True
            
        # Generate cryptographically secure 6-digit OTP
        otp = f"{secrets.randbelow(1000000):06d}"
        
        # Hash OTP using dedicated OTP_HMAC_SECRET
        code_hash = hmac.new(
            settings.OTP_HMAC_SECRET.encode(),
            otp.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Find if user exists to populate user_id
        user_query = select(User).where(User.email == email)
        user_result = await db.execute(user_query)
        existing_user = user_result.scalars().first()
        
        # Create OtpCode record
        new_otp = OtpCode(
            email=email,
            user_id=existing_user.id if existing_user else None,
            code_hash=code_hash,
            expires_at=now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        db.add(new_otp)
        await db.commit()
        
        # Send OTP
        await email_service.send_otp(email, otp)

    async def verify_otp(self, db: AsyncSession, email: str, otp: str) -> OtpTokenResponse:
        """Verify OTP and authenticate/create user."""
        email = email.lower().strip()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        query = select(OtpCode).where(
            OtpCode.email == email,
            OtpCode.is_used == False,
            OtpCode.expires_at > now
        ).order_by(desc(OtpCode.created_at))
        
        result = await db.execute(query)
        otp_record = result.scalars().first()
        
        if not otp_record:
            raise AuthenticationError(detail="Invalid or expired OTP")
            
        if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp_record.is_used = True
            await db.commit()
            raise AuthenticationError(detail="Too many failed attempts. Please request a new OTP.")
            
        otp_record.attempts += 1
        
        expected_hash = hmac.new(
            settings.OTP_HMAC_SECRET.encode(),
            otp.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(otp_record.code_hash, expected_hash):
            await db.commit()
            raise AuthenticationError(detail="Invalid OTP")
            
        otp_record.is_used = True
        
        user_query = select(User).where(User.email == email)
        user_result = await db.execute(user_query)
        user = user_result.scalars().first()
        
        if user and not user.is_active:
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
            
        await db.commit()
        await db.refresh(user)
        
        # Generate VPN profile for new users
        if is_new_user:
            await vpn_service.generate_or_get_profile(db, user)
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_str = create_access_token(
            subject=user.id,
            expires_delta=access_token_expires,
            extra_claims={"username": user.username, "is_admin": user.is_admin}
        )
        
        return OtpTokenResponse(
            access_token=token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            is_new_user=is_new_user,
            user=UserOut.model_validate(user)
        )

    async def resend_otp(self, db: AsyncSession, email: str) -> None:
        """Resend OTP with cooldown enforcement."""
        email = email.lower().strip()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        query = select(OtpCode).where(
            OtpCode.email == email
        ).order_by(desc(OtpCode.created_at))
        result = await db.execute(query)
        last_otp = result.scalars().first()
        
        if last_otp:
            time_since_last = (now - last_otp.created_at).total_seconds()
            if time_since_last < settings.OTP_RESEND_COOLDOWN_SECONDS:
                raise MirrageException(
                    status_code=429,
                    detail=f"Please wait {int(settings.OTP_RESEND_COOLDOWN_SECONDS - time_since_last)} seconds before requesting a new code.",
                    code="OTP_COOLDOWN"
                )
                
        await self.request_otp(db, email)

auth_service = AuthService()
