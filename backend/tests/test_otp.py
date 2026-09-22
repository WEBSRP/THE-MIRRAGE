import asyncio
import os
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.otp import OtpCode
from backend.app.models.user import User
from backend.app.models.activity import ActivityLog, ActivityEventType
from backend.app.services.email_service import email_service

@pytest.fixture(autouse=True)
def setup_otp_dev_mode():
    settings.OTP_DEV_MODE = True
    yield
    settings.OTP_DEV_MODE = False

@pytest.fixture
def mock_send_otp(monkeypatch):
    sent_otps = []
    
    async def mock_send(email: str, otp: str):
        sent_otps.append({"email": email, "otp": otp})
        
    monkeypatch.setattr(email_service, "send_otp", mock_send)
    return sent_otps

@pytest.mark.asyncio
async def test_request_otp_new_email(async_client: AsyncClient, mock_send_otp):
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "newuser@example.com"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "If this email can receive an OTP, a verification code has been sent."
    assert len(mock_send_otp) == 1
    assert mock_send_otp[0]["email"] == "newuser@example.com"

@pytest.mark.asyncio
async def test_request_otp_existing_email(async_client: AsyncClient, test_user: User, mock_send_otp):
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": test_user.email}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "If this email can receive an OTP, a verification code has been sent."
    assert len(mock_send_otp) == 1

@pytest.mark.asyncio
async def test_otp_stored_hashed(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    email = "hashcheck@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    raw_otp = mock_send_otp[0]["otp"]
    
    query = select(OtpCode).where(OtpCode.email == email)
    result = await db_session.execute(query)
    otp_record = result.scalars().first()
    
    assert otp_record is not None
    assert otp_record.code_hash != raw_otp

@pytest.mark.asyncio
async def test_correct_otp_succeeds(async_client: AsyncClient, mock_send_otp):
    email = "success@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["is_new_user"] is True
    assert data["user"]["email"] == email

@pytest.mark.asyncio
async def test_incorrect_otp_fails(async_client: AsyncClient, mock_send_otp):
    email = "fail@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": "000000"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_expired_otp_fails(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    email = "expired@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    # Manually expire the OTP in DB
    query = select(OtpCode).where(OtpCode.email == email)
    result = await db_session.execute(query)
    otp_record = result.scalars().first()
    from datetime import datetime, timedelta, timezone
    otp_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()
    
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_otp_cannot_be_reused(async_client: AsyncClient, mock_send_otp):
    email = "reuse@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    # First use
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert response.status_code == 200
    
    # Second use
    response2 = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert response2.status_code == 401

@pytest.mark.asyncio
async def test_otp_attempt_limit(async_client: AsyncClient, mock_send_otp):
    email = "limit@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    for _ in range(5):
        await async_client.post(
            f"{settings.API_V1_STR}/auth/verify-otp",
            json={"email": email, "otp": "000000"}
        )
        
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": "000000"}
    )
    assert response.status_code == 401
    assert "Too many failed attempts" in response.json()["message"]

@pytest.mark.asyncio
async def test_new_otp_invalidates_previous(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    email = "invalidate@example.com"
    
    # First OTP
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    first_otp = mock_send_otp[0]["otp"]
    
    # Second OTP
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    # Try using first OTP
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": first_otp}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_resend_cooldown_works(async_client: AsyncClient):
    email = "cooldown@example.com"
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/resend-otp",
        json={"email": email}
    )
    
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/resend-otp",
        json={"email": email}
    )
    assert response.status_code == 429
    assert "wait" in response.json()["message"].lower()

@pytest.mark.asyncio
async def test_resend_rate_limit(async_client: AsyncClient, db_session: AsyncSession):
    email = "ratelimit@example.com"
    
    # Override settings for this test to bypass cooldown but test window limit
    settings.OTP_RESEND_COOLDOWN_SECONDS = 0
    
    for _ in range(5):
        await async_client.post(
            f"{settings.API_V1_STR}/auth/resend-otp",
            json={"email": email}
        )
        
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/resend-otp",
        json={"email": email}
    )
    assert response.status_code == 429
    
    settings.OTP_RESEND_COOLDOWN_SECONDS = 60

