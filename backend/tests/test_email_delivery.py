import asyncio
from datetime import datetime, timedelta, timezone
from importlib import import_module
import json
import logging
from unittest.mock import AsyncMock

import httpx
import pytest
import sqlalchemy as sa

from backend.app.core.config import Settings, settings
from backend.app.core.exceptions import MirrageException
from backend.app.core.security import create_access_token
from backend.app.models.email_delivery import EmailDeliveryAttempt
from backend.app.services.auth_service import AuthService
from backend.app.services.email_health import EmailHealth, email_health
from backend.app.services.email_service import EmailDeliveryError, EmailDispatchResult, EmailService

auth_module = import_module("backend.app.services.auth_service")
health_module = import_module("backend.app.services.email_health")


@pytest.fixture
def provider_config(monkeypatch):
    for key, value in dict(ENVIRONMENT="development", OTP_DEV_MODE=False, EMAIL_PROVIDER="resend",
                           EMAIL_API_KEY="dummy-provider-key", EMAIL_FROM="sender@example.com",
                           EMAIL_FROM_NAME="MIRRAGE", EMAIL_REPLY_TO="reply@example.com").items():
        monkeypatch.setattr(settings, key, value)


def prod_settings(**values):
    # Dummy strong-format values exercise production validation without live config.
    defaults = dict(_env_file=None, ENVIRONMENT="production",
        SECRET_KEY="Jw8Mr2Rx6Ck9Zp4Vs7Nt3Ha5Ld1Fq0Eu8Bv6",
        OTP_HMAC_SECRET="Qy4Wn8Ms2Fa7Rt9Lp5Vz1Jd6Ec3Kh0Gb4Xu8",
        K8S_MODE="mock", VPN_MODE="mock", ALLOW_MOCK_IN_PRODUCTION=True,
        EMAIL_PROVIDER="resend", EMAIL_API_KEY="dummy-provider-key", EMAIL_FROM="sender@example.com")
    defaults.update(values)
    return Settings(**defaults)


@pytest.mark.parametrize("values,code", [
    ({"EMAIL_PROVIDER": ""}, "EMAIL_PROVIDER_UNSUPPORTED"),
    ({"EMAIL_PROVIDER": "smtp"}, "EMAIL_PROVIDER_UNSUPPORTED"),
    ({"EMAIL_PROVIDER": "unknown"}, "EMAIL_PROVIDER_UNSUPPORTED"),
    ({"EMAIL_API_KEY": ""}, "EMAIL_API_KEY_INVALID"),
    ({"EMAIL_API_KEY": "sensitive value\r\nX-Key: bad"}, "EMAIL_API_KEY_INVALID"),
    ({"EMAIL_FROM": ""}, "EMAIL_FROM_INVALID"),
    ({"EMAIL_FROM": "not-email"}, "EMAIL_FROM_INVALID"),
    ({"EMAIL_FROM": "sender@example.com\r\nBcc: other@example.com"}, "EMAIL_FROM_INVALID"),
    ({"EMAIL_REPLY_TO": "not-email"}, "EMAIL_REPLY_TO_INVALID"),
    ({"EMAIL_FROM_NAME": "MIRRAGE\r\nX-Header: bad"}, "EMAIL_FROM_NAME_INVALID"),
])
def test_production_rejects_bad_configuration_without_exposing_values(values, code):
    with pytest.raises(ValueError) as error:
        prod_settings(**values).validate_production_config()
    assert code in str(error.value) and "sensitive value" not in str(error.value)


@pytest.mark.parametrize("provider", ["resend", "sendgrid"])
def test_supported_configuration_is_validated_without_network(provider):
    prod_settings(EMAIL_PROVIDER=provider).validate_production_config()


@pytest.mark.asyncio
async def test_bad_email_config_blocks_production_startup_before_any_external_work(monkeypatch):
    main = import_module("backend.app.main")
    monkeypatch.setattr(main, "settings", prod_settings(EMAIL_PROVIDER="smtp"))
    flags = AsyncMock()
    database = AsyncMock()
    monkeypatch.setattr(main, "get_shared_flags", flags)
    monkeypatch.setattr(main, "init_db", database)
    with pytest.raises(ValueError, match="EMAIL_PROVIDER_UNSUPPORTED"):
        async with main.app.router.lifespan_context(main.app):
            pass
    flags.assert_not_called()
    database.assert_not_awaited()


@pytest.mark.parametrize("value", [0, -1, 61, float("inf"), float("nan")])
def test_provider_timeout_must_be_bounded(value):
    with pytest.raises(ValueError):
        prod_settings(EMAIL_TIMEOUT_SECONDS=value)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,status", [("resend", 200), ("sendgrid", 202)])
