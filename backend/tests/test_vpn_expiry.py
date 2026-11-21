from datetime import datetime, timedelta, timezone
from importlib import util
from pathlib import Path
import json
from unittest.mock import AsyncMock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.vpn import VpnProfile, VpnAddressReservation
from backend.app.services.vpn_credentials import certificate_details, PROFILE_SECONDS
from backend.app.services.vpn_service import ProductionVPNService
from backend.app.services import vpn_provisioner as pki
from backend.app.services.vpn_control import vpn_control


def profile_config(name, *, issued=None, days=1):
    issued = issued or datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=2)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(issued).not_valid_after(issued + timedelta(days=days))
            .sign(key, hashes.SHA256()))
    return '<cert>\n' + cert.public_bytes(serialization.Encoding.PEM).decode() + '</cert>\n'


@pytest.fixture
def expiry_pki(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'OPENVPN_CCD_DIR', str(tmp_path))
    issue = AsyncMock()
    monkeypatch.setattr(pki, 'create_client_certificate', issue)
    monkeypatch.setattr(pki, 'build_ovpn_profile', profile_config)
    for method in ('block','publish'):
        monkeypatch.setattr(vpn_control, method, AsyncMock())
    return issue


@pytest.mark.asyncio
async def test_issuer_explicitly_requests_one_day(monkeypatch):
    monkeypatch.setattr(pki, '_certificate_revoked_in_index', lambda _: False)
    monkeypatch.setattr(pki, '_client_cert_exists', lambda _: False)
    run = AsyncMock()
    monkeypatch.setattr(pki, '_run_easyrsa', run)
    # The lock is still real and isolated by the fake directory.
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        Path(root, 'easyrsa').touch()
        monkeypatch.setattr(settings, 'EASYRSA_DIR', root)
        await pki.create_client_certificate('daily-client')
    run.assert_awaited_once_with('--days=1','build-client-full','daily-client','nopass')


def test_signed_expiry_is_not_extended_by_reading_profile():
    config = profile_config('client-a')
    a = certificate_details(config,'client-a')
    b = certificate_details(config,'client-a')
    assert a.expires_at == b.expires_at
    assert (a.expires_at-a.issued_at).total_seconds() == PROFILE_SECONDS
    assert a.usable(a.expires_at-timedelta(seconds=1))
    assert not a.usable(a.expires_at)
    assert not a.usable(a.issued_at-timedelta(seconds=1))
    assert not certificate_details(profile_config('client-a',days=365),'client-a').usable()
    with pytest.raises(ValueError): certificate_details(config,'client-b')


@pytest.mark.asyncio
async def test_valid_download_reuses_file_and_preserves_expiry(db_session,test_user,expiry_pki):
    service = ProductionVPNService()
    a = await service.get_download_profile(db_session,test_user)
    b = await service.get_download_profile(db_session,test_user)
    assert a.config_data == b.config_data and a.expires_at == b.expires_at
    assert expiry_pki.await_count == 1
    assert a.client_ip == b.client_ip


@pytest.mark.asyncio
@pytest.mark.parametrize('expired',[False,True])
async def test_long_lived_or_expired_profile_rotates_without_changing_address(db_session,test_user,expiry_pki,expired):
    issued = datetime.now(timezone.utc)-timedelta(days=2) if expired else None
    old = VpnProfile(user_id=test_user.id,client_name='old-certificate',
                     config_data=profile_config('old-certificate',issued=issued,days=1 if expired else 365),
                     assigned_ip='10.8.0.10',is_connected=True)
    db_session.add_all([old,VpnAddressReservation(user_id=test_user.id,address='10.8.0.10',client_name=old.client_name)])
    await db_session.commit()
    from unittest.mock import patch
    with patch.object(pki,'revoke_client_certificate',new_callable=AsyncMock) as revoke:
        fresh = await ProductionVPNService().generate_or_get_profile(db_session,test_user)
    assert fresh.client_name != 'old-certificate' and fresh.assigned_ip == '10.8.0.10'
    assert certificate_details(fresh.config_data,fresh.client_name).usable()
    assert not fresh.is_connected
    revoke.assert_awaited_once_with('old-certificate')
    reservation=(await db_session.execute(select(VpnAddressReservation).where(VpnAddressReservation.user_id==test_user.id))).scalar_one()
    assert reservation.client_name == fresh.client_name
    vpn_control.block.assert_awaited_once()
    vpn_control.publish.assert_awaited_once_with('old-certificate')


