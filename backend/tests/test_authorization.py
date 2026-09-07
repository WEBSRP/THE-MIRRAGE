"""
MIRRAGE Authorization & IDOR Security Tests

Verifies that:
- User A cannot read User B's session details (returns 404/403)
- User A cannot stop User B's session
- User A cannot download or view User B's VPN profile
- User A cannot read User B's activity logs
- Challenge solves by User A are isolated from User B
"""
import pytest
from httpx import AsyncClient
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_cross_user_session_status_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
):
    """User B cannot access User A's session using User A's session ID."""
    # 1. User A starts a session
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert start_resp.status_code == 201
    user_a_session_id = start_resp.json()["session_id"]

    # 2. User B queries User A's session_id
    cross_resp = await async_client.get(
        f"{settings.API_V1_STR}/session/status",
        headers=second_auth_headers,
        params={"session_id": user_a_session_id},
    )
    # Must fail with 404 (or 403), never return User A's session details
    assert cross_resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_user_session_stop_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
):
    """User B cannot stop User A's active machine."""
    # 1. User A starts a session
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert start_resp.status_code == 201
    user_a_session_id = start_resp.json()["session_id"]

    # 2. User B attempts to stop User A's session
    cross_stop_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/stop",
        headers=second_auth_headers,
        params={"session_id": user_a_session_id},
    )
    assert cross_stop_resp.status_code in (403, 404)

    # 3. Verify User A's session is still active
    status_resp = await async_client.get(
        f"{settings.API_V1_STR}/session/status",
        headers=auth_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["session_id"] == user_a_session_id
    assert status_resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_vpn_profiles_are_isolated_per_user(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
):
    """User A and User B get distinct VPN profiles and distinct IP allocations."""
    # User A profile
    resp_a = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=auth_headers,
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()

    # User B profile
    resp_b = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=second_auth_headers,
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    # Must have distinct client identities and IPs
    assert data_a["filename"] != data_b["filename"]
    assert data_a["client_ip"] != data_b["client_ip"]


@pytest.mark.asyncio
async def test_activity_logs_are_isolated_per_user(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
):
    """User B cannot view User A's activity logs."""
    # User A starts a machine (generates activity logs)
    await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )

    # User A sees activity
    act_a = await async_client.get(
        f"{settings.API_V1_STR}/activity/",
        headers=auth_headers,
    )
    assert act_a.status_code == 200
    assert len(act_a.json()) > 0

    # User B sees only their own activity (empty initially)
    act_b = await async_client.get(
        f"{settings.API_V1_STR}/activity/",
        headers=second_auth_headers,
    )
    assert act_b.status_code == 200
    assert len(act_b.json()) == 0


@pytest.mark.asyncio
async def test_challenge_progress_isolated_between_users(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    db_session,
):
    """User A solving a challenge does NOT mark it solved for User B."""
    from backend.app.services.challenge_service import challenge_service
    await challenge_service.seed_default_challenges(db_session)

    # User A submits correct flag
    submit_resp = await async_client.post(
        f"{settings.API_V1_STR}/challenges/submit",
        headers=auth_headers,
        json={
            "challenge_slug": "first-reflection",
            "flag": "MIRRAGE{r3fl3ct10n_1s_n0t_r34l1ty_7f9a}",
        },
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["is_correct"] is True

    # User A lists challenges -> first-reflection is solved
    list_a = await async_client.get(f"{settings.API_V1_STR}/challenges/", headers=auth_headers)
    chal_a = next(c for c in list_a.json() if c["slug"] == "first-reflection")
    assert chal_a["is_solved"] is True

    # User B lists challenges -> first-reflection is NOT solved
    list_b = await async_client.get(f"{settings.API_V1_STR}/challenges/", headers=second_auth_headers)
    chal_b = next(c for c in list_b.json() if c["slug"] == "first-reflection")
    assert chal_b["is_solved"] is False
