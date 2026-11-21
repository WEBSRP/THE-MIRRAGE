"""Validate packaged migration CLI and app startup in a disposable backend image."""
import argparse
import subprocess

CHECK = r'''
import asyncio
import json
import subprocess
import sys
from backend.app.core.database import init_db

def cli(*args):
    return subprocess.check_output([sys.executable, "-m", "backend.scripts.migrate", *args], text=True)

assert json.loads(cli("status"))["state"] == "unversioned"
try:
    asyncio.run(init_db())
except RuntimeError:
    pass
else:
    raise AssertionError("Unmigrated startup was accepted")
cli("upgrade")
assert json.loads(cli("status"))["state"] == "current"
asyncio.run(init_db())

from backend.app.main import app
async def startup():
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.05)
asyncio.run(startup())
print("PASS: packaged CLI, empty upgrade, revision guard, seeding and mock app startup")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mirrage-backend:migrations-check")
    args = parser.parse_args()
    subprocess.run([
        "docker", "run", "--rm", "--network", "none", "--tmpfs", "/checks:rw,nosuid,nodev",
        "-e", "ENV_FILE=/checks/no.env", "-e", "ENVIRONMENT=testing",
        "-e", "SECRET_KEY=test-only-key-minimum-length-for-local-tests-123",
        "-e", "OTP_HMAC_SECRET=test-only-otp-key-minimum-length-local-tests-123",
        "-e", "K8S_MODE=mock", "-e", "VPN_MODE=mock",
        "-e", "DATABASE_URL=sqlite+aiosqlite:////checks/mirrage.db",
        "--entrypoint", "python", args.image, "-c", CHECK,
    ], check=True, timeout=60)


if __name__ == "__main__":
    main()
