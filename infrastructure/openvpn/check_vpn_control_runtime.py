"""Disposable-container test: real root helper, OpenSSL PKI, simulated management socket."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading


def main():
    if not Path('/.dockerenv').exists() or os.geteuid() != 0:
        raise SystemExit('Run only inside a disposable root container')
    root = Path(tempfile.mkdtemp(prefix='vpn-control-'))
    root.chmod(0o700)
    issued, ccd, newcerts = [root / name for name in ('issued', 'ccd', 'newcerts')]
    for directory in (issued, ccd, newcerts):
        directory.mkdir()

    def run(*args, success=True):
        result = subprocess.run(list(map(str, args)), capture_output=True, timeout=30)
        assert (result.returncode == 0) == success, 'Disposable PKI/helper operation failed'
        return result.stdout

    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=Test-CA',
        '-days', '90', '-keyout', root / 'ca.key', '-out', root / 'ca.crt')
    (root / 'index').touch()
    (root / 'serial').write_text('1000\n')
    (root / 'crlnumber').write_text('1000\n')
    config = root / 'openssl.cnf'
    config.write_text(f'''[ ca ]
default_ca = test
[ test ]
database = {root}/index
new_certs_dir = {newcerts}
certificate = {root}/ca.crt
private_key = {root}/ca.key
serial = {root}/serial
crlnumber = {root}/crlnumber
default_md = sha256
default_days = 30
default_crl_days = 30
policy = policy
[ policy ]
commonName = supplied
''')
    for client in ('player-a', 'player-b'):
        run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + client,
            '-keyout', root / f'{client}.key', '-out', root / f'{client}.csr')
        run('openssl', 'ca', '-batch', '-config', config, '-notext', '-in', root / f'{client}.csr',
            '-out', issued / f'{client}.crt')
        (ccd / client).write_text('test CCD')
    source, destination = root / 'source.pem', root / 'installed.pem'
    run('openssl', 'ca', '-gencrl', '-config', config, '-out', source)
    initial = source.read_bytes()
    management_path = root / 'management.sock'
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(management_path))
    server.listen()
    clients, commands, failures = {'player-a', 'player-b'}, [], []

    def manage():
        try:
            while True:
                connection, _ = server.accept()
                with connection, connection.makefile('rb') as stream:
                    connection.sendall(b'>INFO:Test management interface\n')
                    for raw in stream:
                        command = raw.decode().strip()
                        commands.append(command)
                        if command == 'status 2':
                            rows = ''.join(f'CLIENT_LIST,{client},test\n' for client in sorted(clients))
                            connection.sendall((rows + 'END\n').encode())
                        elif command == 'kill player-a':
                            clients.discard('player-a')
                            connection.sendall(b'SUCCESS: client killed\n')
                        else:
                            raise AssertionError('Unexpected management command')
        except Exception as error:
            failures.append(type(error).__name__)

    threading.Thread(target=manage, daemon=True).start()
    Path('/etc/mirrage').mkdir(exist_ok=True)
    Path('/etc/mirrage/vpn-control.json').write_text(json.dumps(dict(
        ca_certificate=str(root / 'ca.crt'), crl_source=str(source), crl_destination=str(destination),
        issued_directory=str(issued), ccd_directory=str(ccd), management_socket=str(management_path),
        minimum_validity_seconds=3600,
    )))
    helper = Path('/checks/vpn_control.py')
    run('python3', '-I', helper, 'refresh')
    run('python3', '-I', helper, 'block', '--client', 'player-a')
    assert clients == {'player-b'} and (ccd / 'player-b').exists() and not (ccd / 'player-a').exists()
    run('python3', '-I', helper, 'publish', '--client', 'player-a', success=False)
    assert destination.read_bytes() == initial
    run('openssl', 'ca', '-batch', '-config', config, '-revoke', issued / 'player-a.crt')
    run('openssl', 'ca', '-gencrl', '-config', config, '-out', source)
    revoked_certificate = root / 'revoked-a.crt'
    (issued / 'player-a.crt').rename(revoked_certificate)
    run('python3', '-I', helper, 'publish', '--client', 'player-a')
    published = destination.read_bytes()
    # Actual OpenSSL verification rejects A and continues to trust B.
    for cert, success in ((revoked_certificate, False), (issued / 'player-b.crt', True)):
        run('openssl', 'verify', '-CAfile', root / 'ca.crt', '-CRLfile', destination,
            '-crl_check', cert, success=success)
    run('python3', '-I', helper, 'block', '--client', 'player-a')  # Cached cert survives PKI move.
    source.write_bytes(initial)
    run('python3', '-I', helper, 'refresh', success=False)
    assert destination.read_bytes() == published
    assert json.loads(run('python3', '-I', helper, 'health'))['expires_at'] > 0
    assert not failures and commands.count('kill player-a') == 1 and clients == {'player-b'}
    print('PASS: targeted disconnect, CCD removal, cached cert, CRL proof, rollback, health; other client retained')


if __name__ == '__main__':
    main()
