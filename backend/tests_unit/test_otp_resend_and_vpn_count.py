"""Service tests with in-memory records; no database or network needed."""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.app.core.exceptions import MirrageException
from backend.app.services.auth_service import AuthService
from backend.app.services.vpn_service import ProductionVPNService


@pytest.mark.asyncio
async def test_immediate_resend_is_single_use_and_cannot_bypass_cooldown():
    records = []
    async def execute(query):
        if 'FROM users' in str(query):
            return Mock(scalars=Mock(return_value=Mock(first=Mock(return_value=None))))
        rows = list(records)
        return Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=rows))))
    def add(record):
        record.created_at = datetime.now()
        record.is_used = False
        records.append(record)
    db = Mock(bind=SimpleNamespace(dialect=SimpleNamespace(name='sqlite')),
              execute=AsyncMock(side_effect=execute), add=Mock(side_effect=add), commit=AsyncMock())
    service = AuthService()
    with patch('backend.app.services.auth_service.email_service.send_otp', new_callable=AsyncMock) as send:
        assert await service.request_otp(db, 'player@example.com') == 0
        # Concurrent clicks can consume the immediate resend only once.
        results = await asyncio.gather(*(service.resend_otp(db, 'player@example.com') for _ in range(3)), return_exceptions=True)
        assert results.count(60) == 1
        errors = [result for result in results if isinstance(result, MirrageException)]
        assert len(errors) == 2
        assert all(error.code == 'OTP_COOLDOWN' and int(error.headers['Retry-After']) > 0 for error in errors)
        with pytest.raises(MirrageException, match='wait'):
            await service.request_otp(db, 'player@example.com')
        assert send.await_count == 2
        assert records[0].is_used
        for record in records:
            record.created_at -= timedelta(seconds=61)
        assert await service.resend_otp(db, 'player@example.com') == 60
        # Five sends per window still applies after waiting between sends.
        while len(records) < 5:
            for record in records:
                record.created_at -= timedelta(seconds=61)
            await service.resend_otp(db, 'player@example.com')
        with pytest.raises(MirrageException) as limited:
            await service.resend_otp(db, 'player@example.com')
        assert limited.value.code == 'OTP_RATE_LIMIT'
        assert int(limited.value.headers['Retry-After']) > 60


@pytest.mark.asyncio
async def test_vpn_count_tracks_other_clients_without_returning_their_details():
    profile = SimpleNamespace(client_name='my-client', revoked_at=None, is_connected=False,
                              assigned_ip=None, bytes_received=0, bytes_sent=0,
                              connected_since=None, last_seen_at=None)
    service = ProductionVPNService()
    service.generate_or_get_profile = AsyncMock(return_value=profile)
    db = Mock(commit=AsyncMock())
    clients = {'my-client': {'virtual_address': '10.8.0.10'}, 'private-other-client': {'virtual_address': '10.8.0.11'}}
    with patch('backend.app.services.vpn_provisioner.parse_openvpn_status_log', return_value=clients):
        connected = await service.get_vpn_status(db, SimpleNamespace())
        assert connected.is_connected and connected.connected_clients == 2
        assert 'private-other-client' not in connected.model_dump_json()
        assert '10.8.0.11' not in connected.model_dump_json()
        del clients['my-client']
        disconnected = await service.get_vpn_status(db, SimpleNamespace())
        assert not disconnected.is_connected and disconnected.connected_clients == 1
        clients.clear()
        assert (await service.get_vpn_status(db, SimpleNamespace())).connected_clients == 0
