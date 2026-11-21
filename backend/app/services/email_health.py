"""Durable provider acceptance telemetry without message content or recipient PII."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import case, delete, func, select, update

from backend.app.core.config import settings
from backend.app.models.email_delivery import EmailDeliveryAttempt
from backend.app.services.otp_abuse import database_time


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def now(db):
    return datetime.fromtimestamp(await database_time(db), timezone.utc)


class EmailHealth:
    async def begin(self, db, provider):
        attempt = EmailDeliveryAttempt(provider=provider, outcome="pending", started_at=await now(db))
        db.add(attempt)
        await db.flush()
        attempt_id = attempt.id
        await db.commit()  # Persist intent before a request can leave the process.
        return attempt_id

    async def finish(self, db, attempt_id, outcome, error_code=None, http_status=None):
        changed = (await db.execute(update(EmailDeliveryAttempt).where(
            EmailDeliveryAttempt.id == attempt_id, EmailDeliveryAttempt.outcome == "pending",
        ).values(outcome=outcome, finished_at=await now(db), error_code=error_code, http_status=http_status)
          .execution_options(synchronize_session="fetch").returning(EmailDeliveryAttempt.id))).scalar_one_or_none()
        if changed is None:
            raise RuntimeError("Email health attempt is missing or already completed")
        await db.commit()

    async def report(self, db, provider):
        timestamp = await now(db)
        cutoff = timestamp - timedelta(days=1)
        table = EmailDeliveryAttempt
        totals = dict(accepted=0, failed=0, unknown=0, pending=0, simulated=0)
        grace = timedelta(seconds=settings.EMAIL_TIMEOUT_SECONDS + 30)
        outcome = case(((table.outcome == "pending") & (table.started_at <= timestamp - grace), "unknown"),
                       else_=table.outcome)
        for label, count in (await db.execute(select(outcome, func.count()).where(
            table.provider == provider, table.started_at >= cutoff).group_by(outcome))).all():
            totals[label] = count
        latest = (await db.execute(select(table).where(table.provider == provider, table.started_at >= cutoff)
                                   .order_by(table.started_at.desc(), table.id.desc()).limit(1))).scalar_one_or_none()
        status = ("degraded" if latest and (latest.outcome in {"failed", "unknown"} or totals["unknown"])
                  else "pending" if latest and latest.outcome == "pending"
                  else "accepting" if latest and latest.outcome == "accepted"
                  else "simulated" if latest else "not_checked")
        if latest and latest.outcome == "pending" and utc(latest.started_at) + grace <= timestamp:
            status = "degraded"
        return dict(status=status, window_seconds=86400, attempted=sum(totals.values()), **totals,
                    last_attempt_at=utc(latest.started_at) if latest else None,
                    last_error_code=latest.error_code if latest else None,
                    last_http_status=latest.http_status if latest else None,
                    mailbox_delivery_confirmed=False)

    async def cleanup(self, db):
        table = EmailDeliveryAttempt
        cutoff = await now(db) - timedelta(days=settings.EMAIL_HEALTH_RETENTION_DAYS)
        stale = select(table.id).where(table.started_at < cutoff).limit(1000)
        await db.execute(delete(table).where(table.id.in_(stale), table.started_at < cutoff)
                         .execution_options(synchronize_session=False))
        await db.commit()


email_health = EmailHealth()