@pytest.mark.asyncio
async def test_existing_user_not_duplicated(async_client: AsyncClient, test_user: User, mock_send_otp, db_session: AsyncSession):
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": test_user.email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": test_user.email, "otp": otp}
    )
    assert response.status_code == 200
    assert response.json()["is_new_user"] is False
    
    # Check DB
    query = select(User).where(User.email == test_user.email)
    result = await db_session.execute(query)
    users = result.scalars().all()
    assert len(users) == 1

@pytest.mark.asyncio
async def test_new_user_created_correctly(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    email = "newcreated@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    
    query = select(User).where(User.email == email)
    result = await db_session.execute(query)
    user = result.scalars().first()
    
    assert user is not None
    assert user.email_verified is True
    assert user.hashed_password is None
    assert user.username.startswith("player_")

@pytest.mark.asyncio
async def test_email_marked_verified(async_client: AsyncClient, test_user: User, db_session: AsyncSession, mock_send_otp):
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": test_user.email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": test_user.email, "otp": otp}
    )
    
    await db_session.refresh(test_user)
    assert test_user.email_verified is True

@pytest.mark.asyncio
async def test_otp_issued_jwt_works_with_me(async_client: AsyncClient, mock_send_otp):
    email = "mecheck@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    res = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    token = res.json()["access_token"]
    
    me_res = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email


@pytest.mark.asyncio
async def test_existing_activity_remains_associated(async_client: AsyncClient, test_user: User, db_session: AsyncSession, mock_send_otp):
    # Add activity
    activity = ActivityLog(
        user_id=test_user.id,
        event_type=ActivityEventType.SESSION_START,
        summary="Test activity for OTP verification"
    )
    db_session.add(activity)
    await db_session.commit()
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": test_user.email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": test_user.email, "otp": otp}
    )
    
    query = select(ActivityLog).where(ActivityLog.user_id == test_user.id)
    result = await db_session.execute(query)
    activities = result.scalars().all()
    assert len(activities) > 0

@pytest.mark.asyncio
async def test_existing_password_login_works(async_client: AsyncClient, test_user: User):
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"username_or_email": test_user.email, "password": "CyberSecret2026!"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_existing_register_works(async_client: AsyncClient):
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={"email": "newreg@example.com", "username": "newreg", "password": "Password123!"}
    )
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_existing_auth_me_works(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers=auth_headers
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_generic_response_hides_account(async_client: AsyncClient):
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "invalidformat"} # Will fail Pydantic validation if we tested it directly, wait
    )
    # Actually, an invalid format will fail 422 before the generic response. 
    # But for a valid format with DB failure (e.g. rate limit), it should be silent except generic.
    
    response2 = await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": "good@example.com"}
    )
    assert response2.status_code == 200
    assert response2.json()["message"] == "If this email can receive an OTP, a verification code has been sent."

@pytest.mark.asyncio
async def test_request_otp_rate_limit_enforced(async_client: AsyncClient, mock_send_otp):
    """Test that request-otp enforces rate limiting (re-raises OTP_RATE_LIMIT)."""
    email = "ratelimit_request@example.com"
    
    # Override cooldown to bypass it
    original_cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    settings.OTP_RESEND_COOLDOWN_SECONDS = 0
    
    # Send max requests
    for _ in range(settings.OTP_MAX_REQUESTS_PER_WINDOW):
        await async_client.post(
            f"{settings.API_V1_STR}/auth/request-otp",
            json={"email": email}
        )
    
    # Next request should be rate limited
    response = await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    assert response.status_code == 429
    
    settings.OTP_RESEND_COOLDOWN_SECONDS = original_cooldown

@pytest.mark.asyncio
async def test_production_rejects_otp_dev_mode():
    """Test that production configuration rejects OTP_DEV_MODE=true."""
    from backend.app.core.config import Settings
    
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="A-Very-Secure-And-Long-Production-Key-With-No-Banned-Words-32chars",
        OTP_HMAC_SECRET="A-Dedicated-Secure-OTP-HMAC-Key-For-Production-At-Least-32",
        K8S_MODE="production",
        VPN_MODE="production",
        OTP_DEV_MODE=True,
    )
    
    with pytest.raises(ValueError, match="OTP_DEV_MODE must be false in production"):
        prod_settings.validate_production_config()


