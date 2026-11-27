import asyncio
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

from kubernetes import client
from kubernetes.client.rest import ApiException
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.models.session import GameSession, SessionStatus
from backend.app.models.user import User
from backend.app.services.k8s_service import MockKubernetesService, ProductionKubernetesService
from backend.app.services.orphan_cleanup import OrphanCleanupService
from backend.app.services.session_gateway import MockSessionGateway


@pytest_asyncio.fixture
async def environment(monkeypatch):
    k8s, gateway = MockKubernetesService(), MockSessionGateway()
    controller = SimpleNamespace(k8s_provisioner=k8s, gateway=gateway)
    # Tests exercise orchestration; a network delay adds no additional coverage.
    async def no_delay(*args):
        pass
    monkeypatch.setattr("backend.app.services.k8s_service.asyncio.sleep", no_delay)
    return k8s, gateway, controller


async def provision(environment, session_id="session-orphan", owner="deleted-owner"):
    k8s, gateway, _ = environment
    name, ip, _ = await k8s.provision_player_pod(session_id, owner, "test", "10.8.0.10")
    await gateway.grant(session_id, "10.8.0.10", ip, datetime.now(timezone.utc) + timedelta(minutes=30))
    return name


@pytest.mark.asyncio
async def test_lost_database_row_cleanup_survives_controller_restart_and_keeps_live_player(
    db_session, test_user, environment
):
    k8s, gateway, controller = environment
    orphan = await provision(environment)
    live_name = await provision(environment, "session-live", test_user.id)
    db_session.add(GameSession(id="session-live", user_id=test_user.id, status=SessionStatus.READY,
        pod_name=live_name, pod_namespace=settings.K8S_NAMESPACE, pod_ip=k8s.pods[live_name]["ip"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=20)))
    await db_session.commit()
    result = await OrphanCleanupService(controller).sweep(db_session)
    assert result["cleaned"] == 1 and result["preserved"] == 1 and result["pending"] == 0
    assert orphan not in k8s.pods and "access-" + orphan not in k8s.policies
    assert set(gateway.bindings) == {"session-live"} and live_name in k8s.pods
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("remaining", ["policy", "gateway", "pod"])
async def test_partial_resource_orphans_are_discovered_without_any_database_row(db_session, environment, remaining):
    k8s, gateway, controller = environment
    name = await provision(environment)
    if remaining != "pod":
        k8s.pods.clear()
    if remaining != "policy":
        k8s.policies.clear()
    if remaining != "gateway":
        gateway.bindings.clear()
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 1
    assert not k8s.pods and not k8s.policies and not gateway.bindings


@pytest.mark.asyncio
async def test_failed_deletion_retains_policy_and_block_then_new_worker_retries(db_session, environment):
    k8s, gateway, controller = environment
    name = await provision(environment)
    k8s.simulate_deletion_failure = True
    result = await OrphanCleanupService(controller).sweep(db_session)
    assert result["pending"] == 1 and name in k8s.pods and "access-" + name in k8s.policies
    assert gateway.bindings["session-orphan"][2].timestamp() == 0
    k8s.simulate_deletion_failure = False
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 1
    assert not gateway.bindings and not k8s.pods


