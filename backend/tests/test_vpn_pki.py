import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.app.core.config import settings
from backend.app.services import vpn_provisioner as pki


@pytest.fixture
def fake_pki(tmp_path, monkeypatch):
    (tmp_path / "easyrsa").touch()
    (tmp_path / "pki").mkdir()
    monkeypatch.setattr(settings, "EASYRSA_DIR", str(tmp_path))
    return tmp_path / "pki"


@pytest.mark.asyncio
async def test_already_revoked_certificate_only_regenerates_crl(fake_pki, monkeypatch):
    (fake_pki / "index.txt").write_text("R\t300101000000Z\t260101000000Z\t01\tunknown\t/CN=player-a\n")
    (fake_pki / "crl.pem").write_text("test public CRL")
    run = AsyncMock()
    monkeypatch.setattr(pki, "_run_easyrsa", run)
    await pki.revoke_client_certificate("player-a")
    run.assert_awaited_once_with("gen-crl")
    with pytest.raises(pki.VPNProvisionerError, match="revoked"):
        await pki.create_client_certificate("player-a")


@pytest.mark.asyncio
async def test_missing_new_crl_cannot_report_success(fake_pki, monkeypatch):
    monkeypatch.setattr(pki, "_run_easyrsa", AsyncMock())
    with pytest.raises(pki.VPNProvisionerError, match="produce a CRL"):
        await pki.revoke_client_certificate("player-a")


@pytest.mark.asyncio
async def test_pki_lock_serializes_separate_coroutines(fake_pki):
    inside = 0
    async def operation():
        nonlocal inside
        async with pki.pki_lock():
            assert inside == 0
            inside += 1
            await asyncio.sleep(0.02)
            inside -= 1
    await asyncio.gather(operation(), operation())


@pytest.mark.asyncio
async def test_subprocess_output_never_surfaces_secrets(fake_pki, monkeypatch):
    monkeypatch.setattr(pki, "_read_ca_passphrase", lambda: "disposable-passphrase")
    process = type("Process", (), {"returncode": 1, "communicate": AsyncMock(
        return_value=(b"disposable-passphrase", b"private diagnostic"))})()
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(pki.VPNProvisionerError) as error:
        await pki._run_easyrsa("gen-crl")
    assert str(error.value) == "PKI operation failed"
    assert "disposable-passphrase" not in str(spawn.call_args.args)