@pytest.mark.asyncio
async def test_admin_revocation_cannot_be_bypassed_by_daily_renewal(db_session,test_user,expiry_pki):
    old=VpnProfile(user_id=test_user.id,client_name='revoked',config_data='',revoked_at=datetime.now(timezone.utc))
    db_session.add(old);await db_session.commit()
    with pytest.raises(Exception,match='revoked'):
        await ProductionVPNService().get_download_profile(db_session,test_user)
    expiry_pki.assert_not_awaited()


def hook_module():
    path=Path(__file__).resolve().parents[2]/'infrastructure/openvpn/client_connect.py'
    spec=util.spec_from_file_location('expiry_connect',path);m=util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_connection_deadline_is_remaining_certificate_lifetime(tmp_path):
    hook=hook_module();path=tmp_path/'client-a'
    binding=dict(issued_at=100,expires_at=86500,serial=42)
    path.write_text('ifconfig-push 10.8.0.10 255.255.255.0\n'+hook.PREFIX+json.dumps(binding)+'\n');path.chmod(0o640)
    assert hook.session_config('client-a','42',directory=tmp_path,now=86490)=='session-timeout 10\n'
    for now,serial in ((86500,'42'),(86501,'42'),(99,'42'),(100,'43')):
        with pytest.raises(ValueError): hook.session_config('client-a',serial,directory=tmp_path,now=now)
    link=tmp_path/'client-b';link.symlink_to(path)
    with pytest.raises(OSError): hook.session_config('client-b','42',directory=tmp_path,now=100)
    path.write_text('ifconfig-push 10.8.0.10 255.255.255.0\n')
    with pytest.raises(ValueError): hook.session_config('client-a','42',directory=tmp_path,now=100)

@pytest.mark.asyncio
async def test_concurrent_workers_issue_one_replacement(tmp_path,monkeypatch,expiry_pki):
    import os, asyncio
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    from backend.app.core.database import Base
    from backend.app.models.user import User
    url=os.environ.get('MIRRAGE_TEST_POSTGRES_URL')
    if not url:pytest.skip('Requires disposable PostgreSQL')
    schema='expiry_concurrency_'+__import__('uuid').uuid4().hex
    engine=create_async_engine(url,connect_args={'server_settings':{'search_path':schema}});sessions=async_sessionmaker(engine,expire_on_commit=False)
    from unittest.mock import patch
    try:
        async with engine.begin() as c:
            await c.execute(__import__('sqlalchemy').schema.CreateSchema(schema))
            await c.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            user=User(email='daily-concurrency@example.com',username='daily-concurrency');db.add(user);await db.flush();uid=user.id
            db.add_all([VpnProfile(user_id=uid,client_name='old-concurrent',config_data=profile_config('old-concurrent',days=365)),
                        VpnAddressReservation(user_id=uid,address='10.8.0.10',client_name='old-concurrent')]);await db.commit()
        async def renew():
            async with sessions() as db:
                user=await db.get(User,uid)
                return (await ProductionVPNService().get_download_profile(db,user)).filename
        with patch.object(pki,'revoke_client_certificate',new_callable=AsyncMock):
            names=await asyncio.gather(renew(),renew(),renew())
        assert len(set(names))==1 and expiry_pki.await_count==1
    finally:
        async with engine.begin() as c:await c.execute(__import__('sqlalchemy').schema.DropSchema(schema,cascade=True))
        await engine.dispose()