async def test_provider_acceptance_payload_and_logs_are_safe(provider_config, monkeypatch, caplog, provider, status):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", provider)
    monkeypatch.setattr(settings, "OTP_EXPIRY_MINUTES", 3)
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={"id": "dummy-receipt"})
    with caplog.at_level(logging.INFO):
        result = await EmailService(httpx.MockTransport(handler)).send_otp("recipient@example.com", "918273")
    assert result.outcome == "accepted" and result.http_status == status and len(seen) == 1
    request = seen[0]
    payload = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer dummy-provider-key"
    assert request.url.host == ("api.resend.com" if provider == "resend" else "api.sendgrid.com")
    assert "3 minutes" in str(payload) and "918273" in str(payload)
    if provider == "resend":
        assert payload["from"] == "MIRRAGE <sender@example.com>" and payload["reply_to"] == "reply@example.com"
    else:
        assert payload["from"]["email"] == "sender@example.com" and payload["reply_to"]["email"] == "reply@example.com"
    for private in ("918273", "dummy-provider-key", "recipient@example.com", "dummy-receipt"):
        assert private not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500, 503])
async def test_provider_rejection_has_no_body_leak_or_automatic_retry(provider_config, caplog, status):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, text="private-provider-payload", headers={"Location": "https://untrusted.invalid/"})
    with pytest.raises(EmailDeliveryError) as error:
        await EmailService(httpx.MockTransport(handler)).send_otp("recipient@example.com", "918273")
    assert error.value.code == "PROVIDER_REJECTED" and len(seen) == 1
    assert error.value.outcome == ("unknown" if status >= 500 else "failed")
    assert "private-provider-payload" not in str(error.value) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout, "PROVIDER_TIMEOUT"),
                                         (httpx.ConnectError, "PROVIDER_NETWORK_ERROR")])
async def test_transport_error_is_ambiguous_and_sanitized(provider_config, failure, code):
    def handler(request):
        raise failure("private transport diagnostic", request=request)
    with pytest.raises(EmailDeliveryError) as error:
        await EmailService(httpx.MockTransport(handler)).send_otp("recipient@example.com", "918273")
    assert error.value.code == code and error.value.outcome == "unknown"
    assert "private" not in str(error.value)


@pytest.mark.asyncio
async def test_wall_clock_timeout_bounds_slow_provider(provider_config, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_TIMEOUT_SECONDS", 0.02)
    async def handler(request):
        await asyncio.sleep(30)
    with pytest.raises(EmailDeliveryError) as error:
        await asyncio.wait_for(EmailService(httpx.MockTransport(handler)).send_otp("recipient@example.com", "918273"), 1)
    assert error.value.code == "PROVIDER_TIMEOUT"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"id": ""}, {"id": 1}, ["receipt"]])
async def test_resend_requires_acceptance_receipt(provider_config, payload):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(EmailDeliveryError) as error:
        await EmailService(transport).send_otp("recipient@example.com", "918273")
    assert error.value.code == "PROVIDER_RESPONSE_INVALID" and error.value.outcome == "unknown"


@pytest.mark.asyncio
async def test_test_mode_is_simulation_without_provider_io(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "testing")
    def forbidden(request):
        raise AssertionError("Test bypass contacted a provider")
    assert (await EmailService(httpx.MockTransport(forbidden)).send_otp("recipient@example.com", "918273")).outcome == "simulated"


@pytest.mark.asyncio
async def test_smtp_fails_explicitly_instead_of_preparing_unsent_message(provider_config, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    with pytest.raises(EmailDeliveryError) as error:
        await EmailService(httpx.MockTransport(lambda request: None)).send_otp("recipient@example.com", "918273")
    assert error.value.code == "EMAIL_PROVIDER_UNSUPPORTED"


@pytest.mark.asyncio
async def test_api_failure_is_503_with_safe_durable_health(async_client, db_session, provider_config, monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="private-response-key-and-otp"))
    monkeypatch.setattr(auth_module, "email_service", EmailService(transport))
    response = await async_client.post("/api/v1/auth/request-otp", json={"email": "recipient@example.com"})
    assert response.status_code == 503 and response.json()["code"] == "OTP_EMAIL_UNAVAILABLE"
    assert "private-response" not in response.text
    record = (await db_session.execute(sa.select(EmailDeliveryAttempt))).scalar_one()
    assert record.outcome == "failed" and record.error_code == "PROVIDER_REJECTED" and record.http_status == 401
    assert "recipient@example.com" not in str(record.__dict__)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["request-otp", "resend-otp"])
