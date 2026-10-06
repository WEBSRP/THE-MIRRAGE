"""
MIRRAGE Concurrency & Slot Race Condition Tests

Verifies CRITICAL requirement:
- Exactly maximum 5 concurrent active sessions allowed
- Under 10+ simultaneous start requests, ACTIVE_SESSIONS <= 5 ALWAYS
- No request creates a 6th active session
- If Kubernetes provisioning fails, the slot is cleanly released
"""
import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.services.k8s_service import k8s_provisioner


@pytest.mark.asyncio
async def test_concurrent_10_session_starts_strictly_limited_to_5(db_session):
    """
    Launch 10 simultaneous session-start requests for 10 distinct users.
    Assert that:
    1. Maximum 5 sessions are successfully created (HTTP 201).
    2. Remaining 5 requests are cleanly rejected (HTTP 503 Slot Limit Exceeded).
    3. Exactly 5 active sessions exist in the database.
    """
    # 1. Create 10 distinct users and tokens
    users = []
    tokens = []
    for i in range(10):
        user = User(
            email=f"concurrent_operative_{i}@mirrage.io",
            username=f"operative_{i}",
            hashed_password=hash_password("Secret123!"),
            is_active=True,
        )
        db_session.add(user)
        users.append(user)

    await db_session.commit()
    for user in users:
        await db_session.refresh(user)
        token = create_access_token(subject=user.id)
        tokens.append(token)

    # 2. Setup AsyncClient override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async def start_for_user(tok: str):
            return await client.post(
                f"{settings.API_V1_STR}/session/start",
                headers={"Authorization": f"Bearer {tok}"},
            )

        # 3. Fire all 10 requests simultaneously
        responses = await asyncio.gather(*[start_for_user(tok) for tok in tokens])

    app.dependency_overrides.clear()

    # 4. Analyze results
    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(201)
    slot_exceeded_count = status_codes.count(503)

    assert success_count == 5, f"Expected exactly 5 successes, got {success_count}. Codes: {status_codes}"
    assert slot_exceeded_count == 5, f"Expected exactly 5 slot exceeded (503), got {slot_exceeded_count}"

    # 5. Verify database invariant: ACTIVE_SESSIONS <= 5
    from sqlalchemy import func, select
    query = select(func.count(GameSession.id)).where(
        GameSession.status.in_([
            SessionStatus.PENDING,
            SessionStatus.INITIALIZING,
            SessionStatus.PROVISIONING,
            SessionStatus.READY,
        ])
    )
    result = await db_session.execute(query)
    active_count = result.scalar()
    assert active_count == 5, f"Expected 5 active sessions in DB, found {active_count}"


@pytest.mark.asyncio
async def test_slot_released_when_k8s_provisioning_fails(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db_session,
):
    """
    Test that when Kubernetes Pod provisioning fails:
    1. The failed session transitions to ERROR.
    2. The allocated slot is immediately released.
    3. Subsequent session start requests succeed without being blocked.
    """
    # 1. Enable simulated creation failure on Mock K8s
    k8s_provisioner.simulate_creation_failure = True

    try:
        # User 1 attempts to start session -> provisioning fails
        fail_resp = await async_client.post(
            f"{settings.API_V1_STR}/session/start",
            headers=auth_headers,
        )
        assert fail_resp.status_code == 500
        data = fail_resp.json()
        assert data["code"] == "SESSION_PROVISION_ERROR"

        # Check that slot availability is still 5 (slot was not leaked)
        slots_resp = await async_client.get(f"{settings.API_V1_STR}/session/slots")
        assert slots_resp.status_code == 200
        assert slots_resp.json()["available_slots"] == 5

    finally:
        # Restore mock k8s to normal
        k8s_provisioner.simulate_creation_failure = False

    # 2. Now User 2 starts a session -> must succeed because slot was released
    ok_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=second_auth_headers,
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["status"] == "ready"
