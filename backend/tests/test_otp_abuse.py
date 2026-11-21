import asyncio
from importlib import import_module
import os
from unittest.mock import AsyncMock
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from backend.app.core.client_address import otp_client_address
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.exceptions import MirrageException
from backend.app.models.otp import OtpCode
from backend.app.models.otp_abuse import OtpAbuseBucket
from backend.app.services.email_health import EmailHealth
from backend.app.services.auth_service import AuthService
from backend.app.services.otp_abuse import OtpAbuseLimiter, ip_bucket_key

abuse_module = import_module("backend.app.services.otp_abuse")
auth_module = import_module("backend.app.services.auth_service")


@pytest_asyncio.fixture(params=["sqlite", "postgresql"])
async def abuse_db(request, tmp_path, monkeypatch):
    admin = None
    if request.param == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Requires disposable PostgreSQL")
        admin = create_async_engine(url)
        schema = "abuse_" + uuid.uuid4().hex
        async with admin.begin() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'abuse.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    send = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", send)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine, sessions, send
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


async def send(context, email, ip="198.51.100.20", resend=False):
    async with context[1]() as db:
        service = AuthService()  # Independent worker instance and connection.
        return await (service.resend_otp(db, email, client_address=ip) if resend else
                      service.request_otp(db, email, client_address=ip))


async def counters(context):
    async with context[1]() as db:
        return {row.key: row for row in (await db.execute(sa.select(OtpAbuseBucket))).scalars()}


@pytest.mark.asyncio
async def test_ip_budget_survives_concurrent_workers_and_many_emails(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 3)
    results = await asyncio.gather(*(send(abuse_db, f"player{i}@example.com") for i in range(8)),
                                   return_exceptions=True)
    assert sum(isinstance(result, int) for result in results) == 3
    errors = [result for result in results if isinstance(result, MirrageException)]
    assert len(errors) == 5 and all(error.code == "OTP_IP_RATE_LIMIT" for error in errors)
    assert all(0 < int(error.headers["Retry-After"]) <= settings.OTP_IP_WINDOW_SECONDS for error in errors)
    assert abuse_db[2].await_count == 3
    # A new service instance cannot reset a shared persistent bucket.
    with pytest.raises(MirrageException) as limited:
        await send(abuse_db, "fresh-worker@example.com")
    assert limited.value.code == "OTP_IP_RATE_LIMIT"
    stored = await counters(abuse_db)
    assert stored[ip_bucket_key("198.51.100.20")].attempts == 3
    assert all("198.51.100.20" not in key for key in stored)


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", ["hour", "day"])
async def test_global_budget_caps_many_sources_and_addresses_atomically(abuse_db, monkeypatch, budget):
    monkeypatch.setattr(settings, "OTP_EMAIL_HOURLY_LIMIT", 3 if budget == "hour" else 100)
    monkeypatch.setattr(settings, "OTP_EMAIL_DAILY_LIMIT", 3 if budget == "day" else 100)
    results = await asyncio.gather(*(send(abuse_db, f"global{i}@example.com", f"198.51.100.{i + 1}")
                                     for i in range(8)), return_exceptions=True)
    assert sum(isinstance(result, int) for result in results) == 3
    errors = [result for result in results if isinstance(result, MirrageException)]
    assert len(errors) == 5 and all(error.code == "OTP_EMAIL_BUDGET" for error in errors)
    assert abuse_db[2].await_count == 3
    stored = await counters(abuse_db)
    # An hourly reservation preceding a failed daily reservation must roll back.
    assert stored["global:hour"].attempts == stored["global:day"].attempts == 3
    async with abuse_db[1]() as db:
        assert (await db.execute(sa.select(sa.func.count()).select_from(OtpCode))).scalar_one() == 3
        report = await EmailHealth().report(db, "unconfigured")
        assert report["attempted"] == report["simulated"] == 3
        assert report["accepted"] == report["unknown"] == report["pending"] == 0


@pytest.mark.asyncio
async def test_email_cooldown_counts_ip_requests_but_not_global_sends(abuse_db):
    await send(abuse_db, "cooldown@example.com")
    with pytest.raises(MirrageException) as error:
        await send(abuse_db, "cooldown@example.com")
    assert error.value.code == "OTP_COOLDOWN"
    stored = await counters(abuse_db)
    assert stored[ip_bucket_key("198.51.100.20")].attempts == 2
    assert stored["global:hour"].attempts == stored["global:day"].attempts == 1


@pytest.mark.asyncio
async def test_resend_and_request_share_ip_and_global_budgets(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 2)
    await send(abuse_db, "resend@example.com")
    await send(abuse_db, "resend@example.com", resend=True)
    with pytest.raises(MirrageException) as error:
        await send(abuse_db, "other@example.com")
    assert error.value.code == "OTP_IP_RATE_LIMIT" and abuse_db[2].await_count == 2