async def test_unexpected_issue_failures_never_report_success(async_client, monkeypatch, path):
    operation = "request_otp" if path == "request-otp" else "resend_otp"
    monkeypatch.setattr(auth_module.auth_service, operation, AsyncMock(side_effect=MirrageException(
        503, "private unexpected diagnostic", "OTP_GENERATION_FAILED")))
    response = await async_client.post(f"/api/v1/auth/{path}", json={"email": "recipient@example.com"})
    assert response.status_code == 503 and response.json()["code"] == "OTP_EMAIL_UNAVAILABLE"
    assert "private unexpected diagnostic" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [None, EmailDispatchResult("simulated")])
async def test_live_dispatch_requires_real_acceptance_not_simulation(db_session, provider_config, monkeypatch, result):
    monkeypatch.setattr(auth_module.email_service, "send_otp", AsyncMock(return_value=result))
    with pytest.raises(MirrageException) as error:
        await AuthService().request_otp(db_session, "no-false-success@example.com")
    assert error.value.code == "OTP_EMAIL_UNAVAILABLE"
    record = (await db_session.execute(sa.select(EmailDeliveryAttempt))).scalar_one()
    assert record.outcome == "unknown" and record.error_code == "PROVIDER_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_acceptance_is_visible_only_to_admin_and_is_not_mailbox_delivery(
    async_client, db_session, test_user, auth_headers, provider_config, monkeypatch
):
    monkeypatch.setattr(auth_module, "email_service", EmailService(httpx.MockTransport(
        lambda request: httpx.Response(200, json={"id": "dummy-receipt"}))))
    assert (await async_client.get("/api/v1/health/email")).status_code == 401
    assert (await async_client.get("/api/v1/health/email", headers=auth_headers)).status_code == 403
    assert (await async_client.post("/api/v1/auth/request-otp", json={"email": "recipient@example.com"})).status_code == 200
    test_user.is_admin = True
    await db_session.commit()
    admin = {"Authorization": "Bearer " + create_access_token(test_user.id)}
    response = await async_client.get("/api/v1/health/email", headers=admin)
    data = response.json()
    assert data["status"] == "accepting" and data["accepted"] == 1 and data["configuration"] == "ready"
    assert data["mailbox_delivery_confirmed"] is False and response.headers["Cache-Control"] == "no-store"
    for private in ("recipient@example.com", "dummy-provider-key", "dummy-receipt"):
        assert private not in response.text


@pytest.mark.asyncio
async def test_cancelled_dispatch_retains_pending_intent_then_reports_unknown(db_session, provider_config, monkeypatch):
    entered = asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(auth_module, "email_service", EmailService(httpx.MockTransport(handler)))
    task = asyncio.create_task(AuthService().request_otp(db_session, "cancelled@example.com"))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = (await db_session.execute(sa.select(EmailDeliveryAttempt))).scalar_one()
    assert record.outcome == "pending"
    record.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    await db_session.commit()
    report = await EmailHealth().report(db_session, "resend")
    assert report["unknown"] == 1 and report["status"] == "degraded" and report["accepted"] == 0


@pytest.mark.asyncio
async def test_health_db_failure_before_send_prevents_provider_call(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(auth_module.email_service, "send_otp", sender)
    monkeypatch.setattr(email_health, "begin", AsyncMock(side_effect=RuntimeError("private database error")))
    with pytest.raises(MirrageException) as error:
        await AuthService().request_otp(db_session, "nosend@example.com")
    assert error.value.code == "OTP_EMAIL_UNAVAILABLE" and "private" not in error.value.detail
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_finish_failure_does_not_claim_success_or_resend(db_session, monkeypatch):
    sender = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_module.email_service, "send_otp", sender)
    monkeypatch.setattr(email_health, "finish", AsyncMock(side_effect=RuntimeError("private db error")))
    with pytest.raises(MirrageException):
        await AuthService().request_otp(db_session, "ambiguous@example.com")
    sender.assert_awaited_once()
    assert (await db_session.execute(sa.select(EmailDeliveryAttempt))).scalar_one().outcome == "pending"


@pytest.mark.asyncio
async def test_health_cleanup_and_finalization_guard(db_session, monkeypatch):
    monitor = EmailHealth()
    first = await monitor.begin(db_session, "resend")
    await monitor.finish(db_session, first, "accepted", http_status=200)
    with pytest.raises(RuntimeError, match="already completed"):
        await monitor.finish(db_session, first, "failed", "PROVIDER_REJECTED", 401)
    await db_session.rollback()
    row = await db_session.get(EmailDeliveryAttempt, first)
    assert row.outcome == "accepted"
    row.started_at = datetime.now(timezone.utc) - timedelta(days=10)
    await db_session.commit()
    await monitor.begin(db_session, "resend")
    await monitor.cleanup(db_session)
    assert (await db_session.execute(sa.select(sa.func.count()).select_from(EmailDeliveryAttempt))).scalar_one() == 1
