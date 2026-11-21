"""Exercise the CRL publisher against real ephemeral certificates and OpenSSL."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

spec = spec_from_file_location("vpn_control_helper", Path(__file__).resolve().parents[2] /
                              "infrastructure/openvpn/vpn_control.py")
helper = module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def pki(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable test CA")])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(1).not_valid_before(now - timedelta(days=1))
          .not_valid_after(now + timedelta(days=90))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(key, hashes.SHA256()))
    ca_path = tmp_path / "ca.crt"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cache = tmp_path / "cache"
    cache.mkdir()
    for client, serial in (("player-a", 11), ("player-b", 12)):
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, client)])
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(name).public_key(key.public_key())
                .serial_number(serial).not_valid_before(now - timedelta(days=1))
                .not_valid_after(now + timedelta(days=30)).sign(key, hashes.SHA256()))
        (tmp_path / f"{client}.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    config = dict(ca_certificate=str(ca_path), crl_source=str(tmp_path / "source.pem"),
                  crl_destination=str(tmp_path / "installed.pem"), issued_directory=str(tmp_path),
                  minimum_validity_seconds=3600)
    # Only the ownership check is skipped for unprivileged test directories.
    monkeypatch.setattr(helper, "check_destination", lambda path: None)

    def crl(number, serials=(), days=30, signing_key=None):
        builder = (x509.CertificateRevocationListBuilder().issuer_name(name)
                   .last_update(now - timedelta(minutes=1)).next_update(now + timedelta(days=days))
                   .add_extension(x509.CRLNumber(number), critical=False))
        for serial in serials:
            builder = builder.add_revoked_certificate(x509.RevokedCertificateBuilder()
                .serial_number(serial).revocation_date(now - timedelta(minutes=2)).build())
        payload = builder.sign(signing_key or key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)
        Path(config["crl_source"]).write_bytes(payload)
        return payload

    return config, cache, crl


def test_publish_proves_selected_revocation_and_retains_other_client(pki):
    config, cache, crl = pki
    helper.snapshot_certificate(config, "player-a", cache)
    crl(1)
    helper.publish(config)
    original = Path(config["crl_destination"]).read_bytes()
    with pytest.raises(ValueError, match="selected certificate"):
        helper.publish(config, client="player-a", cache_directory=cache)
    assert Path(config["crl_destination"]).read_bytes() == original
    crl(2, [11])
    helper.publish(config, client="player-a", cache_directory=cache)
    info = helper.crl_info(config["crl_destination"], config["ca_certificate"])
    assert info["serials"] == {11} and 12 not in info["serials"]
    helper.publish(config, client="player-a", cache_directory=cache)  # Idempotent retry.


@pytest.mark.parametrize("case", ["rollback", "removed", "same-number", "expired", "wrong-signature"])
def test_bad_crl_never_replaces_installed_revocations(pki, case):
    config, cache, crl = pki
    original = crl(5, [11])
    helper.publish(config)
    if case == "rollback":
        crl(4, [11])
    elif case == "removed":
        crl(6)
    elif case == "same-number":
        crl(5, [11, 12])
    elif case == "expired":
        crl(6, [11], days=0)
    else:
        crl(6, [11], signing_key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
    with pytest.raises(ValueError):
        helper.publish(config)
    assert Path(config["crl_destination"]).read_bytes() == original


def test_certificate_cache_accepts_only_expected_public_identity(pki):
    config, cache, _ = pki
    public = (Path(config["issued_directory"]) / "player-a.crt").read_bytes()
    with pytest.raises(ValueError):
        helper.snapshot_certificate(config, "player-b", cache, public)
    with pytest.raises(ValueError):
        helper.snapshot_certificate(config, "player-a", cache, public + b"PRIVATE KEY")
    saved = helper.snapshot_certificate(config, "player-a", cache, public)
    assert saved.read_bytes() == public
    (Path(config["issued_directory"]) / "player-a.crt").unlink()
    assert helper.snapshot_certificate(config, "player-a", cache) == saved


def test_ccd_delete_cannot_escape_directory(tmp_path):
    ccd = tmp_path / "ccd"
    ccd.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("keep")
    for client in ("../victim", "/victim", "x\nkill other", "-option"):
        with pytest.raises(ValueError):
            helper.remove_ccd(ccd, client)
    (ccd / "player-a").symlink_to(victim)
    helper.remove_ccd(ccd, "player-a")
    assert victim.read_text() == "keep"
    link = tmp_path / "linked-ccd"
    link.symlink_to(ccd)
    with pytest.raises(OSError):
        helper.remove_ccd(link, "player-a")


def test_management_kills_only_selected_client(monkeypatch):
    connected = {"player-a", "player-b"}
    commands = []

    class FakeManagement:
        def __init__(self, path):
            pass
        def connected(self, client):
            return client in connected
        def command(self, command):
            commands.append(command)
            connected.remove(command.split()[1])
            return ["SUCCESS: client killed"]
        def close(self):
            pass

    monkeypatch.setattr(helper, "Management", FakeManagement)
    helper.disconnect("unused", "player-a")
    helper.disconnect("unused", "player-a")
    assert connected == {"player-b"} and commands == ["kill player-a"]
