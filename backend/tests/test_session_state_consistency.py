"""
MIRRAGE Session State Consistency & Reconciliation Test Suite

Verifies:
1. Pod missing, DB says READY -> session reconciled / not reported READY.
2. Target IP cleared or omitted when environment is not active.
3. Target IP updated if pod IP changes.
4. Pod pending -> session not marked READY.
5. Pod running but containers not ready -> session not marked READY.
6. Pod running and containers ready -> session marked READY.
7. Disappearing pod detected on session-status read.
8. Disappearing pod detected by reconciliation pass.
9. Five-session limit enforced (5 active allowed, 6th rejected, released slot immediately usable).
10. Double start from same player rejected or safely idempotent without allocating a second slot.
11. Stop Environment is safe to call when pod already gone.
12. Stop Environment clears target IP.
13. Backend startup reconciles stale READY sessions from DB.
14. Countdown reconstructs correctly from backend timestamp.
15. Frontend / Schema does not display target IP when session is not READY.
"""
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.session import GameSession, SessionStatus
from backend.app.services.k8s_service import k8s_provisioner
from backend.app.services.session_service import session_service


@pytest.mark.asyncio
async def test_1_pod_missing_db_says_ready_reconciles_not_ready(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """1. Pod missing, DB says READY -> session reconciled / not reported READY."""
    # Start session
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    # Forcibly delete the pod from mock K8s (simulating sudden pod deletion externally)
    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    assert session.pod_name in k8s_provisioner.pods
    del k8s_provisioner.pods[session.pod_name]

    # Read status: backend must detect missing pod, reconcile DB, and NOT report ready
    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["is_ready"] is False
    assert data["status"] == SessionStatus.TERMINATED.value
    assert data["mirage_ip"] is None


@pytest.mark.asyncio
async def test_2_target_ip_cleared_when_environment_not_active(
    async_client: AsyncClient, auth_headers: dict
):
    """2. Target IP cleared or omitted when environment is not active."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]
    assert start_resp.json()["mirage_ip"] is not None

    # Stop environment
    stop_resp = await async_client.post(f"{settings.API_V1_STR}/session/stop", headers=auth_headers, params={"session_id": sid})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["mirage_ip"] is None

    # Status check after stop must return mirage_ip as None
    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["mirage_ip"] is None
    assert status_resp.json()["is_ready"] is False


@pytest.mark.asyncio
async def test_3_target_ip_updated_if_pod_ip_changes(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """3. Target IP updated if pod IP changes."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    # Change the IP in Kubernetes pod
    k8s_provisioner.pods[session.pod_name]["ip"] = "10.42.0.199"

    # Status poll must detect updated pod IP
    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["mirage_ip"] == "10.42.0.199"
    assert data["is_ready"] is True


@pytest.mark.asyncio
async def test_4_pod_pending_session_not_marked_ready(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """4. Pod pending -> session not marked READY."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    # Simulate pod in Pending phase
    k8s_provisioner.pods[session.pod_name]["phase"] = "Pending"
    k8s_provisioner.pods[session.pod_name]["ready"] = False

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["is_ready"] is False
    assert data["status"] != SessionStatus.READY.value


@pytest.mark.asyncio
async def test_5_pod_running_but_containers_not_ready_not_marked_ready(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """5. Pod running but containers not ready -> session not marked READY."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    # Running phase but ready condition is False
    k8s_provisioner.pods[session.pod_name]["phase"] = "Running"
    k8s_provisioner.pods[session.pod_name]["ready"] = False

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["is_ready"] is False
    assert data["status"] == SessionStatus.INITIALIZING.value


@pytest.mark.asyncio
async def test_6_pod_running_and_containers_ready_marked_ready(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """6. Pod running and containers ready -> session marked READY."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    k8s_provisioner.pods[session.pod_name]["phase"] = "Running"
    k8s_provisioner.pods[session.pod_name]["ready"] = True
    k8s_provisioner.pods[session.pod_name]["ip"] = "10.42.0.88"

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["is_ready"] is True
    assert data["status"] == SessionStatus.READY.value
    assert data["mirage_ip"] == "10.42.0.88"


@pytest.mark.asyncio
async def test_7_disappearing_pod_detected_on_status_read(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """7. Disappearing pod detected on session-status read."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    k8s_provisioner.pods.pop(session.pod_name, None)

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == SessionStatus.TERMINATED.value
    assert data["is_ready"] is False
    assert data["mirage_ip"] is None


@pytest.mark.asyncio
async def test_8_disappearing_pod_detected_by_reconciliation_pass(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """8. Disappearing pod detected by reconciliation pass."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    k8s_provisioner.pods.pop(session.pod_name, None)

    # Run reconciliation pass explicitly
    reconciled = await session_service.reconcile_orphaned_sessions(db_session)
    assert reconciled >= 1

    # Verify session is TERMINATED in DB
    await db_session.refresh(session)
    assert session.status == SessionStatus.TERMINATED
    assert session.mirage_ip is None


@pytest.mark.asyncio
async def test_9_five_session_limit_enforced_and_released_slot_reused(
    async_client: AsyncClient, test_user, db_session
):
    """9. Five-session limit enforced: 5 active allowed, 6th rejected, released slot immediately usable."""
    from backend.app.core.security import create_access_token, hash_password
    from backend.app.models.user import User

    users = []
    tokens = []
    for i in range(6):
        u = User(
            email=f"limit_user_{i}@mirrage.io",
            username=f"limit_user_{i}",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        db_session.add(u)
        users.append(u)
    await db_session.commit()

    for u in users:
        await db_session.refresh(u)
        tokens.append(create_access_token(subject=u.id))

    # Start 5 sessions -> all 5 must succeed
    for i in range(5):
        resp = await async_client.post(
            f"{settings.API_V1_STR}/session/start",
            headers={"Authorization": f"Bearer {tokens[i]}"},
        )
        assert resp.status_code == 201, f"Failed starting user {i}: {resp.text}"

    # 6th session must be rejected with 503
    resp_6th = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers={"Authorization": f"Bearer {tokens[5]}"},
    )
    assert resp_6th.status_code == 503

    # Stop 1 session (user 0)
    stop_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/stop",
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )
    assert stop_resp.status_code == 200

    # Now 6th user can start successfully
    retry_6th = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers={"Authorization": f"Bearer {tokens[5]}"},
    )
    assert retry_6th.status_code == 201


@pytest.mark.asyncio
async def test_10_double_start_from_same_player_safe_and_idempotent(
    async_client: AsyncClient, auth_headers: dict
):
    """10. Double start from same player rejected or safely idempotent without allocating a second slot."""
    resp1 = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert resp1.status_code == 201
    sid1 = resp1.json()["session_id"]

    # Duplicate call returns the existing session smoothly
    resp2 = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert resp2.status_code in (200, 201)
    assert resp2.json()["session_id"] == sid1


@pytest.mark.asyncio
async def test_11_stop_safe_when_pod_already_gone(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """11. Stop Environment is safe to call when pod already gone."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    k8s_provisioner.pods.pop(session.pod_name, None)

    # Stop when pod is already gone
    stop_resp = await async_client.post(f"{settings.API_V1_STR}/session/stop", headers=auth_headers, params={"session_id": sid})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == SessionStatus.TERMINATED.value

    # Repeat stop must also succeed idempotently
    repeat_stop = await async_client.post(f"{settings.API_V1_STR}/session/stop", headers=auth_headers, params={"session_id": sid})
    assert repeat_stop.status_code == 200


@pytest.mark.asyncio
async def test_12_stop_clears_target_ip(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """12. Stop Environment clears target IP."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    stop_resp = await async_client.post(f"{settings.API_V1_STR}/session/stop", headers=auth_headers, params={"session_id": sid})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["mirage_ip"] is None

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    assert session.mirage_ip is None
    assert session.pod_ip is None


@pytest.mark.asyncio
async def test_13_startup_reconciliation_cleans_stale_sessions(db_session, test_user):
    """13. Backend startup reconciles stale READY sessions from DB."""
    stale_session = GameSession(
        user_id=test_user.id,
        status=SessionStatus.READY,
        pod_name="mock-nonexistent-pod-9999",
        mirage_ip="10.42.0.10",
        pod_ip="10.42.0.10",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=25),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_session)
    await db_session.commit()
    await db_session.refresh(stale_session)

    # Pod mock-nonexistent-pod-9999 does not exist in k8s_provisioner.pods
    assert "mock-nonexistent-pod-9999" not in k8s_provisioner.pods

    # Simulate startup reconciliation
    reconciled = await session_service.reconcile_orphaned_sessions(db_session)
    assert reconciled == 1

    await db_session.refresh(stale_session)
    assert stale_session.status == SessionStatus.TERMINATED
    assert stale_session.mirage_ip is None


@pytest.mark.asyncio
async def test_14_countdown_reconstructs_correctly_from_backend_timestamp(
    async_client: AsyncClient, auth_headers: dict
):
    """14. Countdown reconstructs correctly from backend timestamp."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    assert start_resp.status_code == 201
    data = start_resp.json()
    assert "initialization_deadline" in data
    assert data["initialization_deadline"] is not None

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["initialization_deadline"] is not None
    assert "created_at" in st_data


@pytest.mark.asyncio
async def test_15_status_response_does_not_display_target_ip_when_not_ready(
    async_client: AsyncClient, auth_headers: dict, db_session
):
    """15. Frontend / Schema does not display target IP when session is not READY."""
    start_resp = await async_client.post(f"{settings.API_V1_STR}/session/start", headers=auth_headers)
    sid = start_resp.json()["session_id"]

    res = await db_session.execute(select(GameSession).where(GameSession.id == sid))
    session = res.scalars().first()
    # Simulate pod not ready
    k8s_provisioner.pods[session.pod_name]["ready"] = False

    status_resp = await async_client.get(f"{settings.API_V1_STR}/session/status", headers=auth_headers)
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["is_ready"] is False
    assert st_data["mirage_ip"] is None
