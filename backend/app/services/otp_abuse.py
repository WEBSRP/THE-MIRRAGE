"""Database-enforced OTP IP request limits and atomic global send reservations."""
import hashlib
import hmac
import ipaddress
import math

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.client_address import parse_address
from backend.app.core.config import settings
from backend.app.core.exceptions import MirrageException
from backend.app.models.otp_abuse import OtpAbuseBucket


async def database_time(db):
    expression = (func.extract("epoch", func.clock_timestamp()) if db.bind.dialect.name == "postgresql"
                  else func.strftime("%s", "now"))
    return float((await db.execute(select(expression))).scalar_one())


def ip_bucket_key(value):
    address = parse_address(value)
    # IPv6 interface-ID rotation within one normal allocation shares a budget.
    network = ipaddress.ip_network(f"{address}/{32 if address.version == 4 else 64}", strict=False)
    # Include the configured duration: quotient window numbers from different
    # durations cannot be compared by the monotonic upsert guard.
    material = f"otp-ip-v1:{settings.OTP_IP_WINDOW_SECONDS}:{network}"
    digest = hmac.new(settings.OTP_HMAC_SECRET.encode(), material.encode(),
                      hashlib.sha256).hexdigest()
    return "ip:" + digest


class OtpAbuseLimiter:
    async def _take(self, db, key, seconds, limit, now, code, message="Too many OTP requests. Please try again later."):
        model = OtpAbuseBucket
        window = int(now // seconds)
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        allowed = (await db.execute(insert(model).values(
            key=key, window=window, attempts=1, expires_at=(window + 1) * seconds,
        ).on_conflict_do_update(
            index_elements=["key"], set_={
                "window": window, "expires_at": (window + 1) * seconds,
                "attempts": case((model.window < window, 1), else_=model.attempts + 1),
            },
            where=or_(model.window < window, (model.window == window) & (model.attempts < limit)),
        ).returning(model.key))).scalar_one_or_none()
        if allowed is None:
            raise MirrageException(429, message, code,
                                   headers={"Retry-After": str(max(1, math.ceil((window + 1) * seconds - now)))})

    async def consume_ip(self, db, address):
        try:
            now = await database_time(db)
            await self._take(db, ip_bucket_key(address), settings.OTP_IP_WINDOW_SECONDS,
                             settings.OTP_IP_REQUEST_LIMIT, now, "OTP_IP_RATE_LIMIT")
            await db.commit()  # Count requests even if email cooldown/budget later rejects them.
        except SQLAlchemyError:
            await db.rollback()
            raise MirrageException(503, "OTP requests are temporarily unavailable", "OTP_THROTTLE_UNAVAILABLE") from None
        except Exception:
            await db.rollback()
            raise

    async def reserve_delivery(self, db):
        """No commit: both reservations and OTP issuance succeed or roll back together."""
        try:
            now = await database_time(db)
            await self._take(db, "global:hour", 3600, settings.OTP_EMAIL_HOURLY_LIMIT, now, "OTP_EMAIL_BUDGET")
            await self._take(db, "global:day", 86400, settings.OTP_EMAIL_DAILY_LIMIT, now, "OTP_EMAIL_BUDGET")
        except SQLAlchemyError:
            raise MirrageException(503, "OTP requests are temporarily unavailable", "OTP_THROTTLE_UNAVAILABLE") from None

    async def reserve_queue_notification(self, db):
        """Use a separate send budget so queue mail cannot consume sign-in capacity."""
        now = await database_time(db)
        for period, seconds, limit in (("hour", 3600, 30), ("day", 86400, 100)):
            await self._take(db, "queue:" + period, seconds, limit, now, "QUEUE_EMAIL_BUDGET",
                             "The session notification email budget is exhausted.")

    async def cleanup(self, db):
        now = await database_time(db)
        cutoff = int(now) - settings.OTP_IP_BUCKET_RETENTION_SECONDS
        table = OtpAbuseBucket
        stale = select(table.key).where(table.key.like("ip:%"), table.expires_at <= cutoff).limit(1000)
        await db.execute(delete(table).where(table.key.in_(stale), table.expires_at <= cutoff)
                         .execution_options(synchronize_session=False))
        await db.commit()


otp_abuse_limiter = OtpAbuseLimiter()
