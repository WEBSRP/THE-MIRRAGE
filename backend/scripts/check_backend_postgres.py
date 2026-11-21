"""Run the backend suite with disposable PostgreSQL concurrency checks.

Run from the repository root. Requires Docker, backend/.venv and a cached
postgres:16-alpine image. Does not load production environment files, expose
ports, or connect to an existing database. Container and sockets are removed.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

name = 'mirrage-backend-check-' + uuid.uuid4().hex[:10]
socket_dir = Path(tempfile.mkdtemp(prefix='mirrage-pg-'))
socket_dir.chmod(0o1777)  # PostgreSQL container UID can create its public socket.
def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True, **kwargs)
try:
    docker('run', '--detach', '--name', name, '--network', 'none', '--tmpfs', '/var/lib/postgresql/data',
           '--mount', f'type=bind,source={socket_dir},target={socket_dir}',
           '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-e', f'PGHOST={socket_dir}', 'postgres:16-alpine',
           '-c', f'unix_socket_directories={socket_dir},/var/run/postgresql', '-c', 'listen_addresses=')
    for _ in range(50):
        check = subprocess.run(['docker', 'exec', name, 'pg_isready', '-h', str(socket_dir), '-U', 'postgres'],
                               capture_output=True)
        if check.returncode == 0 and 'PostgreSQL init process complete' in docker('logs', name).stdout:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError('Disposable PostgreSQL did not initialize; check the test image')
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL') if key in os.environ}
    env.update(ENV_FILE=str(socket_dir / 'no.env'), ENVIRONMENT='testing',
               SECRET_KEY='test-only-key-minimum-length-for-local-tests-123',
               OTP_HMAC_SECRET='test-only-otp-key-minimum-length-local-tests-123',
               EASYRSA_DIR=str(socket_dir / 'no-pki'),
               EASYRSA_CA_CERT=str(socket_dir / 'no-ca.crt'),
               EASYRSA_TLS_KEY=str(socket_dir / 'no-tls.key'),
               VPN_CA_PASSPHRASE_FILE=str(socket_dir / 'no-passphrase'),
               VPN_CONTROL_HELPER='/nonexistent/mirrage-vpn-control',
               SESSION_GATEWAY_HELPER='/nonexistent/mirrage-session-access',
               K8S_MODE='mock', VPN_MODE='mock', DATABASE_URL='sqlite+aiosqlite:///:memory:',
               PYTHONPATH='.', MIRRAGE_TEST_POSTGRES_URL=f'postgresql+asyncpg://postgres@/postgres?host={socket_dir}')
    targets = sys.argv[1:] or ['backend/tests', 'backend/tests_unit']
    result = subprocess.run(['backend/.venv/bin/python', '-m', 'pytest', *targets,
                             '-q', '--disable-warnings', '--maxfail=3', '--tb=short'],
                            env=env, timeout=180)
    raise SystemExit(result.returncode)
finally:
    docker('rm', '-f', name)
    for item in socket_dir.iterdir():
        item.unlink()
    socket_dir.rmdir()
