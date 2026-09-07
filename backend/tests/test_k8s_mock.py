"""
MIRRAGE Mock Kubernetes Service Tests

Verifies PHASE 4 requirements:
- Fully functional local mock without real k3s/Kubernetes
- Sequential IP allocation from 10.42.0.0/24 subnet
- Pod status inspection
- Failure simulation modes (creation failure, readiness timeout, deletion failure)
- Idempotent pod deletion
"""
import pytest
from backend.app.services.k8s_service import MockKubernetesService


@pytest.mark.asyncio
async def test_mock_k8s_pod_lifecycle_and_ip_allocation():
    """Verify pod provisioning, IP allocation in 10.42.0.0/24, and deletion."""
    mock_k8s = MockKubernetesService()

    # 1. Provision Pod 1
    pod1, mirage_ip1, ctf_ip1 = await mock_k8s.provision_player_pod(
        session_id="session-test-01",
        user_id="user-01",
        username="operative_alpha",
    )
    assert pod1.startswith("mock-player-")
    assert mirage_ip1.startswith("10.42.0.")
    assert ctf_ip1 == mirage_ip1

    # 2. Check pod status
    status = await mock_k8s.get_pod_status(pod1)
    assert status is not None
    assert status["phase"] == "Running"
    assert status["ip"] == mirage_ip1

    # 3. Provision Pod 2 -> sequential IP allocation
    pod2, mirage_ip2, _ = await mock_k8s.provision_player_pod(
        session_id="session-test-02",
        user_id="user-02",
        username="operative_beta",
    )
    assert mirage_ip1 != mirage_ip2
    assert mirage_ip2.startswith("10.42.0.")

    # 4. Delete Pod 1
    del_ok = await mock_k8s.delete_player_pod(pod1)
    assert del_ok is True

    # 5. Idempotent deletion: deleting already-deleted pod returns True
    del_again = await mock_k8s.delete_player_pod(pod1)
    assert del_again is True

    # 6. Status of deleted pod is None
    assert await mock_k8s.get_pod_status(pod1) is None


@pytest.mark.asyncio
async def test_mock_k8s_failure_simulations():
    """Verify mock failure injection modes."""
    mock_k8s = MockKubernetesService()

    # Test 1: Creation failure
    mock_k8s.simulate_creation_failure = True
    with pytest.raises(RuntimeError, match="Simulated creation failure"):
        await mock_k8s.provision_player_pod("session-fail", "user-01", "operative")
    mock_k8s.simulate_creation_failure = False

    # Test 2: Readiness timeout
    mock_k8s.simulate_readiness_timeout = True
    with pytest.raises(TimeoutError, match="did not become ready"):
        await mock_k8s.provision_player_pod("session-timeout", "user-01", "operative")
    mock_k8s.simulate_readiness_timeout = False

    # Test 3: Deletion failure
    pod_name, _, _ = await mock_k8s.provision_player_pod("session-ok", "user-01", "operative")
    mock_k8s.simulate_deletion_failure = True
    del_res = await mock_k8s.delete_player_pod(pod_name)
    assert del_res is False
    mock_k8s.simulate_deletion_failure = False
