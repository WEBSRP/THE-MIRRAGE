#!/usr/bin/python3
"""OpenVPN learn-address hook: permit only the certificate's reserved IPv4 address.

Install root-owned at /usr/local/lib/mirrage/learn_address.py. No DB, shell,
network, or user-controlled paths. OpenVPN supplies the authenticated CN.
"""
import ipaddress
import os
from pathlib import Path
import re
import shlex
import sys

CCD_DIRECTORY = Path("/var/lib/mirrage/openvpn/ccd")


def allowed(operation: str, address: str, common_name: str | None, directory=CCD_DIRECTORY) -> bool:
    if operation == "delete":
        return True
    if operation not in ("add", "update") or not common_name:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", common_name):
        return False
    try:
        actual = ipaddress.IPv4Address(address)
        fd = os.open(Path(directory) / common_name, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as handle:
            records = [shlex.split(line, comments=True) for line in handle if line.strip()]
        assignments = [row for row in records if row and row[0] == "ifconfig-push"]
        return (len(assignments) == 1 and len(assignments[0]) == 3
                and actual == ipaddress.IPv4Address(assignments[0][1]))
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        raise SystemExit(1)
    raise SystemExit(0 if allowed(args[0], args[1], args[2] if len(args) == 3 else None) else 1)
