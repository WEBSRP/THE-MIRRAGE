"""Shared flag configuration. Plaintext is private deployment input, never DB data."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from backend.app.core.config import BACKEND_DIR, settings

STAGE_SLUGS = {
    "web": "first-reflection",
    "user": "sub-stratum-breach",
    "root": "oasis-evaporation",
}
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


def flag_digest(value: str) -> str:
    # Keep normalization identical to the submission contract: trim edges only.
    return "sha256:" + hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def load_shared_flags(path: Path, *, production: bool = False) -> dict[str, str]:
    try:
        flags = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Do not include parser input or flag values in startup errors.
        raise ValueError("Cannot read CTF flags JSON file") from None
    if not isinstance(flags, dict) or set(flags) != set(STAGE_SLUGS):
        raise ValueError("CTF flags JSON must contain exactly web, user and root")
    for stage, value in flags.items():
        if (not isinstance(value, str) or value != value.strip()
                or not re.fullmatch(r"MIRRAGE\{[A-Za-z0-9_-]+\}", value)
                or len(value) > 128):
            raise ValueError(f"Invalid {stage} flag format")
        if production and (len(value[8:-1]) < 32 or any(
            term in value.lower() for term in ("test", "dummy", "example", "changeme")
        )):
            raise ValueError(f"Production {stage} flag must be a long random value")
    if len(set(flags.values())) != 3:
        raise ValueError("Web, user and root flags must be different")
    return flags


@lru_cache(maxsize=1)
def get_shared_flags() -> dict[str, str]:
    # Freeze one configuration revision per process. Changing the private file
    # requires a backend restart, so new pods and DB verifiers stay in agreement.
    if not settings.CTF_FLAGS_FILE:
        if settings.ENVIRONMENT == "production":
            raise ValueError("CTF_FLAGS_FILE is required in production")
        path = BACKEND_DIR / "ctf-flags.example.json"
    else:
        path = Path(settings.CTF_FLAGS_FILE).expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
    return load_shared_flags(path, production=settings.ENVIRONMENT == "production")
