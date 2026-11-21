#!/usr/bin/env python3
"""Install root-only mounted flags before starting any player-accessible service."""
import json
import os
from pathlib import Path
import pwd
import re
import sys

FLAG_TARGETS = {
    "web": (Path("/var/www/html/flag.txt"), "www-data"),
    "user": (Path("/home/player/flag.txt"), "player"),
    "root": (Path("/root/flag.txt"), "root"),
}


def load_flags(path: Path) -> dict[str, str]:
    try:
        flags = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Cannot read mounted CTF flags JSON") from None
    if not isinstance(flags, dict) or set(flags) != set(FLAG_TARGETS):
        raise ValueError("CTF flags must contain exactly web, user and root")
    for stage, value in flags.items():
        if (not isinstance(value, str) or len(value) > 128
                or not re.fullmatch(r"MIRRAGE\{[A-Za-z0-9_-]+\}", value)):
            raise ValueError(f"Invalid {stage} flag format")
    if len(set(flags.values())) != 3:
        raise ValueError("CTF flags must be different")
    return flags


def install_flags(flags: dict[str, str]) -> None:
    for stage, (path, owner) in FLAG_TARGETS.items():
        account = pwd.getpwnam(owner)
        # Reject symlinks and set restrictive permissions before writing anything.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            os.fchown(handle.fileno(), account.pw_uid, account.pw_gid)
            handle.write(flags[stage] + "\n")


def main() -> None:
    try:
        flags = load_flags(Path("/run/mirrage-flags/flags.json"))
        install_flags(flags)
    except (OSError, ValueError, KeyError):
        print("CTF startup failed: check the private flags mount and permissions", file=sys.stderr)
        raise SystemExit(1) from None
    # No flag values are passed through argv or inherited environment variables.
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