@pytest.mark.asyncio
async def test_revoke_failure_prevents_deletion_and_forget_failure_is_retryable(db_session, environment, monkeypatch):
    k8s, gateway, controller = environment
    name = await provision(environment)
    real_revoke, real_forget = gateway.revoke, gateway.forget
    monkeypatch.setattr(gateway, "revoke", AsyncMock(side_effect=RuntimeError("unavailable")))
    assert (await OrphanCleanupService(controller).sweep(db_session))["pending"] == 1
    assert name in k8s.pods
    monkeypatch.setattr(gateway, "revoke", real_revoke)
    monkeypatch.setattr(gateway, "forget", AsyncMock(side_effect=RuntimeError("unavailable")))
    assert (await OrphanCleanupService(controller).sweep(db_session))["pending"] == 1
    assert not k8s.pods and gateway.bindings["session-orphan"][2].timestamp() == 0
    monkeypatch.setattr(gateway, "forget", real_forget)
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [SessionStatus.EXPIRED, SessionStatus.ERROR, SessionStatus.READY])
async def test_inactive_or_expired_database_rows_cannot_hide_surviving_resources(
    db_session, test_user, environment, status
):
    k8s, gateway, controller = environment
    name = await provision(environment, owner=test_user.id)
    row = GameSession(id="session-orphan", user_id=test_user.id, status=status,
        pod_name=name, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    db_session.add(row)
    await db_session.commit()
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 1
    await db_session.refresh(row)
    assert row.status == (SessionStatus.EXPIRED if status == SessionStatus.READY else status)
    assert not k8s.pods and not gateway.bindings


@pytest.mark.asyncio
async def test_failed_cleanup_persists_stopping_barrier(db_session, test_user, environment):
    k8s, _, controller = environment
    name = await provision(environment, owner=test_user.id)
    row = GameSession(id="session-orphan", user_id=test_user.id, status=SessionStatus.READY,
        pod_name=name, pod_ip=k8s.pods[name]["ip"], expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    db_session.add(row)
    await db_session.commit()
    k8s.simulate_deletion_failure = True
    assert (await OrphanCleanupService(controller).sweep(db_session))["pending"] == 1
    await db_session.refresh(row)
    assert row.status == SessionStatus.STOPPING and row.pod_ip is None


@pytest.mark.asyncio
async def test_initialization_grace_preserves_inflight_start_then_cleans_stale_start(
    db_session, test_user, environment
):
    k8s, gateway, controller = environment
    name = await provision(environment, owner=test_user.id)
    row = GameSession(id="session-orphan", user_id=test_user.id, status=SessionStatus.INITIALIZING,
        created_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
    db_session.add(row)
    await db_session.commit()
    assert (await OrphanCleanupService(controller).sweep(db_session))["preserved"] == 1
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    await db_session.commit()
    assert (await OrphanCleanupService(controller).sweep(db_session))["cleaned"] == 1
    assert name not in k8s.pods and not gateway.bindings


@pytest.mark.asyncio
async def test_unrelated_and_mislabeled_resources_are_preserved_and_block_not_forgotten(db_session, environment):
    k8s, gateway, controller = environment
    name = await provision(environment)
    # Keep the same occupied IP but remove ownership proof. Never delete by name alone.
    k8s.pods[name]["metadata"]["labels"].pop("mirrage.io/user-id")
    assert (await OrphanCleanupService(controller).sweep(db_session))["pending"] == 1
    assert name in k8s.pods and gateway.bindings["session-orphan"][2].timestamp() == 0


@pytest.mark.asyncio
async def test_partial_inventory_or_database_outage_cannot_trigger_deletion(db_session, environment, monkeypatch):
    k8s, gateway, controller = environment
    name = await provision(environment)
    real_inventory = k8s.list_session_resources
    monkeypatch.setattr(k8s, "list_session_resources", AsyncMock(side_effect=RuntimeError("list failed")))
    with pytest.raises(RuntimeError):
        await OrphanCleanupService(controller).sweep(db_session)
    assert name in k8s.pods and gateway.bindings["session-orphan"][2].timestamp() > 0
    monkeypatch.setattr(k8s, "list_session_resources", real_inventory)
    monkeypatch.setattr(db_session, "execute", AsyncMock(side_effect=RuntimeError("database down")))
    assert (await OrphanCleanupService(controller).sweep(db_session))["pending"] == 1
    assert name in k8s.pods and gateway.bindings["session-orphan"][2].timestamp() > 0


@pytest.mark.asyncio
async def test_legacy_sweep_removes_only_old_terminal_unbound_player_pods(db_session, test_user, environment):
    k8s, gateway, controller = environment
    now = datetime.now(timezone.utc)
    names = {}
    for index, case in enumerate(("eligible", "recent", "running", "unowned", "active", "leased")):
        session_id = f"session-{case}"
        name = f"{k8s.pod_name(session_id)}-1793612657"
        labels = {"app.kubernetes.io/name": "mirrage-player", "mirrage.io/session-id": session_id,
                  "mirrage.io/user-id": test_user.id}
        if case == "unowned":
            labels.pop("mirrage.io/user-id")
        metadata = k8s._mock_metadata(name, labels)
        metadata["creationTimestamp"] = (now - timedelta(days=0 if case == "recent" else 2)).isoformat()
        k8s.pods[name] = {"metadata": metadata, "phase": "Running" if case == "running" else "Failed",
                          "ip": f"10.42.0.{20 + index}"}
        names[case] = name
    db_session.add(GameSession(id="session-active", user_id=test_user.id, status=SessionStatus.READY,
                               pod_name=names["active"], expires_at=now + timedelta(minutes=30)))
    db_session.add(GameSession(id="session-leased", user_id=test_user.id, status=SessionStatus.READY,
                               pod_name=names["leased"], expires_at=now + timedelta(minutes=30)))
    await db_session.commit()
    await gateway.grant("session-leased", "10.8.0.10", k8s.pods[names["leased"]]["ip"],
                        now + timedelta(minutes=30))

    result = await OrphanCleanupService(controller).sweep(db_session)

    assert result["cleaned"] == 1 and result["pending"] == 0
    assert set(k8s.pods) == {name for case, name in names.items() if case != "eligible"}
    assert "session-leased" in gateway.bindings


def production_service():
    service = object.__new__(ProductionKubernetesService)
    service.namespace = settings.K8S_NAMESPACE
    service.core_v1, service.networking_v1 = Mock(), Mock()
    return service


def pod(name="player-session-a", uid="uid-original", version="7"):
    return client.V1Pod(metadata=client.V1ObjectMeta(name=name, uid=uid, resource_version=version,
        namespace=settings.K8S_NAMESPACE, labels={"app": "mirrage-session",
        "mirrage.io/session-id": "session-a", "mirrage.io/user-id": "owner-a"}),
        status=client.V1PodStatus(pod_ip="10.42.0.20"))


@pytest.mark.asyncio
async def test_production_inventory_paginates_and_never_mutates_on_partial_failure():
    service = production_service()
    service.core_v1.list_namespaced_pod.side_effect = [
        client.V1PodList(items=[pod()], metadata=client.V1ListMeta(_continue="next-page")),
        ApiException(status=503),
    ]
    with pytest.raises(ApiException):
        await service.list_session_resources()
    assert service.core_v1.list_namespaced_pod.call_args.kwargs["_continue"] == "next-page"
    service.core_v1.delete_namespaced_pod.assert_not_called()
    service.networking_v1.delete_namespaced_network_policy.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["uid", "version", "labels", "unchanged", "conflict", "forbidden"])
async def test_conditional_delete_rechecks_ownership_and_uses_server_preconditions(change):
    service = production_service()
    service.core_v1.list_namespaced_pod.return_value = client.V1PodList(items=[pod()], metadata=client.V1ListMeta())
    service.networking_v1.list_namespaced_network_policy.return_value = client.V1NetworkPolicyList(
        items=[], metadata=client.V1ListMeta())
    observed = (await service.list_session_resources()).resources[0]
    current = pod()
    if change == "uid":
        current.metadata.uid = "replacement"
    elif change == "version":
        current.metadata.resource_version = "8"
    elif change == "labels":
        current.metadata.labels.clear()
    service.core_v1.read_namespaced_pod.side_effect = [current, ApiException(status=404)]
    if change in ("conflict", "forbidden"):
        service.core_v1.delete_namespaced_pod.side_effect = ApiException(status=409 if change == "conflict" else 403)
    result = await service.delete_session_resource(observed)
    assert result == (change == "unchanged")
    if change in ("uid", "version", "labels"):
        service.core_v1.delete_namespaced_pod.assert_not_called()
    else:
        options = service.core_v1.delete_namespaced_pod.call_args.kwargs["body"]
        assert options.preconditions.uid == "uid-original" and options.preconditions.resource_version == "7"
        assert options.grace_period_seconds == 30


@pytest.mark.asyncio
async def test_delete_acknowledgement_without_pod_disappearance_is_not_success(monkeypatch):
    service = production_service()
    service.core_v1.list_namespaced_pod.return_value = client.V1PodList(items=[pod()], metadata=client.V1ListMeta())
    service.networking_v1.list_namespaced_network_policy.return_value = client.V1NetworkPolicyList(
        items=[], metadata=client.V1ListMeta())
    observed = (await service.list_session_resources()).resources[0]
    service.core_v1.read_namespaced_pod.return_value = pod()
    async def no_delay(*args):
        pass
    monkeypatch.setattr("backend.app.services.k8s_service.asyncio.sleep", no_delay)
    assert not await service.delete_session_resource(observed)
    service.networking_v1.delete_namespaced_network_policy.assert_not_called()


@pytest.mark.asyncio
async def test_policy_only_production_cleanup_is_scoped_and_conditional():
    service = production_service()
    metadata = pod().metadata
    metadata.name = "access-player-session-a"
    metadata.labels["mirrage.io/purpose"] = "player-access"
    policy = client.V1NetworkPolicy(metadata=metadata)
    service.core_v1.list_namespaced_pod.return_value = client.V1PodList(items=[], metadata=client.V1ListMeta())
    service.networking_v1.list_namespaced_network_policy.return_value = client.V1NetworkPolicyList(
        items=[policy], metadata=client.V1ListMeta())
    observed = (await service.list_session_resources()).resources[0]
    service.networking_v1.read_namespaced_network_policy.side_effect = [policy, ApiException(status=404)]
    assert await service.delete_session_resource(observed)
    request = service.networking_v1.delete_namespaced_network_policy.call_args.kwargs
    assert request["namespace"] == settings.K8S_NAMESPACE
    assert request["body"].preconditions.uid == metadata.uid
    service.core_v1.delete_namespaced_pod.assert_not_called()


@pytest.mark.asyncio
async def test_postgres_independent_sweepers_preserve_active_row_and_remove_orphan(environment):
    url = os.environ.get("MIRRAGE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requires disposable PostgreSQL")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        unique = uuid.uuid4().hex
        async with sessions() as db:
            owner = User(email=f"{unique}@example.com", username=unique)
            db.add(owner)
            await db.flush()
            await provision(environment, "session-pg-live", owner.id)
            db.add(GameSession(id="session-pg-live", user_id=owner.id, status=SessionStatus.READY,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=20)))
            await db.commit()
        await provision(environment)
        async def sweep():
            async with sessions() as db:
                return await OrphanCleanupService(environment[2]).sweep(db)
        results = await asyncio.gather(sweep(), sweep())
        assert all(result["pending"] == 0 for result in results)
        assert set(environment[1].bindings) == {"session-pg-live"}
        async with sessions() as db:
            assert (await db.execute(select(GameSession.status).where(
                GameSession.id == "session-pg-live"))).scalar_one() == SessionStatus.READY
    finally:
        await engine.dispose()
