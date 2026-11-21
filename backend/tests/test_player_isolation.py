import asyncio
from datetime import datetime, timedelta, timezone
from importlib import import_module, util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.networking import default_deny_policy, player_network_policy
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.models.vpn import VpnAddressReservation
from backend.app.services.k8s_service import ProductionKubernetesService, k8s_provisioner
from backend.app.services.session_service import session_service
from backend.app.services.vpn_access import reserve_address, write_client_config
from backend.app.services.vpn_service import ProductionVPNService

ROOT = Path(__file__).resolve().parents[2]


def load_script(name, filename):
    spec = util.spec_from_file_location(name, ROOT / "infrastructure/openvpn" / filename)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_address_is_persistent_unique_and_independent_of_status_log(db_session, test_user, second_user):
    a = await reserve_address(db_session, test_user.id, "certificate-a")
    b = await reserve_address(db_session, second_user.id, "certificate-b")
    assert a == "10.8.0.10" and b == "10.8.0.11"
    assert await reserve_address(db_session, test_user.id, "certificate-a") == a
    with pytest.raises(Exception, match="identity"):
        await reserve_address(db_session, test_user.id, "changed-certificate")
    rows = (await db_session.execute(select(VpnAddressReservation))).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
async def test_allocation_unique_constraints_arbitrate_concurrent_workers(tmp_path, monkeypatch, database):
    if database == "postgresql":
        url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Requires disposable PostgreSQL")
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'addresses.db'}"
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            users = [User(email=f"isolation{i}@example.com", username=f"isolation{i}") for i in range(4)]
            db.add_all(users)
            await db.commit()
            ids = [user.id for user in users]
        if database == "postgresql":
            # Simulate independent API processes: do not share the local async lock.
            class NoLocalLock:
                async def __aenter__(self):
                    pass
                async def __aexit__(self, *args):
                    pass
            monkeypatch.setattr(import_module("backend.app.services.vpn_access"), "_allocation_lock", NoLocalLock())

        async def allocate(user_id):
            async with sessions() as db:
                return await reserve_address(db, user_id, "isolation-" + user_id[:8])
        results = await asyncio.gather(*(allocate(user_id) for user_id in ids + [ids[0], ids[1]]))
        assert len(set(results[:4])) == 4
        assert results[4:] == results[:2]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_production_profile_writes_ccd_and_retains_reservation_after_failure(
    db_session, test_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "OPENVPN_CCD_DIR", str(tmp_path / "ccd"))
    provisioner = import_module("backend.app.services.vpn_provisioner")
    create = AsyncMock()
    monkeypatch.setattr(provisioner, "create_client_certificate", create)
    monkeypatch.setattr(provisioner, "build_ovpn_profile", lambda _: "test-only-config")
    service = ProductionVPNService()
    profile = await service.generate_or_get_profile(db_session, test_user)
    address = profile.assigned_ip
    assert (tmp_path / "ccd" / profile.client_name).read_text() == f"ifconfig-push {address} 255.255.255.0\n"
    assert await reserve_address(db_session, test_user.id, profile.client_name) == address
    assert (await service.generate_or_get_profile(db_session, test_user)).assigned_ip == address
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_existing_real_certificate_name_is_preserved(db_session, test_user, tmp_path, monkeypatch):
    from backend.app.models.vpn import VpnProfile
    monkeypatch.setattr(settings, "OPENVPN_CCD_DIR", str(tmp_path))
    old = VpnProfile(user_id=test_user.id, client_name="old-real-certificate", config_data="old-config",
                     assigned_ip="10.8.0.99", is_connected=False)
    db_session.add(old)
    await db_session.commit()
    profile = await ProductionVPNService().generate_or_get_profile(db_session, test_user)
    assert profile.client_name == "old-real-certificate"
    assert profile.config_data == "old-config"
    assert (tmp_path / "old-real-certificate").is_file()
    assert profile.assigned_ip == "10.8.0.10"


