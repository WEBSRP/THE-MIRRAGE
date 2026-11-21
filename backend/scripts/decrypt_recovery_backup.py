"""Decrypt an EC2 recovery artifact to a new, mode-0600 file.

Requires cryptography. Keep the original encrypted artifact's filename: the
backup format authenticates that name as well as its contents.
"""

import argparse
import base64
import os
from pathlib import Path
import sys

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"MIRRAGE-BACKUP-v1\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--encrypted-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    created = False
    try:
        key = base64.b64decode(args.key_file.read_bytes().strip(), validate=True)
        if len(key) != 32:
            raise ValueError("Expected a 256-bit backup key")
        payload = args.encrypted_file.read_bytes()
        if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 12 + 16:
            raise ValueError("Unsupported or truncated backup format")
        nonce = payload[len(MAGIC):len(MAGIC) + 12]
        plaintext = AESGCM(key).decrypt(
            nonce,
            payload[len(MAGIC) + 12:],
            MAGIC + args.encrypted_file.name.encode("utf-8"),
        )
        # Authenticate before opening an output; never overwrite an existing file.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(plaintext)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError, InvalidTag):
        if created:
            args.output.unlink(missing_ok=True)
        print("Decryption failed; check the key, original artifact name, and output path.", file=sys.stderr)
        return 1
    print("Authenticated backup decrypted to a new protected file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