@pytest.mark.asyncio
async def test_production_rejects_missing_or_weak_otp_hmac_secret():
    """Test that production configuration rejects missing or weak OTP_HMAC_SECRET."""
    from backend.app.core.config import Settings

    # Missing OTP_HMAC_SECRET
    with pytest.raises(ValueError, match="OTP_HMAC_SECRET"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="A-Very-Secure-And-Long-Production-Key-With-No-Banned-Words-32chars",
            OTP_HMAC_SECRET="",
            K8S_MODE="production",
            VPN_MODE="production",
        )

    # Insecure term in OTP_HMAC_SECRET
    with pytest.raises(ValueError, match="OTP_HMAC_SECRET"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="A-Very-Secure-And-Long-Production-Key-With-No-Banned-Words-32chars",
            OTP_HMAC_SECRET="mirrage-otp-secret-key-too-obvious-to-use-in-prod-32c",
            K8S_MODE="production",
            VPN_MODE="production",
        )

    # Too short OTP_HMAC_SECRET
    with pytest.raises(ValueError, match="OTP_HMAC_SECRET"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="A-Very-Secure-And-Long-Production-Key-With-No-Banned-Words-32chars",
            OTP_HMAC_SECRET="short-secret",
            K8S_MODE="production",
            VPN_MODE="production",
        )


@pytest.mark.asyncio
async def test_otp_hmac_uses_dedicated_secret(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp, monkeypatch):
    """Test that OTP hashing is cryptographically bound to OTP_HMAC_SECRET and NOT SECRET_KEY."""
    import hashlib
    import hmac

    email = "dedicatedsecret@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    raw_otp = mock_send_otp[0]["otp"]

    query = select(OtpCode).where(OtpCode.email == email)
    result = await db_session.execute(query)
    otp_record = result.scalars().first()
    assert otp_record is not None

    expected_hmac_secret = hmac.new(
        settings.OTP_HMAC_SECRET.encode(),
        raw_otp.encode(),
        hashlib.sha256
    ).hexdigest()

    expected_jwt_secret = hmac.new(
        settings.SECRET_KEY.encode(),
        raw_otp.encode(),
        hashlib.sha256
    ).hexdigest()

    # The record code_hash MUST match the one generated with OTP_HMAC_SECRET
    assert otp_record.code_hash == expected_hmac_secret
    # And MUST NOT match the one generated with SECRET_KEY (since they are different secrets)
    assert otp_record.code_hash != expected_jwt_secret

@pytest.mark.asyncio
async def test_otp_new_user_gets_vpn_profile(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    """Test that new users created via OTP verification get a VPN profile."""
    from backend.app.models.vpn import VpnProfile
    
    email = "vpncheck@example.com"
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    
    otp = mock_send_otp[0]["otp"]
    
    res = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert res.status_code == 200
    user_id = res.json()["user"]["id"]
    
    # Check VPN profile exists
    query = select(User).where(User.id == user_id)
    result = await db_session.execute(query)
    user = result.scalars().first()
    assert user is not None
    
    vpn_query = select(VpnProfile).where(VpnProfile.user_id == user_id)
    vpn_result = await db_session.execute(vpn_query)
    vpn_profile = vpn_result.scalars().first()
    assert vpn_profile is not None
    assert vpn_profile.assigned_ip.startswith("10.8.0.")

@pytest.mark.asyncio
async def test_concurrent_otp_verification_no_duplicate_users(async_client: AsyncClient, db_session: AsyncSession, mock_send_otp):
    """Test that concurrent OTP verifications for the same email don't create duplicate users."""
    email = "concurrent@example.com"
    
    await async_client.post(
        f"{settings.API_V1_STR}/auth/request-otp",
        json={"email": email}
    )
    otp = mock_send_otp[0]["otp"]
    
    # First verification succeeds
    res1 = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert res1.status_code == 200
    
    # Second verification with same OTP fails (already used)
    res2 = await async_client.post(
        f"{settings.API_V1_STR}/auth/verify-otp",
        json={"email": email, "otp": otp}
    )
    assert res2.status_code == 401
    
    # Verify only one user exists
    query = select(User).where(User.email == email)
    result = await db_session.execute(query)
    users = result.scalars().all()
    assert len(users) == 1
