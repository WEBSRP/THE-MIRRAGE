"""
Production VPN provisioner module.

Provides a clean importable interface for Easy-RSA certificate operations.
Designed to be called by ProductionVPNService — never exposes CA passphrase
in logs, exceptions, CLI arguments, or API responses.
"""

import asyncio
from contextlib import asynccontextmanager
import fcntl
from functools import wraps
import signal
import time
import logging
import os
import re
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings

logger = logging.getLogger("mirrage.vpn.provisioner")

# Restrict characters in client names to prevent command injection
_CLIENT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class VPNProvisionerError(Exception):
    """Raised when VPN certificate provisioning fails.

    SECURITY: Messages must never include the CA passphrase,
    private key contents, or other secret material.
    """
    pass


def _validate_client_name(client_name: str) -> str:
    """Validate and return a safe client name.

    Only alphanumeric characters, underscores, and hyphens are allowed.
    Maximum 64 characters.
    """
    if not _CLIENT_NAME_PATTERN.fullmatch(client_name):
        raise VPNProvisionerError(
            "Invalid client name. Use only letters, numbers, _ and - (max 64 chars)."
        )
    return client_name


def _read_ca_passphrase() -> str:
    """Read the CA passphrase from the protected file.

    SECURITY: The passphrase is read from a file with restrictive
    permissions (root:admin 640) and must never be logged or exposed.
    """
    passphrase_path = Path(settings.VPN_CA_PASSPHRASE_FILE).expanduser()

    if not passphrase_path.exists():
        raise VPNProvisionerError(
            f"CA passphrase file not found: {settings.VPN_CA_PASSPHRASE_FILE}"
        )

    try:
        passphrase = passphrase_path.read_text().strip()
    except PermissionError:
        raise VPNProvisionerError(
            "Cannot read CA passphrase file — insufficient permissions"
        )

    if not passphrase:
        raise VPNProvisionerError(
            "CA passphrase file is empty"
        )

    return passphrase


def _get_easyrsa_paths():
    """Return validated Easy-RSA path objects."""
    easyrsa_dir = Path(settings.EASYRSA_DIR).expanduser()
    easyrsa_bin = easyrsa_dir / "easyrsa"

    if not easyrsa_dir.exists():
        raise VPNProvisionerError(
            f"Easy-RSA directory not found: {easyrsa_dir}"
        )

    if not easyrsa_bin.exists():
        raise VPNProvisionerError(
            f"Easy-RSA binary not found: {easyrsa_bin}"
        )

    return easyrsa_dir, easyrsa_bin


def _client_cert_exists(client_name: str) -> bool:
    """Check if a client certificate already exists in the PKI."""
    client_name = _validate_client_name(client_name)
    cert_path = Path(settings.EASYRSA_DIR).expanduser() / "pki" / "issued" / f"{client_name}.crt"
    return cert_path.exists()


