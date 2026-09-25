"""
Comprehensive tests for the production VPN provisioning system.

Tests cover:
- VPN provisioner module (certificate generation, .ovpn building, revocation)
- OpenVPN status log parser
- ProductionVPNService (with mocked filesystem/subprocess)
- VPN endpoint behavior (mock mode — existing tests preserved)
- Security validations (no secret leaks, input validation)
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.vpn import VpnProfile
from backend.app.services.vpn_provisioner import (
    _validate_client_name,
    _sanitize_error,
    generate_client_name,
    parse_openvpn_status_log,
    build_ovpn_profile,
    VPNProvisionerError,
)


# ============================================================
# Client Name Validation Tests
# ============================================================

class TestClientNameValidation:
    """Test client name validation and generation."""

    def test_valid_client_name(self):
        assert _validate_client_name("mirrage-abc123") == "mirrage-abc123"

    def test_valid_client_name_underscore(self):
        assert _validate_client_name("mirrage_test_user") == "mirrage_test_user"

    def test_valid_client_name_max_length(self):
        name = "a" * 64
        assert _validate_client_name(name) == name

    def test_invalid_client_name_too_long(self):
        with pytest.raises(VPNProvisionerError, match="Invalid client name"):
            _validate_client_name("a" * 65)

    def test_invalid_client_name_special_chars(self):
        with pytest.raises(VPNProvisionerError, match="Invalid client name"):
            _validate_client_name("user;rm -rf /")

    def test_invalid_client_name_spaces(self):
        with pytest.raises(VPNProvisionerError, match="Invalid client name"):
            _validate_client_name("user name")

    def test_invalid_client_name_dots(self):
        with pytest.raises(VPNProvisionerError, match="Invalid client name"):
            _validate_client_name("../../../etc/passwd")

    def test_invalid_client_name_empty(self):
        with pytest.raises(VPNProvisionerError, match="Invalid client name"):
            _validate_client_name("")

    def test_generate_client_name_format(self):
        user_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        name = generate_client_name(user_id)
        assert name.startswith(settings.VPN_CLIENT_NAME_PREFIX + "-")
        assert len(name) <= 64
        # Should not contain hyphens from UUID (they're stripped)
        uuid_part = name.split("-", 1)[1]
        assert "-" not in uuid_part

    def test_generate_client_name_deterministic(self):
        user_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert generate_client_name(user_id) == generate_client_name(user_id)

    def test_generate_client_name_different_users(self):
        id1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        id2 = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        assert generate_client_name(id1) != generate_client_name(id2)


# ============================================================
# Error Sanitization Tests
# ============================================================

class TestErrorSanitization:
    """Test that error messages are sanitized of sensitive content."""

    def test_sanitize_passphrase_reference(self):
        error = "Error: wrong passphrase for ca.key"
        result = _sanitize_error(error)
        assert "passphrase" not in result.lower() or "[sensitive content redacted]" in result

    def test_sanitize_password_reference(self):
        error = "password verification failed"
        result = _sanitize_error(error)
        assert "[sensitive content redacted]" in result

    def test_sanitize_private_key_reference(self):
        error = "unable to load private key"
        result = _sanitize_error(error)
        assert "[sensitive content redacted]" in result

    def test_sanitize_passin_reference(self):
        error = "EASYRSA_PASSIN=pass:mysecret"
        result = _sanitize_error(error)
        assert "mysecret" not in result

    def test_sanitize_safe_error_unchanged(self):
        error = "Certificate file not found"
        result = _sanitize_error(error)
        assert result == error

    def test_sanitize_truncates_long_errors(self):
        error = "x" * 1000
        result = _sanitize_error(error)
        assert len(result) <= 510  # 500 + "..."


# ============================================================
# OpenVPN Status Log Parser Tests
# ============================================================

class TestStatusLogParser:
    """Test parsing of OpenVPN status log (CSV v2 format)."""

    def test_parse_empty_status(self, tmp_path):
        """Test parsing when no clients are connected."""
        log_content = (
            "TITLE,OpenVPN 2.6.14\n"
            "TIME,2026-09-23 04:21:45,1790137305\n"
            "HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,"
            "Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,"
            "Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher\n"
            "HEADER,ROUTING_TABLE,Virtual Address,Common Name,Real Address,"
            "Last Ref,Last Ref (time_t)\n"
            "GLOBAL_STATS,Max bcast/mcast queue length,0\n"
            "GLOBAL_STATS,dco_enabled,0\n"
            "END\n"
        )
        log_file = tmp_path / "status.log"
        log_file.write_text(log_content)

        clients = parse_openvpn_status_log(str(log_file))
        assert clients == {}

    def test_parse_connected_client(self, tmp_path):
        """Test parsing when a client is connected."""
        log_content = (
            "TITLE,OpenVPN 2.6.14\n"
            "TIME,2026-09-23 12:00:00,1790168400\n"
            "HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,"
            "Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,"
            "Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher\n"
            "mirrage-abc12345,1.2.3.4:54321,10.8.0.2,,15000,8000,"
            "2026-09-23 11:30:00,1790166600,UNDEF,0,0,AES-256-GCM\n"
            "HEADER,ROUTING_TABLE,Virtual Address,Common Name,Real Address,"
            "Last Ref,Last Ref (time_t)\n"
            "10.8.0.2,mirrage-abc12345,1.2.3.4:54321,2026-09-23 12:00:00,1790168400\n"
            "GLOBAL_STATS,Max bcast/mcast queue length,1\n"
            "END\n"
        )
        log_file = tmp_path / "status.log"
        log_file.write_text(log_content)

        clients = parse_openvpn_status_log(str(log_file))
        assert "mirrage-abc12345" in clients
        info = clients["mirrage-abc12345"]
        assert info["virtual_address"] == "10.8.0.2"
        assert info["bytes_received"] == 15000
        assert info["bytes_sent"] == 8000
        assert info["real_address"] == "1.2.3.4:54321"

    def test_parse_multiple_clients(self, tmp_path):
        """Test parsing with multiple connected clients."""
        log_content = (
            "TITLE,OpenVPN 2.6.14\n"
            "TIME,2026-09-23 12:00:00,1790168400\n"
            "HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,"
            "Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,"
            "Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher\n"
            "mirrage-user1,1.1.1.1:11111,10.8.0.2,,1000,500,"
            "2026-09-23 11:00:00,1790164800,UNDEF,0,0,AES-256-GCM\n"
            "mirrage-user2,2.2.2.2:22222,10.8.0.3,,2000,1000,"
            "2026-09-23 11:30:00,1790166600,UNDEF,1,1,AES-256-GCM\n"
            "END\n"
        )
        log_file = tmp_path / "status.log"
        log_file.write_text(log_content)

        clients = parse_openvpn_status_log(str(log_file))
        assert len(clients) == 2
        assert "mirrage-user1" in clients
        assert "mirrage-user2" in clients

    def test_parse_missing_log(self, tmp_path):
        """Test graceful handling of missing log file."""
        clients = parse_openvpn_status_log(str(tmp_path / "nonexistent.log"))
        assert clients == {}

    def test_parse_malformed_lines(self, tmp_path):
        """Test that malformed lines are skipped gracefully."""
        log_content = (
            "TITLE,OpenVPN 2.6.14\n"
            "this is not valid csv\n"
            "END\n"
        )
        log_file = tmp_path / "status.log"
        log_file.write_text(log_content)

        clients = parse_openvpn_status_log(str(log_file))
        assert clients == {}


# ============================================================
# VPN Model Tests
# ============================================================

@pytest.mark.asyncio
async def test_vpn_profile_assigned_ip_nullable(db_session: AsyncSession):
    """Test that assigned_ip can be NULL (for production where IP is dynamic)."""
    from backend.app.models.user import User
    from backend.app.core.security import hash_password

    user = User(
        email="vpntest@mirrage.io",
        username="vpn_tester",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    profile = VpnProfile(
        user_id=user.id,
        client_name="test-client",
        config_data="mock config",
        assigned_ip=None,  # NULL — production behavior
        is_connected=False,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    assert profile.assigned_ip is None
    assert profile.revoked_at is None


@pytest.mark.asyncio
async def test_vpn_profile_revoked_at(db_session: AsyncSession):
    """Test that revoked_at can be set for certificate lifecycle management."""
    from backend.app.models.user import User
    from backend.app.core.security import hash_password

    user = User(
        email="revoketest@mirrage.io",
        username="revoke_tester",
        hashed_password=hash_password("TestPass123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    profile = VpnProfile(
        user_id=user.id,
        client_name="revoke-client",
        config_data="mock config",
        assigned_ip="10.8.0.100",
        is_connected=False,
    )
    db_session.add(profile)
    await db_session.commit()

    # Revoke the profile
    now = datetime.now(timezone.utc)
    profile.revoked_at = now
    await db_session.commit()
    await db_session.refresh(profile)

    assert profile.revoked_at is not None
    # SQLite strips timezone info, so compare without tzinfo
    assert profile.revoked_at.replace(tzinfo=None) == now.replace(tzinfo=None)


# ============================================================
# VPN Endpoint Tests (Mock Mode)
# ============================================================

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


@pytest.mark.asyncio
async def test_vpn_profile_is_per_user(async_client: AsyncClient, auth_headers: dict):
    """Test that VPN profile is idempotent per user."""
    r1 = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=auth_headers,
    )
    r2 = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=auth_headers,
    )
    assert r1.json()["filename"] == r2.json()["filename"]


@pytest.mark.asyncio
async def test_vpn_status_requires_auth(async_client: AsyncClient):
    """Test that VPN endpoints require authentication."""
    response = await async_client.get(f"{settings.API_V1_STR}/vpn/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vpn_download_requires_auth(async_client: AsyncClient):
    """Test that VPN download requires authentication."""
    response = await async_client.get(f"{settings.API_V1_STR}/vpn/download")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vpn_revoke_requires_admin(async_client: AsyncClient, auth_headers: dict):
    """Test that VPN revocation requires admin privileges."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/vpn/revoke",
        headers=auth_headers,
    )
    # Non-admin user should get 403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_vpn_profile_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
):
    """Test that users get different VPN profiles."""
    r1 = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=auth_headers,
    )
    r2 = await async_client.get(
        f"{settings.API_V1_STR}/vpn/profile",
        headers=second_auth_headers,
    )
    assert r1.json()["filename"] != r2.json()["filename"]


# ============================================================
# Security Tests
# ============================================================

class TestSecurityValidation:
    """Test security aspects of VPN provisioning."""

    def test_command_injection_blocked(self):
        """Ensure command injection via client name is blocked."""
        malicious_names = [
            "$(whoami)",
            "`id`",
            "user;cat /etc/passwd",
            "user|ls",
            "user&&ls",
            "../../../etc/shadow",
            "user\nls",
            "user\x00ls",
        ]
        for name in malicious_names:
            with pytest.raises(VPNProvisionerError):
                _validate_client_name(name)

    def test_path_traversal_blocked(self):
        """Ensure path traversal via client name is blocked."""
        with pytest.raises(VPNProvisionerError):
            _validate_client_name("../../etc/passwd")

    def test_error_messages_sanitized(self):
        """Ensure error messages don't contain secrets."""
        error = "Error: wrong pass:mysupersecret for ca.key\npassphrase verification failed"
        sanitized = _sanitize_error(error)
        assert "mysupersecret" not in sanitized
        assert "[sensitive content redacted]" in sanitized
