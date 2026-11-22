from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models.session import GameSession
from backend.app.services.session_service import _to_utc, session_service
from backend.app.models.session_queue import SessionQueueEntry
from backend.app.models.user import User
from backend.app.services import session_queue
from backend.app.services.email_service import email_service


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_finishes_early", [True, False])
async def test_fifo_hold_blocks_bypass_and_expired_offer_releases_capacity(
    async_client, auth_headers, second_auth_headers, db_session, monkeypatch, cleanup_finishes_early,
):
    monkeypatch.setattr(settings, "MAX_CONCURRENT_SESSIONS", 1)
    mail = AsyncMock()
    monkeypatch.setattr(email_service, "send_slot_ready", mail)
    third = User(email="third@example.com", username="third", is_active=True)
    outsider = User(email="outsider@example.com", username="outsider", is_active=True)
    db_session.add_all([third, outsider])
    await db_session.commit()
    third_headers = {"Authorization": f"Bearer {create_access_token(subject=third.id)}"}
    outsider_headers = {"Authorization": f"Bearer {create_access_token(subject=outsider.id)}"}
    base = "/api/v1/session"

    started = await async_client.post(f"{base}/start", headers=auth_headers)
    assert started.status_code == 201
    session = await db_session.get(GameSession, started.json()["session_id"])
    assert (await async_client.post(f"{base}/queue", headers=second_auth_headers)).json()["position"] == 1
    assert (await async_client.post(f"{base}/queue", headers=second_auth_headers)).json()["position"] == 1
    assert (await async_client.post(f"{base}/queue", headers=third_headers)).json()["position"] == 2
    await session_queue.process(db_session)
    mail.assert_not_awaited()

    left = datetime.now(timezone.utc)
    with monkeypatch.context() as patch:
        patch.setattr(session_service.k8s_provisioner, "delete_player_pod", AsyncMock(return_value=False))
        assert (await async_client.post(f"{base}/stop", headers=auth_headers)).status_code == 503
    await db_session.refresh(session)
    delay = _to_utc(session.slot_release_not_before) - left
    assert timedelta(minutes=10) <= delay < timedelta(minutes=10, seconds=2)

    if not cleanup_finishes_early:
        session.slot_release_not_before = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db_session.commit()
        await session_queue.process(db_session)
        mail.assert_not_awaited()
        pending = (await async_client.get(f"{base}/slots")).json()
        assert pending["active_slots"] == 1 and pending["available_slots"] == 0

    assert (await async_client.post(f"{base}/stop", headers=auth_headers)).status_code == 200
    if cleanup_finishes_early:
        await session_queue.process(db_session)
        mail.assert_not_awaited()
        slots = (await async_client.get(f"{base}/slots")).json()
        assert slots["active_slots"] == 0 and slots["cooldown_slots"] == 1 and slots["available_slots"] == 0
        session.slot_release_not_before = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db_session.commit()

    # Even before the worker polls, the wait list has first claim on free capacity.
    blocked = await async_client.post(f"{base}/start", headers=outsider_headers)
    assert blocked.status_code == 409 and blocked.json()["code"] == "SESSION_QUEUE_REQUIRED"
    await session_queue.process(db_session)
    await session_queue.process(db_session)
    assert mail.await_count == 1
    assert timedelta(minutes=9, seconds=58) < mail.await_args.args[1] - datetime.now(timezone.utc) <= timedelta(minutes=10)
    assert (await async_client.get(f"{base}/queue", headers=second_auth_headers)).json()["status"] == "offered"
    assert (await async_client.get(f"{base}/queue", headers=third_headers)).json()["position"] == 1

    offer = await db_session.scalar(select(SessionQueueEntry).where(SessionQueueEntry.hold_until.is_not(None)))
    offer.hold_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    await session_queue.process(db_session)
    assert mail.await_count == 2
    assert mail.await_args.args[0] == third.email
    assert (await async_client.get(f"{base}/queue", headers=second_auth_headers)).json()["status"] == "idle"
    assert (await async_client.post(f"{base}/start", headers=third_headers)).status_code == 201
    assert (await async_client.get(f"{base}/queue", headers=third_headers)).json()["status"] == "idle"
    assert (await async_client.get(f"{base}/slots")).json()["active_slots"] == 1