def test_ccd_writer_and_learning_hook_enforce_authenticated_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OPENVPN_CCD_DIR", str(tmp_path))
    write_client_config("certificate-a", "10.8.0.10")
    write_client_config("certificate-b", "10.8.0.11")
    hook = load_script("learning", "learn_address.py")
    assert hook.allowed("add", "10.8.0.10", "certificate-a", tmp_path)
    assert hook.allowed("update", "10.8.0.11", "certificate-b", tmp_path)
    for address in ("10.8.0.11", "10.8.0.20", "10.8.0.10/24", "::1"):
        assert not hook.allowed("add", address, "certificate-a", tmp_path)
    assert not hook.allowed("add", "10.8.0.10", "../certificate-a", tmp_path)
    assert hook.allowed("delete", "10.8.0.10", None, tmp_path)
    assert not hook.allowed("unknown", "10.8.0.10", "certificate-a", tmp_path)
    (tmp_path / "symlink").symlink_to(tmp_path / "certificate-a")
    assert not hook.allowed("add", "10.8.0.10", "symlink", tmp_path)
    assert (tmp_path / "certificate-a").stat().st_mode & 0o777 == 0o640
    with pytest.raises(ValueError):
        write_client_config("../../bad", "10.8.0.10")


@pytest.mark.asyncio
async def test_unexpected_vpn_telemetry_cannot_reassign_owner_address(monkeypatch):
    profile = SimpleNamespace(client_name="certificate-a", assigned_ip="10.8.0.10", revoked_at=None,
                              is_connected=True, bytes_received=0, bytes_sent=0,
                              connected_since=None, last_seen_at=None)
    service = ProductionVPNService()
    service.generate_or_get_profile = AsyncMock(return_value=profile)
    monkeypatch.setattr(import_module("backend.app.services.vpn_provisioner"), "parse_openvpn_status_log",
                        lambda: {"certificate-a": {"virtual_address": "10.8.0.11"}})
    result = await service.get_vpn_status(AsyncMock(), SimpleNamespace(id="owner"))
    assert not result.is_connected and result.assigned_ip == "10.8.0.10"
    assert profile.assigned_ip == "10.8.0.10"


def test_policies_select_owner_session_and_allow_no_other_outbound(monkeypatch):
    a = player_network_policy("player-a", "session-a", "user-a", "10.8.0.10")
    b = player_network_policy("player-b", "session-b", "user-b", "10.8.0.11")
    assert a["spec"]["podSelector"]["matchLabels"] == {
        "mirrage.io/session-id": "session-a", "mirrage.io/user-id": "user-a",
    }
    assert a["spec"]["ingress"][0]["from"] == [{"ipBlock": {"cidr": "10.8.0.10/32"}}]
    assert b["spec"]["ingress"][0]["from"] == [{"ipBlock": {"cidr": "10.8.0.11/32"}}]
    assert a["spec"]["egress"] == [{"to": [{"ipBlock": {"cidr": "10.8.0.10/32"}}],
                                     "ports": [{"protocol": "TCP", "port": 4444}]}]
    monkeypatch.setattr(settings, "SESSION_CALLBACK_PORTS", [])
    assert player_network_policy("p", "s", "u", "10.8.0.10")["spec"]["egress"] == []
    with pytest.raises(ValueError):
        player_network_policy("p", "s", "u", "192.168.1.1")


def test_existing_broad_or_unknown_policy_blocks_provisioning():
    service = object.__new__(ProductionKubernetesService)
    service.namespace = settings.K8S_NAMESPACE
    service.networking_v1 = Mock()
    broad = default_deny_policy()
    broad["spec"]["ingress"] = [{"from": [{"ipBlock": {"cidr": "10.8.0.0/24"}}]}]
    service.networking_v1.list_namespaced_network_policy.return_value = SimpleNamespace(items=[broad])
    with pytest.raises(RuntimeError, match="Unsafe"):
        service._ensure_network_boundary()
    unknown = default_deny_policy()
    unknown["metadata"]["name"] = "allow-everything"
    service.networking_v1.list_namespaced_network_policy.return_value = SimpleNamespace(items=[unknown])
    with pytest.raises(RuntimeError, match="Unexpected"):
        service._ensure_network_boundary()
    service.networking_v1.create_namespaced_network_policy.assert_not_called()
    service.networking_v1.list_namespaced_network_policy.return_value = SimpleNamespace(items=[
        default_deny_policy(), player_network_policy("player-a", "a", "u", "10.8.0.10"),
    ])
    service._ensure_network_boundary()


