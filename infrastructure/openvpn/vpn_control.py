#!/usr/bin/python3 -I
"""Narrow root operations: remove one CCD/kick one CN; validate/publish public CRLs.

No CA private keys, passphrases, arbitrary paths, arbitrary management commands,
service restarts or shell execution. Install root-owned outside the repository.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

CONFIG = Path("/etc/mirrage/vpn-control.json")
STATE = Path("/var/lib/mirrage/vpn-control")
OPENSSL = "/usr/bin/openssl"
CLIENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def client_name(value):
    if not CLIENT.fullmatch(value or ""):
        raise ValueError("Invalid certificate identity")
    return value


def read_public(path, maximum=8 * 1024 * 1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Expected a regular public certificate/CRL file")
        value = handle.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError("Public certificate/CRL file exceeds size limit")
    return value


def openssl(*arguments):
    result = subprocess.run([OPENSSL, *map(str, arguments)], capture_output=True, timeout=10,
                            env={"PATH": "/usr/bin:/usr/sbin", "LC_ALL": "C"})
    if result.returncode:
        raise ValueError("Public certificate/CRL validation failed")
    if arguments and arguments[0] == "crl" and "-verify" in arguments:
        if b"verify OK" not in result.stdout + result.stderr:
            raise ValueError("CRL signature verification did not succeed")
    return result.stdout


def crl_info(path, ca_certificate, *, fresh=False, minimum=3600):
    openssl("crl", "-in", path, "-noout", "-verify", "-CAfile", ca_certificate)
    output = openssl("crl", "-in", path, "-noout", "-lastupdate", "-nextupdate", "-crlnumber").decode()
    fields = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    issued = datetime.strptime(fields["lastUpdate"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    expires = datetime.strptime(fields["nextUpdate"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    number = int(fields["crlNumber"], 0)
    now = datetime.now(timezone.utc).timestamp()
    if fresh and (issued.timestamp() > now + 60 or expires.timestamp() <= now + minimum):
        raise ValueError("CRL is stale, not yet valid or near expiry")
    text = openssl("crl", "-in", path, "-noout", "-text").decode()
    serials = {int(value.replace(":", ""), 16) for value in re.findall(
        r"^\s*Serial Number:\s*([0-9A-Fa-f:]+)\s*$", text, re.MULTILINE
    )}
    der = openssl("crl", "-in", path, "-outform", "DER")
    return {"number": number, "expires": int(expires.timestamp()), "serials": serials,
            "digest": hashlib.sha256(der).hexdigest()}


def certificate_serial(path, ca_certificate, expected_client):
    openssl("verify", "-no_check_time", "-CAfile", ca_certificate, path)
    subject = openssl("x509", "-in", path, "-noout", "-subject", "-nameopt", "RFC2253").decode().strip()
    parts = re.split(r"(?<!\\),", subject.split("=", 1)[1].strip())
    names = [part[3:] for part in parts if part.startswith("CN=")]
    if names != [expected_client]:
        raise ValueError("Public certificate identity mismatch")
    serial = openssl("x509", "-in", path, "-noout", "-serial").decode().strip().split("=", 1)[1]
    return int(serial, 16)


def snapshot_certificate(config, client, cache_directory, supplied=None):
    client = client_name(client)
    destination = cache_directory / f"{client}.crt"
    if destination.exists():
        certificate_serial(destination, config["ca_certificate"], client)
        return destination
    if supplied is not None:
        if len(supplied) > 65536 or not re.fullmatch(
            rb"\s*-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*", supplied
        ):
            raise ValueError("Expected one public certificate")
        public = supplied
    else:
        issued = read_public(Path(config["issued_directory"]) / f"{client}.crt", maximum=65536)
        match = re.search(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", issued, re.DOTALL)
        if match is None:
            raise ValueError("Public certificate is missing")
        public = match.group(0)
    fd, name = tempfile.mkstemp(dir=cache_directory)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(public)
        certificate_serial(temporary, config["ca_certificate"], client)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def remove_ccd(directory, client):
    client = client_name(client)
    # A backend-writable CCD directory must never become a root unlink primitive.
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            os.unlink(client, dir_fd=fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(fd)


class Management:
    def __init__(self, path):
        info = Path(path).lstat()
        parent = Path(path).parent.stat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0
                or parent.st_uid != 0 or parent.st_mode & 0o022):
            raise ValueError("Management socket must be protected and root-owned")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(4)
        try:
            self.sock.connect(str(path))
        except BaseException:
            self.sock.close()
            raise
        self.stream = self.sock.makefile("rb")

    def close(self):
        self.stream.close()
        self.sock.close()

    def command(self, command, *, status=False):
        self.sock.sendall(command.encode("ascii") + b"\n")
        rows = []
        for _ in range(10000):
            raw = self.stream.readline(16384)
            if not raw or len(raw) >= 16384:
                raise RuntimeError("Incomplete management response")
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            rows.append(line)
            if (status and line == "END") or (not status and line.startswith(("SUCCESS:", "ERROR:"))):
                return rows
        raise RuntimeError("Management response limit exceeded")

    def connected(self, client):
        rows = self.command("status 2", status=True)
        return any(line.startswith("CLIENT_LIST,") and line.split(",")[1] == client for line in rows)


def disconnect(path, client):
    client = client_name(client)
    management = Management(path)
    try:
        if not management.connected(client):
            return
        result = management.command("kill " + client)
        # Always verify absence; a success string alone is insufficient.
        if not any(line.startswith(("SUCCESS:", "ERROR:")) for line in result):
            raise RuntimeError("Unexpected management response")
        if management.connected(client):
            raise RuntimeError("VPN client is still connected")
    finally:
        management.close()


def check_destination(destination):
    parent = destination.parent.stat()
    if parent.st_uid != 0 or parent.st_mode & 0o022 or destination.is_symlink():
        raise ValueError("CRL destination must be protected")


def publish(config, *, client=None, cache_directory=None):
    if client is not None:
        client_name(client)
    destination = Path(config["crl_destination"])
    # Root-owned destination parent; source is an unprivileged PKI writer's public file.
    check_destination(destination)
    payload = read_public(config["crl_source"])
    fd, name = tempfile.mkstemp(dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        candidate = crl_info(temporary, config["ca_certificate"], fresh=True,
                             minimum=config["minimum_validity_seconds"])
        if destination.exists():
            current = crl_info(destination, config["ca_certificate"])
            if (candidate["number"] < current["number"] or not candidate["serials"].issuperset(current["serials"])
                    or (candidate["number"] == current["number"] and candidate["digest"] != current["digest"])):
                raise ValueError("CRL rollback or removal of revocations is forbidden")
        if client:
            serial = certificate_serial(cache_directory / f"{client}.crt", config["ca_certificate"], client)
            if serial not in candidate["serials"]:
                raise ValueError("CRL does not revoke the selected certificate")
        temporary.chmod(0o644)
        os.replace(temporary, destination)
        return candidate["expires"]
    finally:
        temporary.unlink(missing_ok=True)


def load_config():
    info = CONFIG.stat()
    if CONFIG.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("VPN control configuration must be root-owned")
    config = json.loads(CONFIG.read_text())
    paths = {"ca_certificate", "crl_source", "crl_destination", "issued_directory", "ccd_directory", "management_socket"}
    if set(config) != paths | {"minimum_validity_seconds"}:
        raise ValueError("Invalid VPN control configuration")
    if any(not isinstance(config[key], str) or not Path(config[key]).is_absolute() for key in paths):
        raise ValueError("VPN control paths must be absolute")
    if type(config["minimum_validity_seconds"]) is not int or not 60 <= config["minimum_validity_seconds"] <= 86400:
        raise ValueError("Invalid CRL validity requirement")
    ca = Path(config["ca_certificate"])
    info = ca.stat()
    if ca.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("VPN CA trust anchor must be protected")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["block", "publish", "refresh", "health"])
    parser.add_argument("--client")
    parser.add_argument("--certificate-stdin", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("VPN control helper requires root")
    config = load_config()
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
        raise ValueError("VPN control state must be root-only")
    cache = STATE / "certificates"
    cache.mkdir(mode=0o700, exist_ok=True)
    with (STATE / "lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if args.action in ("block", "publish"):
            client = client_name(args.client)
            if args.action == "block":
                remove_ccd(config["ccd_directory"], client)
                supplied = sys.stdin.buffer.read(65537) if args.certificate_stdin else None
                snapshot_certificate(config, client, cache, supplied)
                disconnect(config["management_socket"], client)
            else:
                expires = publish(config, client=client, cache_directory=cache)
                print(json.dumps({"expires_at": expires}))
        elif args.action == "refresh":
            print(json.dumps({"expires_at": publish(config)}))
        else:
            info = crl_info(config["crl_destination"], config["ca_certificate"])
            print(json.dumps({"expires_at": info["expires"]}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("VPN control operation failed; check protected configuration and service health", file=sys.stderr)
        raise SystemExit(1) from None
