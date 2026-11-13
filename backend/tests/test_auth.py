import pytest
from httpx import AsyncClient
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_get_me(async_client: AsyncClient, auth_headers: dict, test_user):
    """Test retrieving authenticated user profile."""
    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email


@pytest.mark.asyncio
async def test_expired_jwt_rejected(async_client: AsyncClient, test_user):
    """Test that expired JWT access tokens are rejected with 401."""
    from datetime import datetime, timedelta, timezone
    from backend.app.core.security import create_access_token

    # Generate token that expired 1 hour ago
    expired_token = create_access_token(
        subject=test_user.id,
        expires_delta=timedelta(hours=-1)
    )
    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "token" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_tampered_jwt_rejected(async_client: AsyncClient, auth_headers: dict):
    """Test that tampered or malformed JWT tokens are rejected."""
    # Malformed token
    res1 = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert res1.status_code == 401

    # Tampered signature
    valid_token = auth_headers["Authorization"].split(" ")[1]
    tampered_token = valid_token[:-4] + "XXXX"
    res2 = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_jwt_signed_with_different_key_rejected(async_client: AsyncClient, test_user):
    """Test that a token signed with an unknown or different key is rejected."""
    import jwt
    from datetime import datetime, timedelta, timezone

    fake_secret = "different-unauthorized-secret-key-32chars"
    token = jwt.encode(
        {"sub": test_user.id, "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        fake_secret,
        algorithm="HS256"
    )
    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["development", "testing", "production"])
@pytest.mark.parametrize("path", ["login", "register", "dev-login"])
async def test_non_otp_auth_unavailable(async_client, monkeypatch, environment, path):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/{path}",
        json={"email": "player@mirrage.io", "username_or_email": "operative_zero",
              "username": "operative_zero", "password": "CyberSecret2026!"},
    )
    assert response.status_code == 404
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_deactivated_account_token_rejected(async_client, db_session, test_user):
    from backend.app.core.security import create_access_token
    token = create_access_token(subject=test_user.id)
    test_user.is_active = False
    await db_session.commit()
    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
