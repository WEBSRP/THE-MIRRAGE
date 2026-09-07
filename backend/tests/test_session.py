import pytest
from httpx import AsyncClient
from backend.app.core.config import settings
from backend.app.models.session import SessionStatus


@pytest.mark.asyncio
async def test_get_slots_info(async_client: AsyncClient):
    """Test public or authenticated slot availability check."""
    response = await async_client.get(f"{settings.API_V1_STR}/session/slots")
    assert response.status_code == 200
    data = response.json()
    assert data["total_slots"] == 3
    assert data["available_slots"] <= 3
    assert "is_slot_available" in data


@pytest.mark.asyncio
async def test_start_session_lifecycle(async_client: AsyncClient, auth_headers: dict, test_user):
    """Test complete player machine lifecycle: Start -> Status -> Stop."""
    # 1. Start machine
    start_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
        json={"difficulty": "standard"},
    )
    assert start_resp.status_code == 201
    start_data = start_resp.json()
    assert "session_id" in start_data
    assert start_data["status"] == SessionStatus.READY
    # Verify Decoy IP is in 10.42.0.x
    assert start_data["mirage_ip"].startswith("10.42.0.")
    assert start_data["mirage_port"] == 22
    # Verify CTF IP is NEVER exposed in the response
    assert "ctf_ip" not in start_data

    session_id = start_data["session_id"]

    # 2. Check session status
    status_resp = await async_client.get(
        f"{settings.API_V1_STR}/session/status",
        headers=auth_headers,
    )
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["session_id"] == session_id
    assert status_data["is_ready"] is True
    assert status_data["time_remaining_seconds"] > 0

    # 3. Stop session
    stop_resp = await async_client.post(
        f"{settings.API_V1_STR}/session/stop",
        headers=auth_headers,
        params={"session_id": session_id},
    )
    assert stop_resp.status_code == 200
    stop_data = stop_resp.json()
    assert stop_data["status"] == SessionStatus.TERMINATED


@pytest.mark.asyncio
async def test_start_duplicate_session_returns_existing(
    async_client: AsyncClient, auth_headers: dict
):
    """Test that starting a session when one is already active returns the existing session."""
    resp1 = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert resp1.status_code == 201
    id1 = resp1.json()["session_id"]

    # Starting again should return current session smoothly
    resp2 = await async_client.post(
        f"{settings.API_V1_STR}/session/start",
        headers=auth_headers,
    )
    assert resp2.status_code == 201 or resp2.status_code == 200
    id2 = resp2.json()["session_id"]
    assert id1 == id2


@pytest.mark.asyncio
async def test_unauthenticated_session_start_rejected(async_client: AsyncClient):
    """Test that unauthenticated requests to start machine are rejected."""
    response = await async_client.post(f"{settings.API_V1_STR}/session/start")
    assert response.status_code == 401
