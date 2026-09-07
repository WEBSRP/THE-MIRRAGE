import pytest
from httpx import AsyncClient
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    """Test successful user registration and initial VPN profile generation."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "archaeologist@mirrage.io",
            "username": "surveyor_99",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "archaeologist@mirrage.io"
    assert data["username"] == "surveyor_99"
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient, test_user):
    """Test registration failure when email already exists."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": test_user.email,
            "username": "another_user",
            "password": "Password123!",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "email" in data["message"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client: AsyncClient, test_user):
    """Test registration failure when username already exists."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "brand_new@mirrage.io",
            "username": test_user.username,
            "password": "Password123!",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "username" in data["message"].lower()


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Test user login with valid credentials."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "CyberSecret2026!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == test_user.username


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, test_user):
    """Test login failure with wrong password."""
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401


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
async def test_deactivated_account_login_and_token_rejected(
    async_client: AsyncClient, db_session, test_user
):
    """Test that deactivated accounts cannot log in or use existing tokens."""
    # 1. Login should succeed while active
    login_resp = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"username_or_email": test_user.username, "password": "CyberSecret2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 2. Deactivate user
    test_user.is_active = False
    await db_session.commit()

    # 3. Existing token must be rejected
    me_resp = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 401
    assert "disabled" in me_resp.json()["message"].lower() or "deactivated" in me_resp.json()["message"].lower()

    # 4. New login attempt must also be rejected
    login_resp2 = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"username_or_email": test_user.username, "password": "CyberSecret2026!"},
    )
    assert login_resp2.status_code == 401