@pytest.mark.asyncio
async def test_policy_is_installed_before_pod_and_deleted_after_confirmed_removal():
    from kubernetes.client.rest import ApiException
    service = object.__new__(ProductionKubernetesService)
    service.namespace = settings.K8S_NAMESPACE
    service._ensure_namespace_and_sa = Mock()
    service._ensure_flags_secret = Mock(return_value="private-revision")
    service.networking_v1 = Mock()
    service.core_v1 = Mock()
    service.networking_v1.list_namespaced_network_policy.return_value = SimpleNamespace(items=[])
    events = []
    service.networking_v1.create_namespaced_network_policy.side_effect = lambda **kw: events.append(kw["body"]["metadata"]["name"])
    service.core_v1.create_namespaced_pod.side_effect = lambda **kw: events.append("pod")
    service.core_v1.read_namespaced_pod.return_value = SimpleNamespace(status=SimpleNamespace(
        phase="Running", pod_ip="10.42.0.20", container_statuses=[SimpleNamespace(ready=True)] * 2,
        conditions=[SimpleNamespace(type="Ready", status="True")],
    ))
    name, _, _ = await service.provision_player_pod("session-a", "owner-a", "player", "10.8.0.10")
    assert events == ["isolate-player-sessions", "access-player-session-a", "pod"]
    service.core_v1.read_namespaced_pod.side_effect = ApiException(status=404)
    assert await service.delete_player_pod(name)
    service.networking_v1.delete_namespaced_network_policy.assert_called_once_with(
        name="access-player-session-a", namespace=settings.K8S_NAMESPACE,
    )


def test_gateway_rules_and_leases_fail_closed_on_expiry_and_revoke():
    guard = load_script("guard", "session_access.py")
    config = guard.validate_config(json.loads((ROOT / "infrastructure/openvpn/player-isolation.example.json").read_text()))
    table = guard.render_table(config)
    assert "flush ruleset" not in table
    assert 'iifname "tun0" drop' in table and 'oifname "tun0" drop' in table
    assert "ip saddr . ip daddr @active_pairs" in table
    state = guard.change_state(config, {}, "grant", "session-a", "10.8.0.10", "10.42.0.20", 200, now=100)
    with pytest.raises(ValueError, match="another session"):
        guard.change_state(config, state, "grant", "session-b", "10.8.0.11", "10.42.0.20", 200, now=100)
    with pytest.raises(ValueError, match="binding"):
        guard.change_state(config, state, "grant", "session-a", "10.8.0.10", "10.42.0.21", 200, now=100)
    with pytest.raises(ValueError, match="Revoke"):
        guard.change_state(config, state, "forget", "session-a", now=100)
    assert "timeout 100s" in guard.render_sets(config, state, now=100)
    expired = guard.render_sets(config, state, now=201)
    assert "add element inet mirrage_player_guard active_pairs" not in expired
    assert "10.42.0.20" in expired  # Keep an orphan sandbox blocked from the host.
    revoked = guard.change_state(config, state, "revoke", "session-a", now=100)
    with pytest.raises(ValueError, match="cannot be renewed"):
        guard.change_state(config, revoked, "renew", "session-a", "10.8.0.10", "10.42.0.20", 300, now=100)
    renewed = guard.change_state(config, state, "renew", "session-a", "10.8.0.10", "10.42.0.20", 300, now=100)
    stale = guard.change_state(config, renewed, "renew", "session-a", "10.8.0.10", "10.42.0.20", 250, now=100)
    assert stale["session-a"]["expires_at"] == 300
    assert "timeout" not in guard.render_sets(config, revoked, now=100)
    assert guard.change_state(config, revoked, "forget", "session-a", now=100) == {}
    with pytest.raises(ValueError):
        guard.change_state(config, {}, "grant", "session-a", "10.8.0.10", "169.254.169.254", 200, now=100)


@pytest.mark.asyncio
async def test_gateway_grant_failure_prevents_ready_and_cleans_pod(async_client, auth_headers, db_session, monkeypatch):
    gateway = SimpleNamespace(active=AsyncMock(return_value=True), grant=AsyncMock(side_effect=RuntimeError("not installed")),
                              revoke=AsyncMock(), forget=AsyncMock())
    monkeypatch.setattr(session_service, "_gateway", gateway)
    response = await async_client.post("/api/v1/session/start", headers=auth_headers)
    assert response.status_code == 500
    session = (await db_session.execute(select(GameSession))).scalars().one()
    assert session.status == SessionStatus.ERROR and not session.mirage_ip
    assert await k8s_provisioner.get_pod_status(session.pod_name) is None
    gateway.revoke.assert_awaited_once_with(session.id)


