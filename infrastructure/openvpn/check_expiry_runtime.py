"""Disposable network-namespace check using real OpenVPN and an ephemeral CA."""
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
import json, os
from pathlib import Path
import subprocess, tempfile, time


def main():
    if not Path('/.dockerenv').exists() or os.geteuid()!=0:
        raise SystemExit('Run only in a disposable container')
    processes=[]
    with tempfile.TemporaryDirectory(prefix='expiry-runtime-') as folder:
        root=Path(folder)
        def run(*args):return subprocess.run(list(map(str,args)),check=True,capture_output=True,timeout=20).stdout
        try:
            run('openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes',
                '-subj','/CN=Expiry-Test-CA','-days','30','-keyout',root/'ca.key','-out',root/'ca.crt')
            for name,usage in (('server','serverAuth'),('expiry-client','clientAuth')):
                run('openssl','req','-new','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes',
                    '-subj','/CN='+name,'-keyout',root/(name+'.key'),'-out',root/(name+'.csr'))
                (root/'extensions').write_text('basicConstraints=CA:FALSE\nkeyUsage=digitalSignature\nextendedKeyUsage='+usage+'\n')
                run('openssl','x509','-req','-in',root/(name+'.csr'),'-CA',root/'ca.crt','-CAkey',root/'ca.key',
                    '-CAcreateserial','-days','1','-extfile',root/'extensions','-out',root/(name+'.crt'))
            serial=int(run('openssl','x509','-in',root/'expiry-client.crt','-noout','-serial').decode().strip().split('=')[1],16)
            ccd=Path('/var/lib/mirrage/openvpn/ccd');ccd.mkdir(parents=True)
            deadline=int(time.time())+12
            (ccd/'expiry-client').write_text('ifconfig-push 10.9.0.10 255.255.255.0\n# mirrage-profile-v1 '+
                json.dumps(dict(issued_at=deadline-86400,expires_at=deadline,serial=serial))+'\n')
            (ccd/'expiry-client').chmod(0o640)
            server=root/'server.conf';server.write_text(f'''dev tun-server
proto udp
port 19194
local 127.0.0.1
server 10.9.0.0 255.255.255.0 nopool
topology subnet
disable-dco
ca {root}/ca.crt
cert {root}/server.crt
key {root}/server.key
dh none
remote-cert-tls client
client-config-dir {ccd}
ccd-exclusive
script-security 2
client-connect "/usr/bin/python3 -I /checks/client_connect.py"
management {root}/management.sock unix
log {root}/server.log
verb 3
''')
            client=root/'client.conf';client.write_text(f'''client
dev tun-client
proto udp
remote 127.0.0.1 19194
nobind
disable-dco
ca {root}/ca.crt
cert {root}/expiry-client.crt
key {root}/expiry-client.key
remote-cert-tls server
connect-retry 1 1
log {root}/client.log
verb 3
''')
            def spawn(config):
                p=subprocess.Popen(['/usr/sbin/openvpn','--config',str(config)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                processes.append(p);return p
            server_process=spawn(server)
            control=SourceFileLoader('test_vpn_control','/checks/vpn_control.py').load_module()
            def connected():
                m=control.Management(root/'management.sock')
                try:return any(x.startswith('CLIENT_LIST,expiry-client,') for x in m.command('status 2',status=True))
                finally:m.close()
            for _ in range(50):
                if (root/'management.sock').exists():break
                assert server_process.poll() is None
                time.sleep(.1)
            client_process=spawn(client)
            for _ in range(70):
                if connected() and 'Initialization Sequence Completed' in (root/'client.log').read_text():break
                time.sleep(.1)
            else:raise AssertionError('Real client did not connect before expiry')
            while time.time()<deadline+2:time.sleep(.1)
            assert not connected(),'Server retained the connection past its fixed deadline'
            client_process.terminate();client_process.wait(timeout=5)
            (root/'client.log').unlink()
            spawn(client)
            for _ in range(25):
                assert not (root/'client.log').exists() or 'Initialization Sequence Completed' not in (root/'client.log').read_text(),'Expired credentials reconnected'
                time.sleep(.1)
            assert any(x in (root/'server.log').read_text() for x in ('client-connect script','Failed running command (--client-connect)'))
            assert server_process.poll() is None
            print('PASS: real OpenVPN connected, server-side expiry disconnected it, and reconnection after deadline was rejected.')
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':main()
