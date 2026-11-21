#!/usr/bin/env python3
"""Generate private shared flags without printing values or overwriting a file."""
import argparse
import json
import os
from pathlib import Path
import secrets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    flags = {stage: f"MIRRAGE{{{stage}_{secrets.token_hex(24)}}}" for stage in ("web", "user", "root")}
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(flags, handle, indent=2)
        handle.write("\n")
    print(f"Created private flags file: {args.output} (mode 600). Values were not printed.")


if __name__ == "__main__":
    main()
