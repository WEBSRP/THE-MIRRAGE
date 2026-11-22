"""FIFO waiting list sharing the same database lock as session allocation."""
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import delete, exists, func, or_, select, text, update

from backend.app.core.config import settings
from backend.app.core.exceptions import ActiveSessionExistsError, MirrageException, SlotLimitExceededError
from backend.app.models.session import GameSession
from backend.app.models.session_queue import SessionQueueEntry
from backend.app.models.user import User
from backend.app.models.vpn import VpnProfile, VpnRevocation
from backend.app.schemas.session import SessionQueueStatus
from backend.app.services.vpn_access import require_vpn_access

logger = logging.getLogger(__name__)
HOLD_DURATION = timedelta(minutes=10)
Queue = SessionQueueEntry


async def lock_slots(db):
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(74291823)"))
    else:
        # Acquire SQLite's write lock before reading state used for admission.
        await db.execute(update(Queue).where(Queue.id < 0).values(hold_until=None))


def _valid(now):
    return or_(Queue.hold_until.is_(None), Queue.hold_until > now)


def _eligible():
    return (
        exists().where(User.id == Queue.user_id, User.is_active.is_(True)).correlate(Queue),
        ~exists().where(VpnRevocation.user_id == Queue.user_id).correlate(Queue),
        ~exists().where(VpnProfile.user_id == Queue.user_id, VpnProfile.revoked_at.is_not(None)).correlate(Queue),
    )


async def open_slots(db, active_count):
    now = datetime.now(timezone.utc)
    queued = await db.scalar(select(func.count(Queue.id)).where(_valid(now), *_eligible()))
    return max(0, settings.MAX_CONCURRENT_SESSIONS - active_count - queued)


async def get_status(db, user_id):
    now = datetime.now(timezone.utc)
    row = await db.scalar(select(Queue).where(Queue.user_id == user_id, _valid(now), *_eligible()))
    if row is None:
        return SessionQueueStatus(status="idle")
    if row.hold_until is not None:
        deadline = row.hold_until
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return SessionQueueStatus(status="offered", hold_until=deadline)
    ahead = await db.scalar(select(func.count(Queue.id)).where(
        Queue.id < row.id, Queue.hold_until.is_(None), *_eligible(),
    ))
    return SessionQueueStatus(status="waiting", position=ahead + 1)


async def require_slot(db, user_id, active_count):
    """Called under the admission lock. Return the offer to consume at commit."""
    if active_count >= settings.MAX_CONCURRENT_SESSIONS:
        raise SlotLimitExceededError(settings.MAX_CONCURRENT_SESSIONS)
    now = datetime.now(timezone.utc)
    entry = await db.scalar(select(Queue).where(Queue.user_id == user_id, _valid(now), *_eligible()))
    if entry is not None and entry.hold_until is not None:
        return entry
    if entry is not None or not await open_slots(db, active_count):
        raise MirrageException(
            409, "Available slots are reserved for the waiting list. Join the queue or wait for your turn.",
            "SESSION_QUEUE_REQUIRED",
        )
    return None


async def join(db, user_id):
    from backend.app.services.session_service import ACTIVE_STATUSES, slot_counts

    await require_vpn_access(db, user_id)
    await lock_slots(db)
    active = await db.scalar(select(GameSession.id).where(
        GameSession.user_id == user_id, GameSession.status.in_(ACTIVE_STATUSES),
    ).limit(1))
    if active is not None:
        raise ActiveSessionExistsError(active)
    status = await get_status(db, user_id)
    if status.status != "idle":
        await db.commit()
        return status
    active_count, cooldown = await slot_counts(db, datetime.now(timezone.utc))
    if not await open_slots(db, active_count + cooldown):
        await db.execute(delete(Queue).where(Queue.user_id == user_id))
        db.add(Queue(user_id=user_id))
        await db.flush()
        status = await get_status(db, user_id)
    await db.commit()
    return status


async def leave(db, user_id):
    await lock_slots(db)
    await db.execute(delete(Queue).where(Queue.user_id == user_id))
    await db.commit()
    return SessionQueueStatus(status="idle")


async def process(db):
    from backend.app.services.email_service import EmailDeliveryError, email_service
    from backend.app.services.otp_abuse import otp_abuse_limiter
    from backend.app.services.session_service import ACTIVE_STATUSES, slot_counts

    await lock_slots(db)
    now = datetime.now(timezone.utc)
    active_sessions = select(GameSession.user_id).where(GameSession.status.in_(ACTIVE_STATUSES))
    disabled = select(User.id).where(User.is_active.is_(False))
    revoked = select(VpnRevocation.user_id)
    revoked_profiles = select(VpnProfile.user_id).where(VpnProfile.revoked_at.is_not(None))
    await db.execute(delete(Queue).where(or_(
        Queue.hold_until <= now, Queue.user_id.in_(active_sessions), Queue.user_id.in_(disabled),
        Queue.user_id.in_(revoked), Queue.user_id.in_(revoked_profiles),
    )).execution_options(synchronize_session=False))
    active_count, cooldown = await slot_counts(db, now)
    reserved = await db.scalar(select(func.count(Queue.id)).where(Queue.hold_until > now))
    count = max(0, settings.MAX_CONCURRENT_SESSIONS - active_count - cooldown - reserved)
    if count:
        waiting = await db.scalars(select(Queue).where(Queue.hold_until.is_(None)).order_by(Queue.id).limit(count))
        for entry in waiting:
            entry.hold_until = now + HOLD_DURATION
    await db.flush()

    # Claim one notification durably before making the external request. A crash
    # or ambiguous provider outcome cannot generate duplicate emails on retry.
    pending = (await db.execute(select(Queue, User.email).join(User, User.id == Queue.user_id).where(
        Queue.hold_until > now, Queue.email_attempted_at.is_(None), *_eligible(),
    ).order_by(Queue.id).limit(1))).first()
    recipient = None
    if pending:
        try:
            async with db.begin_nested():
                await otp_abuse_limiter.reserve_queue_notification(db)
        except MirrageException as error:
            if error.status_code != 429:
                raise
        else:
            entry, recipient = pending
            entry.email_attempted_at = now
            deadline = now + HOLD_DURATION
            entry.hold_until = deadline
    await db.commit()
    if recipient:
        try:
            await email_service.send_slot_ready(recipient, deadline)
        except EmailDeliveryError as error:
            logger.warning("Slot-ready email delivery result: %s", error.code)
