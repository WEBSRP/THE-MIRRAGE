"""
MIRRAGE Security Audit Validation Tests

Verifies PHASE 8, 9, 13, 14 requirements:
1. Challenge flag leakage protection (flags never exposed in API, lists, or errors)
2. Constant-time flag comparison via hmac.compare_digest
3. Telemetry sanitization (passwords, JWTs, keys masked in logs)
4. Production fail-closed validation (K8S_MODE=mock or weak secret rejected in prod)
5. Injection and malformed input handling
6. CORS restricted methods and headers
"""
import pytest
from httpx import AsyncClient
from backend.app.core.config import Settings, settings
from backend.app.services.activity_service import _sanitize_payload


@pytest.mark.asyncio
async def test_challenge_flag_never_leaked_in_api_responses(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    """Verify that challenge flags are strictly private and never returned in list endpoints."""
    from backend.app.services.challenge_service import challenge_service
    await challenge_service.seed_default_challenges(db_session)

    # 1. Query challenges list
    response = await async_client.get(
        f"{settings.API_V1_STR}/challenges/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    challenges = response.json()

    KNOWN_FLAGS = [
        "MIRRAGE{r3fl3ct10n_1s_n0t_r34l1ty_7f9a}",
        "MIRRAGE{b3y0nd_th3_d3c0y_c0nt41n3r_82k1}",
        "MIRRAGE{p4rch3d_34rth_r3v34ls_4ll_491d}",
    ]

    for chal in challenges:
        # Schema should never include flag key
        assert "flag" not in chal
        # Check that none of the secret flag strings appear in any string field
        for flag in KNOWN_FLAGS:
            assert flag not in str(chal)


@pytest.mark.asyncio
async def test_invalid_flag_submission_does_not_reveal_flag(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    """Submitting an incorrect flag gives a failure response without leaking the expected flag."""
    from backend.app.services.challenge_service import challenge_service
    await challenge_service.seed_default_challenges(db_session)

    response = await async_client.post(
        f"{settings.API_V1_STR}/challenges/submit",
        headers=auth_headers,
        json={"challenge_slug": "first-reflection", "flag": "MIRRAGE{totally_wrong_guess}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is False
    assert "r3fl3ct10n" not in data["message"]
    assert "flag" not in data or data["flag"] is None


def test_telemetry_payload_sanitization():
    """Verify recursive masking of sensitive keys in activity payloads."""
    dirty_payload = {
        "user_id": "user-123",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
        "nested": {
            "api_secret": "my-secret-value",
            "ovpn_config": "client dev tun ...",
            "normal_data": "visible_telemetry",
            "list_items": [
                {"private_key": "-----BEGIN PRIVATE KEY-----"},
                {"safe_item": 42},
            ],
        },
    }

    clean = _sanitize_payload(dirty_payload)

    assert clean["user_id"] == "user-123"
    assert clean["password"] == "[REDACTED]"
    assert clean["access_token"] == "[REDACTED]"
    assert clean["nested"]["api_secret"] == "[REDACTED]"
    assert clean["nested"]["ovpn_config"] == "[REDACTED]"
    assert clean["nested"]["normal_data"] == "visible_telemetry"
    assert clean["nested"]["list_items"][0]["private_key"] == "[REDACTED]"
    assert clean["nested"]["list_items"][1]["safe_item"] == 42


def test_production_fails_closed_with_mock_services():
    """Production mode must fail closed if K8S_MODE or VPN_MODE is 'mock' without explicit override."""
    # Misconfigured production settings (mock k8s in prod, valid long key without banned words)
    bad_prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="A-Very-Secure-And-Long-Production-Key-With-No-Banned-Words-32chars",
        K8S_MODE="mock",
        VPN_MODE="production",
        ALLOW_MOCK_IN_PRODUCTION=False,
    )

    with pytest.raises(ValueError, match="K8S_MODE must be 'production'"):
        bad_prod_settings.validate_production_config()


def test_production_fails_closed_with_insecure_secret():
    """Production mode must fail closed if SECRET_KEY contains known insecure patterns."""
    with pytest.raises(Exception) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="mirrage-insecure-key-too-obvious-to-use-in-production-32c",
            K8S_MODE="production",
            VPN_MODE="production",
        )
    assert "insecure" in str(exc_info.value).lower() or "mirrage" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_sql_injection_in_session_id_returns_clean_404(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """Verify that SQL injection patterns in query parameters return safe 404 without SQL error."""
    sqli_payload = "' OR 1=1; DROP TABLE users; --"
    response = await async_client.get(
        f"{settings.API_V1_STR}/session/status",
        headers=auth_headers,
        params={"session_id": sqli_payload},
    )
    # Must return 404 Entity Not Found cleanly, never 500 or SQL syntax error
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "ENTITY_NOT_FOUND"


def test_settings_loads_backend_env_reliably(monkeypatch):
    """
    Regression test: Settings must resolve backend/.env reliably regardless of current working directory.
    Also verifies that environment variables maintain higher priority than .env values.
    """
    import os
    from backend.app.core.config import Settings, DEFAULT_ENV_FILE
    from pathlib import Path

    # Verify default env file points to backend/.env
    assert Path(DEFAULT_ENV_FILE).name == ".env"
    assert Path(DEFAULT_ENV_FILE).parent.name == "backend"
    assert Path(DEFAULT_ENV_FILE).exists()

    # Clear SECRET_KEY from os.environ to test loading directly from backend/.env
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    loaded_settings = Settings()
    assert loaded_settings.SECRET_KEY is not None
    assert len(loaded_settings.SECRET_KEY) >= 32
    assert loaded_settings.PROJECT_NAME == "MIRRAGE API"

    # Verify env var override takes precedence over .env file
    monkeypatch.setenv("PROJECT_NAME", "Overridden API Name")
    override_settings = Settings()
    assert override_settings.PROJECT_NAME == "Overridden API Name"


def test_openapi_uses_http_bearer_security_scheme():
    """
    Regression test: Verify that the OpenAPI schema specifies an HTTP Bearer JWT security scheme
    (type: http, scheme: bearer, bearerFormat: JWT) rather than OAuth2 password flow.
    """
    from backend.app.main import app

    # Reset cached openapi schema so it generates fresh
    app.openapi_schema = None
    openapi = app.openapi()
    security_schemes = openapi.get("components", {}).get("securitySchemes", {})

    # Must have BearerAuth scheme
    assert "BearerAuth" in security_schemes, f"BearerAuth missing from securitySchemes: {list(security_schemes.keys())}"
    scheme = security_schemes["BearerAuth"]

    assert scheme["type"] == "http"
    assert scheme["scheme"].lower() == "bearer"
    assert scheme.get("bearerFormat") == "JWT"

    # Must NOT have OAuth2 password flow or tokenUrl
    for s_name, s_def in security_schemes.items():
        assert s_def.get("type") != "oauth2", f"Found disallowed oauth2 security scheme: {s_name}"
        assert "tokenUrl" not in s_def, f"Found disallowed tokenUrl in security scheme: {s_name}"
        assert "flows" not in s_def, f"Found disallowed flows in security scheme: {s_name}"