@pytest.mark.asyncio
async def test_failed_revoke_holds_slot_and_retries_before_pod_deletion(async_client, auth_headers, db_session, monkeypatch):
    gateway = SimpleNamespace(active=AsyncMock(return_value=True), grant=AsyncMock(), renew=AsyncMock(), revoke=AsyncMock(), forget=AsyncMock())
    monkeypatch.setattr(session_service, "_gateway", gateway)
    start = await async_client.post("/api/v1/session/start", headers=auth_headers)
    assert start.status_code == 201
    session = await db_session.get(GameSession, start.json()["session_id"])
    pod_name = session.pod_name
    gateway.revoke.side_effect = RuntimeError("gateway unavailable")
    stop = await async_client.post("/api/v1/session/stop", headers=auth_headers)
    assert stop.status_code == 503 and stop.json()["code"] == "SESSION_CLEANUP_PENDING"
    await db_session.refresh(session)
    assert session.status == SessionStatus.STOPPING and session.mirage_ip is None
    assert await k8s_provisioner.get_pod_status(pod_name) is not None
    slots = await session_service.get_active_slots_info(db_session)
    assert slots.active_slots == 1
    gateway.revoke.side_effect = None
    await session_service.cleanup_expired_sessions(db_session)
    await db_session.refresh(session)
    assert session.status == SessionStatus.TERMINATED
    assert await k8s_provisioner.get_pod_status(pod_name) is None
    gateway.forget.assert_awaited_once_with(session.id)


@pytest.mark.asyncio
async def test_extension_persists_expiry_before_renewing_gateway(async_client, auth_headers, db_session, monkeypatch):
    gateway = SimpleNamespace(active=AsyncMock(return_value=True), grant=AsyncMock(), renew=AsyncMock(), revoke=AsyncMock(), forget=AsyncMock())
    monkeypatch.setattr(session_service, "_gateway", gateway)
    started = await async_client.post("/api/v1/session/start", headers=auth_headers)
    session = await db_session.get(GameSession, started.json()["session_id"])
    old_expiry = session.expires_at
    extended = await async_client.post("/api/v1/session/extend", headers=auth_headers)
    assert extended.status_code == 200
    await db_session.refresh(session)
    assert session.expires_at.replace(tzinfo=None) == old_expiry.replace(tzinfo=None) + timedelta(hours=1)
    assert gateway.grant.await_count == 1 and gateway.renew.await_count == 1
    renewed = gateway.renew.call_args.args
    assert renewed[:3] == (session.id, session.player_vpn_ip, session.pod_ip)
    assert renewed[3].replace(tzinfo=None) == session.expires_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_failed_renewal_closes_session_without_reverting_committed_expiry(
    async_client, auth_headers, db_session, monkeypatch
):
    gateway = SimpleNamespace(active=AsyncMock(return_value=True), grant=AsyncMock(), renew=AsyncMock(side_effect=RuntimeError("failed")),
                              revoke=AsyncMock(), forget=AsyncMock())
    monkeypatch.setattr(session_service, "_gateway", gateway)
    started = await async_client.post("/api/v1/session/start", headers=auth_headers)
    session = await db_session.get(GameSession, started.json()["session_id"])
    old_expiry = session.expires_at
    response = await async_client.post("/api/v1/session/extend", headers=auth_headers)
    assert response.status_code == 503
    await db_session.refresh(session)
    assert session.status == SessionStatus.STOPPING and session.mirage_ip is None
    assert session.expires_at.replace(tzinfo=None) == old_expiry.replace(tzinfo=None) + timedelta(hours=1)
    gateway.revoke.assert_awaited_once_with(session.id)
    await session_service.cleanup_expired_sessions(db_session)
    assert session.status == SessionStatus.TERMINATED


def test_kubeconfig_failure_does_not_fall_back_to_cluster_admin(monkeypatch):
    from kubernetes import config
    monkeypatch.setattr(settings, "K8S_IN_CLUSTER", False)
    monkeypatch.setattr(settings, "K8S_KUBECONFIG_PATH", "/missing/controller-config")
    loader = Mock(side_effect=config.ConfigException("missing"))
    monkeypatch.setattr(config, "load_kube_config", loader)
    with pytest.raises(config.ConfigException):
        ProductionKubernetesService()
    loader.assert_called_once_with(config_file="/missing/controller-config")
