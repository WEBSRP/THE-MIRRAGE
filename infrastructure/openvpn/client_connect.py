#!/usr/bin/python3 -I
"""Enforce certificate-bound expiry and a server-side per-client disconnect timer."""
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

CCD_DIRECTORY = Path('/var/lib/mirrage/openvpn/ccd')
PREFIX = '# mirrage-profile-v1 '
MAX_SECONDS = 86400


def session_config(common_name, serial, *, directory=CCD_DIRECTORY, now=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', common_name or ''):
        raise ValueError('Invalid certificate identity')
    if not re.fullmatch(r'[0-9]{1,60}', serial or '') or int(serial) < 1:
        raise ValueError('Missing verified certificate serial')
    fd = os.open(Path(directory) / common_name, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o007 or info.st_size > 4096:
            raise ValueError('Unsafe CCD')
        records = [x[len(PREFIX):] for x in stream.read().splitlines() if x.startswith(PREFIX)]
    if len(records) != 1:
        raise ValueError('Missing profile expiry binding')
    binding = json.loads(records[0])
    if set(binding) != {'issued_at', 'expires_at', 'serial'} or any(type(v) is not int for v in binding.values()):
        raise ValueError('Invalid expiry binding')
    now = int(time.time()) if now is None else int(now)
    if (binding['serial'] != int(serial)
            or not 0 < binding['expires_at'] - binding['issued_at'] <= MAX_SECONDS
            or not binding['issued_at'] <= now < binding['expires_at']):
        raise ValueError('Expired or mismatched profile')
    remaining = binding['expires_at'] - now
    # This is server-side instance config, not a client-controlled pushed timer.
    return f'session-timeout {remaining}\n'


def main():
    try:
        if len(sys.argv) != 2:
            return 1
        content = session_config(os.environ.get('common_name'), os.environ.get('tls_serial_0'))
        fd = os.open(sys.argv[1], os.O_WRONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'w') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
                return 1
            os.ftruncate(stream.fileno(), 0)
            stream.write(content)
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        return 1  # No public/private certificate or profile contents in logs.


if __name__ == '__main__':
    raise SystemExit(main())