@asynccontextmanager
async def pki_lock():
    directory, _ = _get_easyrsa_paths()
    fd = os.open(directory / ".mirrage-pki.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + settings.VPN_PKI_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise VPNProvisionerError("PKI operation is busy")
                await asyncio.sleep(0.1)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def serialized_pki(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        async with pki_lock():
            return await function(*args, **kwargs)
    return wrapped


async def _run_easyrsa(*arguments) -> None:
    directory, binary = _get_easyrsa_paths()
    env = os.environ.copy()
    env["EASYRSA_BATCH"] = "1"
    env["EASYRSA_PASSIN"] = "pass:" + _read_ca_passphrase()
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            str(binary), *arguments, cwd=str(directory), env=env, start_new_session=True,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(process.communicate(), timeout=settings.VPN_PKI_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise VPNProvisionerError("PKI operation interrupted or timed out") from None
        if process.returncode:
            # Never surface subprocess output: it can include private paths/values.
            raise VPNProvisionerError("PKI operation failed")
    finally:
        env.pop("EASYRSA_PASSIN", None)


@serialized_pki
async def create_client_certificate(client_name: str) -> None:
    client_name = _validate_client_name(client_name)
    if _certificate_revoked_in_index(client_name):
        raise VPNProvisionerError("Certificate is revoked; explicit reissuance is required")
    if _client_cert_exists(client_name):
        return
    await _run_easyrsa("--days=1", "build-client-full", client_name, "nopass")


def _certificate_revoked_in_index(client_name: str) -> bool:
    index = Path(settings.EASYRSA_DIR).expanduser() / "pki" / "index.txt"
    if not index.exists():
        return False
    for line in index.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) >= 6 and fields[0] == "R":
            if re.search(r"(?:^|/)CN=" + re.escape(client_name) + r"(?:/|$)", fields[5]):
                return True
    return False


def build_ovpn_profile(client_name: str) -> str:
    """Build an inline .ovpn profile containing all required credentials.

    Reads:
        - CA certificate
        - Client certificate
        - Client private key
        - TLS-crypt key

    Returns:
        Complete .ovpn configuration string

    Raises:
        VPNProvisionerError: If required files are missing
    """
    client_name = _validate_client_name(client_name)

    easyrsa_dir = Path(settings.EASYRSA_DIR).expanduser()
    ca_cert_path = Path(settings.EASYRSA_CA_CERT).expanduser()
    tls_key_path = Path(settings.EASYRSA_TLS_KEY).expanduser()
    client_cert_path = easyrsa_dir / "pki" / "issued" / f"{client_name}.crt"
    client_key_path = easyrsa_dir / "pki" / "private" / f"{client_name}.key"

    # Verify all required files exist
    required_files = {
        "CA certificate": ca_cert_path,
        "TLS-crypt key": tls_key_path,
        "Client certificate": client_cert_path,
        "Client private key": client_key_path,
    }

    for name, path in required_files.items():
        if not path.exists():
            raise VPNProvisionerError(f"Missing {name}: {path}")

    # Read file contents
    ca_cert = ca_cert_path.read_text()
    client_cert = client_cert_path.read_text()
    client_key = client_key_path.read_text()
    tls_key = tls_key_path.read_text()

    # Build the inline .ovpn profile
    server_host = settings.OPENVPN_SERVER_HOST
    server_port = settings.OPENVPN_SERVER_PORT

    ovpn = f"""client

dev tun
proto {settings.OPENVPN_PROTO}

remote {server_host} {server_port}

resolv-retry infinite
nobind

persist-key
persist-tun

remote-cert-tls server

data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
auth SHA256

verb 3

<ca>
{ca_cert.strip()}
</ca>

<cert>
{client_cert.strip()}
</cert>

<key>
{client_key.strip()}
</key>

<tls-crypt>
{tls_key.strip()}
</tls-crypt>
"""

    return ovpn


@serialized_pki
async def revoke_client_certificate(client_name: str) -> None:
    """Revoke idempotently and generate a fresh CRL; publishing is a verified root operation."""
    client_name = _validate_client_name(client_name)
    if not _certificate_revoked_in_index(client_name):
        # Missing files/certificates must fail, never masquerade as successful revocation.
        await _run_easyrsa("revoke", client_name)
    await _run_easyrsa("gen-crl")
    if not (Path(settings.EASYRSA_DIR).expanduser() / "pki" / "crl.pem").is_file():
        raise VPNProvisionerError("PKI did not produce a CRL")


@serialized_pki
async def refresh_certificate_revocation_list() -> None:
    await _run_easyrsa("gen-crl")
    if not (Path(settings.EASYRSA_DIR).expanduser() / "pki" / "crl.pem").is_file():
        raise VPNProvisionerError("PKI did not produce a CRL")


def generate_client_name(user_id: str) -> str:
    """Generate a safe, deterministic client name from user ID.

    Format: mirrage-<first 8 chars of user_id>
    This ensures uniqueness (UUIDs) while keeping names short.
    """
    # Strip hyphens and take first 12 chars for sufficient uniqueness
    safe_id = user_id.replace("-", "")[:12]
    prefix = settings.VPN_CLIENT_NAME_PREFIX
    return f"{prefix}-{safe_id}"


def parse_openvpn_status_log(log_path: Optional[str] = None) -> dict:
    """Parse the OpenVPN status log (version 2, CSV format).

    Returns a dict mapping Common Name -> connection info dict:
    {
        "client_name": {
            "real_address": "1.2.3.4:port",
            "virtual_address": "10.8.0.X",
            "bytes_received": int,
            "bytes_sent": int,
            "connected_since": "datetime string",
        }
    }
    """
    if log_path is None:
        log_path = settings.OPENVPN_STATUS_LOG_PATH

    status_path = Path(log_path).expanduser()
    clients = {}

    if not status_path.exists():
        logger.warning("OpenVPN status log not found: %s", log_path)
        return clients

    try:
        content = status_path.read_text()
    except PermissionError:
        logger.error("Cannot read OpenVPN status log — insufficient permissions: %s", log_path)
        return clients

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(("TITLE,", "TIME,", "HEADER,", "GLOBAL_STATS,", "END")):
            continue

        parts = line.split(",")

        # CLIENT_LIST lines have the format:
        # Common Name, Real Address, Virtual Address, Virtual IPv6 Address,
        # Bytes Received, Bytes Sent, Connected Since, Connected Since (time_t),
        # Username, Client ID, Peer ID, Data Channel Cipher
        if parts[0] == "CLIENT_LIST" and len(parts) >= 8:
            common_name = parts[1]
            try:
                clients[common_name] = {
                    "real_address": parts[2],
                    "virtual_address": parts[3],
                    "bytes_received": int(parts[5]) if parts[5] else 0,
                    "bytes_sent": int(parts[6]) if parts[6] else 0,
                    "connected_since": parts[7] if parts[7] else None,
                }
            except (ValueError, IndexError):
                logger.warning("Skipping malformed status log line: %s", line[:80])
                continue
        elif len(parts) >= 7 and parts[0] != "Common Name" and parts[0] != "ROUTING_TABLE":
            common_name = parts[0]
            try:
                clients[common_name] = {
                    "real_address": parts[1],
                    "virtual_address": parts[2],
                    "bytes_received": int(parts[4]) if parts[4] else 0,
                    "bytes_sent": int(parts[5]) if parts[5] else 0,
                    "connected_since": parts[6] if parts[6] else None,
                }
            except (ValueError, IndexError):
                logger.warning("Skipping malformed status log line: %s", line[:80])
                continue

    return clients


def _sanitize_error(error_text: str) -> str:
    """Remove any potential secret material from error messages.

    Strips passphrase references, paths to private keys, and
    other sensitive content that might leak through error output.
    """
    # Truncate very long errors
    if len(error_text) > 500:
        error_text = error_text[:500] + "..."

    # Remove lines that might contain passphrase-related content
    sanitized_lines = []
    sensitive_patterns = [
        "pass:", "passphrase", "password", "PASSIN",
        "private key", "ca.key",
    ]

    for line in error_text.splitlines():
        lower_line = line.lower()
        if any(pattern.lower() in lower_line for pattern in sensitive_patterns):
            sanitized_lines.append("[sensitive content redacted]")
        else:
            sanitized_lines.append(line)

    return "\n".join(sanitized_lines)
