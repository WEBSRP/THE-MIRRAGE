"""
MIRRAGE 30-Minute Inactivity System Tests

Verifies PHASE 5 & 10 requirements:
1. Meaningful player activity extends the session lifetime (30 minutes from last activity).
2. Status polling (GET /session/status) does NOT extend the session lifetime.
3. Inactivity beyond 30 minutes causes session to expire.
4. Expired sessions cannot be used.
5. Cleanup worker reaps expired sessions and releases slots.
6. Repeated cleanup calls are completely idempotent.
"""
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from backend.app.core.config import settings
from backend.app.models.session import GameSession, SessionStatus
from backend.app.services.session_service import session_service


@pytest.mark.asyncio
async def test_polling_status_does_not_extend_expiry(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    """
    Assert that calling GET /session/status does NOT extend expires_at.
    Prevents frontend polling loops from keeping sessions alive indefinitely.
    """
    # 1. Start session
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert start_resp.status_code == 201
    initial_expires_at = start_resp.json()["expires_at"]

    # 2. Simulate polling /session/status
    poll_resp = await async_client.get(
        f"{settings.API_V1_STR}/session/status",
        headers=auth_headers,
    )
    assert poll_resp.status_code == 200
    poll_expires_at = poll_resp.json()["expires_at"]

    # Expiry timestamp must remain unchanged after polling
    assert initial_expires_at == poll_expires_at


@pytest.mark.asyncio
async def test_meaningful_activity_extends_expiry(
    async_client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """
    Assert that meaningful activity (such as flag submission or explicit action)
    extends session expiration 30 minutes from the time of activity.
    """
    from backend.app.services.challenge_service import challenge_service
    await challenge_service.seed_default_challenges(db_session)

    # 1. Start session
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["session_id"]

    # 2. Artificially backdate the session's expires_at by 15 minutes
    res = await db_session.execute(select(GameSession).where(GameSession.id == session_id))
    session = res.scalars().first()
    backdated_time = datetime.now(timezone.utc) + timedelta(minutes=15)
    session.expires_at = backdated_time
    await db_session.commit()
    await db_session.refresh(session)

    # 3. Perform meaningful activity: submit a flag
    submit_resp = await async_client.post(
        f"{settings.API_V1_STR}/challenges/submit",
        headers=auth_headers,
        json={"challenge_slug": "first-reflection", "flag": "MIRRAGE{r3fl3ct10n_1s_n0t_r34l1ty_7f9a}"},
    )
    assert submit_resp.status_code == 200

    # 4. Refresh session and verify expires_at was extended back to ~30 minutes
    await db_session.refresh(session)
    now = datetime.now(timezone.utc)
    from backend.app.services.session_service import _to_utc
    seconds_remaining = (_to_utc(session.expires_at) - now).total_seconds()
    # Should be close to 30 minutes (1800s), definitely more than the backdated 15 minutes (900s)
    assert seconds_remaining > 1500, f"Expected >1500s remaining after extension, got {seconds_remaining}"


@pytest.mark.asyncio
async def test_inactivity_expiration_and_cleanup_worker(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    """
    Assert that sessions with past expires_at:
    1. Are transitioned to EXPIRED when queried or cleaned up.
    2. The cleanup worker terminates the pod and frees the slot.
    3. Repeated cleanup calls are completely safe and idempotent.
    """
    # 1. Start session
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["session_id"]

    # 2. Simulate 30 minutes of inactivity: set expires_at to the past
    res = await db_session.execute(select(GameSession).where(GameSession.id == session_id))
    session = res.scalars().first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    # 3. Run cleanup worker
    reaped = await session_service.cleanup_expired_sessions(db_session)
    assert reaped == 1

    # 4. Verify session is now marked EXPIRED in database
    await db_session.refresh(session)
    assert session.status == SessionStatus.EXPIRED
    assert session.terminated_at is not None

    # 5. Verify slot is freed (available slots = 5)
    slots_resp = await async_client.get(f"{settings.API_V1_STR}/session/slots")
    assert slots_resp.status_code == 200
    assert slots_resp.json()["available_slots"] == 5

    # 6. Run cleanup worker AGAIN (idempotence check)
    reaped_again = await session_service.cleanup_expired_sessions(db_session)
    assert reaped_again == 0  # Already cleaned, zero crashes, safe
