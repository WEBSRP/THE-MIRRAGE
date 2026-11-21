from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.app.core.database import Base
from backend.app.models.user import User

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models.activity import ActivityLog
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.vpn import VpnCrlMaintenance, VpnProfile, VpnRevocation
from backend.app.services.session_service import session_service
from backend.app.services.vpn_revocation import VPNRevocationService, vpn_revocation_service


@pytest.fixture(autouse=True)
def no_real_background_db(monkeypatch):
    # API requests use the test fixture DB, not the app's production session factory.
    monkeypatch.setattr(vpn_revocation_service, "run_background", AsyncMock())


@pytest_asyncio.fixture
async def admin_headers(test_user, db_session):
    test_user.is_admin = True
    await db_session.commit()
    return {"Authorization": "Bearer " + create_access_token(test_user.id)}


async def profile_for(async_client, headers):
    response = await async_client.get("/api/v1/vpn/profile", headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_admin_revokes_selected_player_keeps_others_and_blocks_all_reentry(
    async_client, admin_headers, second_auth_headers, test_user, second_user, db_session
):
    await profile_for(async_client, second_auth_headers)
    other_profile = await profile_for(async_client, admin_headers)
    target_session = await async_client.post("/api/v1/session/start", headers=second_auth_headers)
    own_session = await async_client.post("/api/v1/session/start", headers=admin_headers)
    assert target_session.status_code == own_session.status_code == 201
    path = f"/api/v1/vpn/users/{second_user.id}/revoke"
    response = await async_client.post(path, headers=admin_headers)
    assert response.status_code == 202 and response.json()["status"] == "pending"
    assert response.json()["user_id"] == second_user.id
    assert response.headers["Cache-Control"] == "no-store"
    target_profile = (await db_session.execute(select(VpnProfile).where(
        VpnProfile.user_id == second_user.id
    ))).scalar_one()
    assert target_profile.revoked_at and target_profile.config_data == ""
    # Denial is effective before certificate/socket work succeeds.
    for endpoint in ("/api/v1/vpn/profile", "/api/v1/vpn/download"):
        denied = await async_client.get(endpoint, headers=second_auth_headers)
        assert denied.status_code == 403 and denied.json()["code"] == "VPN_REVOKED"
    denied = await async_client.post("/api/v1/session/start", headers=second_auth_headers)
    assert denied.status_code == 403
    denied = await async_client.post("/api/v1/session/extend", headers=second_auth_headers)
    assert denied.status_code == 403 and denied.json()["code"] == "VPN_REVOKED"
    await vpn_revocation_service.process_pending(db_session)
    status = await async_client.get(f"/api/v1/vpn/users/{second_user.id}/revocation", headers=admin_headers)
    assert status.json()["status"] == "completed"
    session = await db_session.get(GameSession, target_session.json()["session_id"])
    assert session.status == SessionStatus.TERMINATED and session.mirage_ip is None
    own = await db_session.get(GameSession, own_session.json()["session_id"])
    assert own.status == SessionStatus.READY
    assert (await profile_for(async_client, admin_headers))["filename"] == other_profile["filename"]
    repeated = await async_client.post(path, headers=admin_headers)
    assert repeated.status_code == 200 and repeated.json()["status"] == "completed"
    assert len((await db_session.execute(select(VpnRevocation))).scalars().all()) == 1
    events = (await db_session.execute(select(ActivityLog).where(
        ActivityLog.user_id == second_user.id
    ))).scalars().all()
    assert sum(bool(event.payload and event.payload.get("action") == "vpn_revocation_requested") for event in events) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_revoke_or_inspect_other_players_or_crl(
    async_client, auth_headers, second_user
):
    for method, path in (
        ("post", f"/api/v1/vpn/users/{second_user.id}/revoke"),
        ("get", f"/api/v1/vpn/users/{second_user.id}/revocation"),
        ("get", "/api/v1/vpn/crl-health"),
    ):
        assert (await getattr(async_client, method)(path, headers=auth_headers)).status_code == 403


@pytest.mark.asyncio
async def test_missing_profile_is_not_claimed_revoked(async_client, admin_headers, second_user):
    response = await async_client.post(f"/api/v1/vpn/users/{second_user.id}/revoke", headers=admin_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_production_failure_is_durable_retryable_and_never_exposes_error_output(
    async_client, admin_headers, second_auth_headers, second_user, db_session, monkeypatch
):
    await profile_for(async_client, second_auth_headers)
    await vpn_revocation_service.request(db_session, second_user.id, second_user.id)
    job = await vpn_revocation_service.get(db_session, second_user.id)
    fake = SimpleNamespace(block=AsyncMock(), publish=AsyncMock(side_effect=RuntimeError("private-pki-value")))
    monkeypatch.setattr(import_module("backend.app.services.vpn_control"), "vpn_control", fake)
    revoke = AsyncMock()
    monkeypatch.setattr(import_module("backend.app.services.vpn_provisioner"), "revoke_client_certificate", revoke)
    monkeypatch.setattr(settings, "VPN_MODE", "production")
    assert not await vpn_revocation_service.process_one(db_session, job.client_name)
    await db_session.refresh(job)
    assert job.completed_at is None and job.last_error == "CRL_PUBLISH_FAILED" and job.attempts == 1
    response = await async_client.get(f"/api/v1/vpn/users/{second_user.id}/revocation", headers=admin_headers)
    assert response.json()["status"] == "pending" and "private-pki-value" not in response.text
    fake.publish.side_effect = None
    job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert await vpn_revocation_service.process_one(db_session, job.client_name)
    await db_session.refresh(job)
    assert job.completed_at and job.last_error is None and job.attempts == 2
    assert fake.block.await_count == 3  # Initial failed publish, then pre/post publication retry.
    assert revoke.await_count == 2


@pytest.mark.asyncio
async def test_interrupted_worker_claim_can_be_reclaimed(db_session, test_user, async_client, auth_headers):
    await profile_for(async_client, auth_headers)
    job = await vpn_revocation_service.request(db_session, test_user.id, test_user.id)
    job.claim_token = "interrupted-worker"
    job.claimed_until = datetime.now(timezone.utc) + timedelta(seconds=60)
    await db_session.commit()
    assert not await vpn_revocation_service.process_one(db_session, job.client_name)
    job.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert await VPNRevocationService().process_one(db_session, job.client_name)


@pytest.mark.asyncio
async def test_public_certificate_only_survives_profile_scrubbing(db_session, test_user):
    public = "-----BEGIN CERTIFICATE-----\nTESTPUBLIC\n-----END CERTIFICATE-----"
    profile = VpnProfile(user_id=test_user.id, client_name="public-test", config_data=(
        f"<cert>bag attributes\n{public}</cert><key>NEVER-KEEP-THIS-KEY</key>"
    ))
    db_session.add(profile)
    await db_session.commit()
    job = await vpn_revocation_service.request(db_session, test_user.id, test_user.id)
    assert job.certificate_pem == public and "KEY" not in job.certificate_pem
    assert profile.config_data == ""
    # The deny survives profile deletion; it cannot be regenerated implicitly.
    await db_session.delete(profile)
    await db_session.commit()
    from backend.app.services.vpn_service import MockVPNService
    with pytest.raises(Exception) as error:
        await MockVPNService().generate_or_get_profile(db_session, test_user)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_failed_session_cleanup_keeps_revocation_pending_and_retries(
    async_client, auth_headers, test_user, db_session, monkeypatch
):
    await profile_for(async_client, auth_headers)
    job = await vpn_revocation_service.request(db_session, test_user.id, test_user.id)
    monkeypatch.setattr(vpn_revocation_service, "close_sessions", AsyncMock(return_value=False))
    assert not await vpn_revocation_service.process_one(db_session, job.client_name)
    await db_session.refresh(job)
    assert job.last_error == "SESSION_CLEANUP_PENDING" and not job.completed_at


@pytest.mark.asyncio
async def test_crl_maintenance_refreshes_only_near_expiry_and_persists_health(db_session, monkeypatch):
    monkeypatch.setattr(settings, "VPN_MODE", "production")
    now = datetime.now(timezone.utc)
    healthy = int((now + timedelta(days=30)).timestamp())
    fake = SimpleNamespace(health=AsyncMock(return_value={"expires_at": int(now.timestamp()) + 100}),
                           refresh=AsyncMock(return_value={"expires_at": healthy}))
    renew = AsyncMock()
    monkeypatch.setattr(import_module("backend.app.services.vpn_control"), "vpn_control", fake)
    monkeypatch.setattr(import_module("backend.app.services.vpn_provisioner"), "refresh_certificate_revocation_list", renew)
    await vpn_revocation_service.maintain_crl(db_session)
    state = await db_session.get(VpnCrlMaintenance, 1)
    assert state.checked_at and state.expires_at and state.last_error is None
    renew.assert_awaited_once()
    await vpn_revocation_service.maintain_crl(db_session)
    assert fake.health.await_count == 1  # A second worker/check respects the durable schedule.
    state.next_check_at = now - timedelta(seconds=1)
    await db_session.commit()
    fake.health.return_value = {"expires_at": healthy}
    await vpn_revocation_service.maintain_crl(db_session)
    assert renew.await_count == 1


@pytest.mark.asyncio
async def test_crl_maintenance_failure_is_visible_without_claiming_success(db_session, monkeypatch):
    monkeypatch.setattr(settings, "VPN_MODE", "production")
    fake = SimpleNamespace(health=AsyncMock(side_effect=RuntimeError("unavailable")),
                           refresh=AsyncMock(side_effect=RuntimeError("unavailable")))
    monkeypatch.setattr(import_module("backend.app.services.vpn_control"), "vpn_control", fake)
    monkeypatch.setattr(import_module("backend.app.services.vpn_provisioner"),
                        "refresh_certificate_revocation_list", AsyncMock(side_effect=RuntimeError("private-error")))
    await vpn_revocation_service.maintain_crl(db_session)
    state = await db_session.get(VpnCrlMaintenance, 1)
    assert state.last_error == "CRL_MAINTENANCE_FAILED" and state.expires_at is None


@pytest.mark.asyncio
async def test_postgres_independent_workers_claim_once_and_tombstone_blocks_grants():
    url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requires disposable PostgreSQL")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        unique = uuid.uuid4().hex
        async with sessions() as db:
            user = User(email=f"{unique}@example.com", username=unique)
            db.add(user)
            await db.flush()
            user_id = user.id
            client = "claim-" + unique
            db.add(VpnProfile(user_id=user_id, client_name=client, config_data="disposable"))
            await db.commit()
            await VPNRevocationService().request(db, user_id, user_id)

        calls = []
        async def close_sessions(db, target):
            calls.append(target)
            await asyncio.sleep(0.1)
            return True
        async def process():
            service = VPNRevocationService()
            service.close_sessions = close_sessions
            async with sessions() as db:
                return await service.process_one(db, client)
        results = await asyncio.gather(*(process() for _ in range(5)))
        assert sum(results) == 1 and calls == [user_id]

        # Once revocation commits, later grants observe the tombstone.
        from backend.app.services.vpn_access import require_vpn_access
        from backend.app.core.exceptions import MirrageException
        async with sessions() as db:
            with pytest.raises(MirrageException) as error:
                await require_vpn_access(db, user_id, lock=True)
            assert error.value.status_code == 403
    finally:
        await engine.dispose()
