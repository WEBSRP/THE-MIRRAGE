import pytest
from httpx import AsyncClient
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_get_vpn_status(async_client: AsyncClient, auth_headers: dict):
    """Test retrieving VPN connection status and assigned IP."""
    response = await async_client.get(
        f"{settings.API_V1_STR}/vpn/status",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "assigned_ip" in data
    assert data["assigned_ip"].startswith("10.8.0.")
    assert "indicator" in data
    assert data["indicator"] in ("connected", "disconnected")


@pytest.mark.asyncio
async def test_get_vpn_profile(async_client: AsyncClient, auth_headers: dict):
    """Test retrieving .ovpn configuration metadata."""
    response = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".ovpn")
    assert "client" in data["config_data"]
    assert "10.42.0.0" in data["config_data"]  # Route to K8s Pod network


@pytest.mark.asyncio
async def test_download_ovpn_file(async_client: AsyncClient, auth_headers: dict):
    """Test direct attachment download of .ovpn file."""
    response = await async_client.get(
        f"{settings.API_V1_STR}/vpn/download",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-openvpn-profile"
    assert "attachment" in response.headers["content-disposition"]
    assert "-----BEGIN CERTIFICATE-----" in response.text