@pytest.mark.asyncio
async def test_failed_delivery_still_uses_budget_without_refund(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_EMAIL_HOURLY_LIMIT", 1)
    abuse_db[2].side_effect = RuntimeError("provider unavailable")
    with pytest.raises(MirrageException) as failure:
        await send(abuse_db, "failure@example.com")
    assert failure.value.code == "OTP_EMAIL_UNAVAILABLE"
    with pytest.raises(MirrageException) as error:
        await send(abuse_db, "retry@example.com", "198.51.100.21")
    assert error.value.code == "OTP_EMAIL_BUDGET" and abuse_db[2].await_count == 1


@pytest.mark.asyncio
async def test_budget_rejected_resend_does_not_invalidate_previous_code(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_EMAIL_HOURLY_LIMIT", 1)
    await send(abuse_db, "keep@example.com")
    async with abuse_db[1]() as db:
        original = (await db.execute(sa.select(OtpCode))).scalar_one()
        original_id = original.id
    with pytest.raises(MirrageException) as error:
        await send(abuse_db, "keep@example.com", resend=True)
    assert error.value.code == "OTP_EMAIL_BUDGET"
    async with abuse_db[1]() as db:
        assert not (await db.get(OtpCode, original_id)).is_used
        assert (await db.execute(sa.select(sa.func.count()).select_from(OtpCode))).scalar_one() == 1


@pytest.mark.asyncio
async def test_fixed_windows_reset_forward_but_stale_requests_cannot_reset_back(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 1)
    monkeypatch.setattr(settings, "OTP_IP_WINDOW_SECONDS", 10)
    clock = AsyncMock(return_value=100.0)
    monkeypatch.setattr(abuse_module, "database_time", clock)
    async with abuse_db[1]() as db:
        await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
        with pytest.raises(MirrageException):
            await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
        clock.return_value = 110.0
        await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
        clock.return_value = 100.0
        with pytest.raises(MirrageException):
            await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
    stored = await counters(abuse_db)
    assert stored[ip_bucket_key("198.51.100.20")].window == 11
    assert stored[ip_bucket_key("198.51.100.20")].attempts == 1


@pytest.mark.asyncio
async def test_changed_ip_window_duration_uses_a_distinct_bucket(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 1)
    monkeypatch.setattr(settings, "OTP_IP_WINDOW_SECONDS", 10)
    monkeypatch.setattr(abuse_module, "database_time", AsyncMock(return_value=100.0))
    old_key = ip_bucket_key("198.51.100.20")
    async with abuse_db[1]() as db:
        await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
        monkeypatch.setattr(settings, "OTP_IP_WINDOW_SECONDS", 20)
        await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
        with pytest.raises(MirrageException):
            await OtpAbuseLimiter().consume_ip(db, "198.51.100.20")
    assert old_key != ip_bucket_key("198.51.100.20")
    assert len(await counters(abuse_db)) == 2


@pytest.mark.asyncio
async def test_cleanup_removes_only_stale_ip_buckets(abuse_db, monkeypatch):
    monkeypatch.setattr(settings, "OTP_IP_BUCKET_RETENTION_SECONDS", 10)
    monkeypatch.setattr(abuse_module, "database_time", AsyncMock(return_value=100.0))
    async with abuse_db[1]() as db:
        db.add_all([OtpAbuseBucket(key=key, window=1, attempts=1, expires_at=expiry) for key, expiry in
                    (("ip:stale", 89), ("ip:current", 91), ("global:day", 1))])
        await db.commit()
        await OtpAbuseLimiter().cleanup(db)
    assert set(await counters(abuse_db)) == {"ip:current", "global:day"}


@pytest.mark.asyncio
async def test_database_failure_fails_closed_and_exposes_no_driver_output(abuse_db, monkeypatch):
    async with abuse_db[1]() as db:
        monkeypatch.setattr(db, "execute", AsyncMock(side_effect=SQLAlchemyError("private diagnostic")))
        with pytest.raises(MirrageException) as error:
            await AuthService().request_otp(db, "none@example.com", client_address="198.51.100.20")
        assert error.value.status_code == 503 and "private" not in error.value.detail
    abuse_db[2].assert_not_awaited()


def request(peer="198.51.100.20", headers=()):
    return Request({"type": "http", "client": (peer, 12345), "headers": headers})


def test_untrusted_peer_cannot_choose_an_identity_with_any_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, "OTP_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    headers = [(name, b"203.0.113.10") for name in
               (b"x-forwarded-for", b"cf-connecting-ip", b"x-real-ip", b"x-mirrage-client-ip")]
    assert otp_client_address(request(headers=headers)) == "198.51.100.20"


@pytest.mark.parametrize("headers", [[], [(b"x-mirrage-client-ip", b"not-an-ip")],
    [(b"x-mirrage-client-ip", b"198.51.100.1, 203.0.113.1")],
    [(b"x-mirrage-client-ip", b"198.51.100.1"), (b"x-mirrage-client-ip", b"203.0.113.1")],
    [(b"x-mirrage-client-ip", b"fe80::1%eth0")]])
def test_trusted_proxy_requires_exactly_one_literal_ip(monkeypatch, headers):
    monkeypatch.setattr(settings, "OTP_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    with pytest.raises(MirrageException) as error:
        otp_client_address(request("127.0.0.1", headers))
    assert error.value.status_code == 503


def test_proxy_header_and_ipv4_mapped_addresses_are_canonicalized(monkeypatch):
    monkeypatch.setattr(settings, "OTP_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    assert otp_client_address(request("::ffff:127.0.0.1", [(b"x-mirrage-client-ip", b"::ffff:198.51.100.1")])) == "198.51.100.1"
    assert ip_bucket_key("::ffff:198.51.100.1") == ip_bucket_key("198.51.100.1")
    assert ip_bucket_key("2001:db8:1:2::1") == ip_bucket_key("2001:db8:1:2::fffe")
    assert ip_bucket_key("2001:db8:1:3::1") != ip_bucket_key("2001:db8:1:2::1")


@pytest.mark.parametrize("networks", [["0.0.0.0/0"], ["::/0"], ["invalid"]])
def test_configuration_rejects_wildcard_or_invalid_proxy_trust(networks):
    from backend.app.core.config import Settings
    with pytest.raises(ValueError):
        Settings(_env_file=None, ENVIRONMENT="testing", SECRET_KEY="unit-test-key",
                 OTP_TRUSTED_PROXY_CIDRS=networks)


@pytest.mark.asyncio
async def test_both_public_send_routes_enforce_ip_limit_and_ignore_spoofing(async_client, monkeypatch):
    monkeypatch.setattr(settings, "OTP_TRUSTED_PROXY_CIDRS", [])
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 2)
    delivery = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", delivery)
    for path in ("request-otp", "resend-otp"):
        response = await async_client.post(f"/api/v1/auth/{path}", json={"email": "public@example.com"},
            headers={"X-Mirrage-Client-IP": "203.0.113.1", "X-Forwarded-For": "203.0.113.2"})
        assert response.status_code == 200
    blocked = await async_client.post("/api/v1/auth/request-otp", json={"email": "other@example.com"},
                                      headers={"X-Mirrage-Client-IP": "192.0.2.10"})
    assert blocked.status_code == 429 and blocked.json()["code"] == "OTP_IP_RATE_LIMIT"
    assert int(blocked.headers["Retry-After"]) > 0 and delivery.await_count == 2


@pytest.mark.asyncio
async def test_trusted_proxy_routes_separate_visitors_and_reject_missing_identity(db_session, monkeypatch):
    from backend.app.main import app
    from backend.app.core.database import get_db
    monkeypatch.setattr(settings, "OTP_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    monkeypatch.setattr(settings, "OTP_IP_REQUEST_LIMIT", 1)
    delivery = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", delivery)
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app, client=("127.0.0.1", 123)), base_url="http://test") as http:
            for i in (1, 2):
                response = await http.post("/api/v1/auth/request-otp", json={"email": f"visitor{i}@example.com"},
                                           headers={"X-Mirrage-Client-IP": f"198.51.100.{i}"})
                assert response.status_code == 200
            response = await http.post("/api/v1/auth/request-otp", json={"email": "missing@example.com"})
            assert response.status_code == 503 and delivery.await_count == 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_global_budget_returns_429_for_new_requests_and_resends(async_client, monkeypatch):
    monkeypatch.setattr(settings, "OTP_EMAIL_HOURLY_LIMIT", 1)
    delivery = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", delivery)
    assert (await async_client.post("/api/v1/auth/request-otp", json={"email": "one@example.com"})).status_code == 200
    for path, email in (("resend-otp", "one@example.com"), ("request-otp", "two@example.com")):
        blocked = await async_client.post(f"/api/v1/auth/{path}", json={"email": email})
        assert blocked.status_code == 429 and blocked.json()["code"] == "OTP_EMAIL_BUDGET"
        assert int(blocked.headers["Retry-After"]) > 0
    delivery.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_counter_outage_returns_generic_503_and_sends_nothing(async_client, monkeypatch):
    delivery = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", delivery)
    monkeypatch.setattr(abuse_module, "database_time", AsyncMock(side_effect=SQLAlchemyError("private-driver-value")))
    response = await async_client.post("/api/v1/auth/request-otp", json={"email": "outage@example.com"})
    assert response.status_code == 503 and response.json()["code"] == "OTP_THROTTLE_UNAVAILABLE"
    assert "private-driver-value" not in response.text
    delivery.assert_not_awaited()
