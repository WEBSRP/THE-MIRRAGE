import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from backend.app.core.config import settings
from backend.app.core.flags import get_shared_flags
from backend.app.services.session_resources import SessionInventory, identify_resource
from backend.app.core.networking import (
    DEFAULT_DENY_NAME, default_deny_policy, normalize_spec, player_network_policy,
)

logger = logging.getLogger(__name__)

class KubernetesService(ABC):
    @abstractmethod
    async def list_session_resources(self) -> SessionInventory:
        """List the configured namespace completely; partial reads must raise."""
        pass

    @abstractmethod
    async def delete_session_resource(self, resource) -> bool:
        """Delete only the observed UID/version and confirm its absence."""
        pass

    def pod_name(self, session_id: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]{1,100}", session_id):
            raise ValueError("Invalid session identifier")
        return f"player-{session_id}"

    @abstractmethod
    async def provision_player_pod(self, session_id: str, user_id: str, username: str, player_vpn_ip: Optional[str] = None) -> Tuple[str, str, str]:
        """Returns (pod_name, mirage_ip, ctf_ip)"""
        pass
    
    @abstractmethod
    async def delete_player_pod(self, pod_name: str) -> bool:
        pass
    
    @abstractmethod
    async def get_pod_status(self, pod_name: str) -> Optional[dict]:
        pass

class ProductionKubernetesService(KubernetesService):
    async def list_session_resources(self):
        def inventory():
            resources, occupied, ignored = [], set(), 0
            api = client.ApiClient()
            for kind, listing in (("Pod", self.core_v1.list_namespaced_pod),
                                  ("NetworkPolicy", self.networking_v1.list_namespaced_network_policy)):
                token = None
                while True:
                    page = listing(namespace=self.namespace, limit=200, _continue=token,
                                   _request_timeout=(3, 10))
                    for item in page.items:
                        data = api.sanitize_for_serialization(item)
                        metadata = data.get("metadata") or {}
                        ip = (data.get("status") or {}).get("podIP") if kind == "Pod" else None
                        if ip:
                            occupied.add(ip)  # Include unrelated/ambiguous pods when retaining source blocks.
                        resource = (identify_resource(kind, metadata, self.pod_name, ip)
                                    if metadata.get("namespace") == self.namespace else None)
                        if resource:
                            resources.append(resource)
                        else:
                            ignored += 1
                    token = page.metadata._continue
                    if not token:
                        break
            return SessionInventory(tuple(resources), frozenset(occupied), ignored)
        return await asyncio.to_thread(inventory)

    async def delete_session_resource(self, resource):
        if resource.kind == "Pod":
            read, delete = self.core_v1.read_namespaced_pod, self.core_v1.delete_namespaced_pod
        elif resource.kind == "NetworkPolicy":
            read = self.networking_v1.read_namespaced_network_policy
            delete = self.networking_v1.delete_namespaced_network_policy
        else:
            return False
        try:
            try:
                current = await asyncio.to_thread(read, name=resource.name, namespace=self.namespace,
                                                  _request_timeout=(3, 10))
            except ApiException as error:
                if error.status == 404:
                    return True
                raise
            data = client.ApiClient().sanitize_for_serialization(current)
            metadata = data.get("metadata") or {}
            observed = identify_resource(resource.kind, metadata, self.pod_name, resource.pod_ip)
            if metadata.get("namespace") != self.namespace or observed != resource:
                return False  # Changed labels, UID or version: rescan; never delete a replacement.
            options = client.V1DeleteOptions(preconditions=client.V1Preconditions(
                uid=resource.uid, resource_version=resource.resource_version,
            ), grace_period_seconds=30 if resource.kind == "Pod" else None)
            try:
                await asyncio.to_thread(delete, name=resource.name, namespace=self.namespace,
                                        body=options, _request_timeout=(3, 10))
            except ApiException as error:
                if error.status == 404:
                    return True
                raise
            for _ in range(20):
                try:
                    await asyncio.to_thread(read, name=resource.name, namespace=self.namespace,
                                            _request_timeout=(3, 10))
                except ApiException as error:
                    if error.status == 404:
                        return True
                    raise
                await asyncio.sleep(0.25)
            return False
        except ApiException:
            logger.warning("Conditional resource cleanup pending: %s", resource.name)
            return False

    def __init__(self):
        # Never fall back to the node's cluster-admin credentials when the
        # configured controller identity is missing or invalid.
        if settings.K8S_IN_CLUSTER:
            config.load_incluster_config()
        else:
            config.load_kube_config(config_file=os.path.expanduser(settings.K8S_KUBECONFIG_PATH))
        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.namespace = settings.K8S_NAMESPACE

    def _ensure_namespace_and_sa(self):
        try:
            self.core_v1.read_namespace(name=self.namespace)
        except ApiException as e:
            if e.status == 404:
                try:
                    ns_body = client.V1Namespace(
                        metadata=client.V1ObjectMeta(
                            name=self.namespace,
                            labels={
                                "app.kubernetes.io/name": "mirrage-sessions",
                                "mirrage.io/purpose": "player-sandboxes"
                            }
                        )
                    )
                    self.core_v1.create_namespace(body=ns_body)
                    logger.info(f"Created namespace {self.namespace}")
                except ApiException as create_err:
                    if create_err.status != 409:
                        raise
            else:
                raise

        try:
            self.core_v1.read_namespaced_service_account(name="mirrage-player-sandbox", namespace=self.namespace)
        except ApiException as e:
            if e.status == 404:
                try:
                    sa_body = client.V1ServiceAccount(
                        metadata=client.V1ObjectMeta(
                            name="mirrage-player-sandbox",
                            namespace=self.namespace
                        )
                    )
                    self.core_v1.create_namespaced_service_account(namespace=self.namespace, body=sa_body)
                    logger.info(f"Created serviceaccount mirrage-player-sandbox in {self.namespace}")
                except ApiException as sa_err:
                    if sa_err.status != 409:
                        raise
            else:
                raise
    
    def _ensure_network_boundary(self) -> None:
        """Reject additive broad permissions instead of silently trusting /32 rules."""
        existing = self.networking_v1.list_namespaced_network_policy(namespace=self.namespace).items
        found_default = False
        for policy in existing:
            serialized = client.ApiClient().sanitize_for_serialization(policy)
            meta = serialized["metadata"]
            if meta["name"] == DEFAULT_DENY_NAME:
                expected = default_deny_policy()
                found_default = True
            else:
                labels = meta.get("labels") or {}
                annotations = meta.get("annotations") or {}
                if labels.get("mirrage.io/purpose") != "player-access" or not meta["name"].startswith("access-"):
                    raise RuntimeError("Unexpected NetworkPolicy: remove broad permissions before provisioning")
                try:
                    expected = player_network_policy(
                        meta["name"][7:], labels["mirrage.io/session-id"],
                        labels["mirrage.io/user-id"], annotations["mirrage.io/vpn-ip"],
                    )
                except (KeyError, ValueError):
                    raise RuntimeError("Invalid player NetworkPolicy") from None
            if normalize_spec(serialized["spec"]) != normalize_spec(expected["spec"]):
                raise RuntimeError("Unsafe NetworkPolicy: apply the default-deny/session policy migration first")
        if not found_default:
            try:
                self.networking_v1.create_namespaced_network_policy(namespace=self.namespace, body=default_deny_policy())
            except ApiException as error:
                if error.status != 409:
                    raise
                # Another worker installed it. Re-read and verify, never assume.
                self._ensure_network_boundary()

    def _create_player_policy(self, pod_name, session_id, user_id, vpn_ip):
        desired = player_network_policy(pod_name, session_id, user_id, vpn_ip)
        self.networking_v1.create_namespaced_network_policy(namespace=self.namespace, body=desired)

    def _ensure_flags_secret(self) -> str:
        """Immutable revision, shared across players; never put flags in pod env."""
        flags = get_shared_flags()
        content = json.dumps(flags, sort_keys=True, separators=(",", ":"))
        revision = hashlib.sha256(content.encode()).hexdigest()[:24]
        name = f"mirrage-ctf-flags-{revision}"
        try:
            existing = self.core_v1.read_namespaced_secret(name=name, namespace=self.namespace)
        except ApiException as exc:
            if exc.status != 404:
                raise
            body = client.V1Secret(
                metadata=client.V1ObjectMeta(name=name, labels={"mirrage.io/purpose": "ctf-flags"}),
                type="Opaque", immutable=True, string_data={"flags.json": content},
            )
            try:
                self.core_v1.create_namespaced_secret(namespace=self.namespace, body=body)
                return name
            except ApiException as create_exc:
                if create_exc.status != 409:
                    # Do not surface an API error body that might include submitted data.
                    raise RuntimeError("Cannot create CTF flag Secret") from None
                existing = self.core_v1.read_namespaced_secret(name=name, namespace=self.namespace)
        try:
            actual = json.loads(base64.b64decode(existing.data["flags.json"]).decode())
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise RuntimeError("Invalid CTF flag Secret") from None
        if actual != flags:
            raise RuntimeError("CTF flag Secret does not match configured verifiers")
        return name

    async def provision_player_pod(self, session_id: str, user_id: str, username: str, player_vpn_ip: Optional[str] = None) -> Tuple[str, str, str]:
        if player_vpn_ip is None:
            raise ValueError("A reserved VPN IP is required before provisioning")
        pod_name = self.pod_name(session_id)
        self._ensure_namespace_and_sa()
        await asyncio.to_thread(self._ensure_network_boundary)
        flags_secret = await asyncio.to_thread(self._ensure_flags_secret)
        await asyncio.to_thread(self._create_player_policy, pod_name, session_id, user_id, player_vpn_ip)
        
        container_security_context = client.V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=client.V1Capabilities(
                drop=["ALL"],
                add=[
                    "SYS_CHROOT",
                    "SETUID",
                    "SETGID",
                    "CHOWN",
                    "DAC_OVERRIDE",
                    "FOWNER",
                    "KILL",
                    "AUDIT_WRITE",
                    "NET_BIND_SERVICE",
                ]
            ),
            read_only_root_filesystem=False,
            run_as_non_root=False
        )
        
        pod_security_context = client.V1PodSecurityContext(
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault")
        )

        mirage_readiness = client.V1Probe(
            tcp_socket=client.V1TCPSocketAction(port=2222),
            initial_delay_seconds=2,
            period_seconds=2,
            failure_threshold=15
        )
        ctf_readiness = client.V1Probe(
            http_get=client.V1HTTPGetAction(path="/_health", port=80),
            initial_delay_seconds=2,
            period_seconds=2,
            failure_threshold=15
        )

        mirage_container = client.V1Container(
            name="mirage",
            image=settings.MIRAGE_CONTAINER_IMAGE,
            image_pull_policy="IfNotPresent",
            resources=client.V1ResourceRequirements(
                limits={"cpu": "200m", "memory": "256Mi"}
            ),
            security_context=container_security_context,
            readiness_probe=mirage_readiness,
            ports=[
                client.V1ContainerPort(container_port=2222, name="mirage-ssh")
            ],
            env=[
                client.V1EnvVar(name="USERNAME", value=username)
            ]
        )
        
        ctf_container = client.V1Container(
            name="ctf",
            image=settings.CTF_CONTAINER_IMAGE,
            image_pull_policy="IfNotPresent",
            resources=client.V1ResourceRequirements(
                limits={"cpu": "300m", "memory": "512Mi"}
            ),
            security_context=container_security_context,
            readiness_probe=ctf_readiness,
            env=[client.V1EnvVar(name="CTF_DEVELOPER_SSH_PUBLIC_KEY", value=settings.CTF_DEVELOPER_SSH_PUBLIC_KEY)],
            volume_mounts=[client.V1VolumeMount(
                name="ctf-flags", mount_path="/run/mirrage-flags", read_only=True
            )],
            ports=[
                client.V1ContainerPort(container_port=22, name="ctf-ssh"),
                client.V1ContainerPort(container_port=80, name="ctf-http")
            ]
        )
        
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels={
                    "app": "mirrage-session",
                    "app.kubernetes.io/name": "mirrage-session",
                    "session": str(session_id),
                    "mirrage.io/session-id": str(session_id),
                    "mirrage.io/user-id": str(user_id)
                }
            ),
            spec=client.V1PodSpec(
                node_name=settings.K8S_SESSION_NODE_NAME or None,
                containers=[mirage_container, ctf_container],
                volumes=[client.V1Volume(name="ctf-flags", secret=client.V1SecretVolumeSource(
                    secret_name=flags_secret, default_mode=0o400
                ))],
                restart_policy="Never",
                service_account_name="mirrage-player-sandbox",
                automount_service_account_token=False,
                host_network=False,
                host_pid=False,
                host_ipc=False,
                security_context=pod_security_context
            )
        )
        
        try:
            created = self.core_v1.create_namespaced_pod(namespace=self.namespace, body=pod)
            uid = getattr(getattr(created, "metadata", None), "uid", None)
            if isinstance(uid, str) and uid:
                self.networking_v1.patch_namespaced_network_policy(
                    name=f"access-{pod_name}", namespace=self.namespace,
                    body={"metadata": {"ownerReferences": [{"apiVersion": "v1", "kind": "Pod",
                           "name": pod_name, "uid": uid}]}},
                )
            for _ in range(60):
                current = self.core_v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
                if current.status.phase in ("Failed", "Unknown"):
                    raise RuntimeError("Player pod entered a terminal phase")
                statuses = current.status.container_statuses or []
                ready = any(c.type == "Ready" and c.status == "True" for c in current.status.conditions or [])
                if (current.status.phase == "Running" and current.status.pod_ip and ready
                        and len(statuses) >= 2 and all(status.ready for status in statuses)):
                    return pod_name, current.status.pod_ip, current.status.pod_ip
                await asyncio.sleep(2)
            raise TimeoutError("Player pod did not become ready in time")
        except BaseException:
            # Deterministic identity is also persisted by SessionService for retries.
            await asyncio.shield(self.delete_player_pod(pod_name))
            raise

    async def delete_player_pod(self, pod_name: str) -> bool:
        try:
            try:
                self.core_v1.delete_namespaced_pod(
                    name=pod_name, namespace=self.namespace,
                    body=client.V1DeleteOptions(grace_period_seconds=30),
                )
            except ApiException as error:
                if error.status != 404:
                    raise
            for _ in range(20):
                try:
                    self.core_v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
                except ApiException as error:
                    if error.status == 404:
                        break
                    raise
                await asyncio.sleep(0.25)
            else:
                return False
            try:
                self.networking_v1.delete_namespaced_network_policy(
                    name=f"access-{pod_name}", namespace=self.namespace,
                )
            except ApiException as error:
                if error.status != 404:
                    raise
            return True
        except ApiException:
            logger.error("Unable to confirm player pod/policy removal: %s", pod_name)
            return False

    async def get_pod_status(self, pod_name: str) -> Optional[dict]:
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            conditions = pod.status.conditions or []
            ready_cond = any(c.type == "Ready" and c.status == "True" for c in conditions)
            c_statuses = pod.status.container_statuses or []
            all_c_ready = len(c_statuses) >= 2 and all(cs.ready for cs in c_statuses)
            is_ready = (pod.status.phase == "Running") and bool(pod.status.pod_ip) and ready_cond and all_c_ready

            labels = pod.metadata.labels or {}
            session_id = labels.get("mirrage.io/session-id") or labels.get("session")
            user_id = labels.get("mirrage.io/user-id")

            return {
                "phase": pod.status.phase,
                "ip": pod.status.pod_ip,
                "ready": is_ready,
                "start_time": pod.status.start_time,
                "labels": labels,
                "session_id": session_id,
                "user_id": user_id,
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Exception reading pod status: {e}")
            raise


class MockKubernetesService(KubernetesService):
    def pod_name(self, session_id: str) -> str:
        return "mock-" + super().pod_name(session_id)

    simulate_creation_failure: bool = False
    simulate_readiness_timeout: bool = False
    simulate_deletion_failure: bool = False

    def __init__(self):
        self.pods: Dict[str, Dict[str, Any]] = {}
        self.policies = {}
        self._next_ip = 10

    def _mock_metadata(self, name, labels):
        return {"name": name, "namespace": settings.K8S_NAMESPACE, "labels": dict(labels),
                "uid": str(uuid.uuid4()), "resourceVersion": "1"}

    async def list_session_resources(self):
        resources, occupied, ignored = [], set(), 0
        for kind, entries in (("Pod", self.pods), ("NetworkPolicy", self.policies)):
            for name, data in entries.items():
                ip = data.get("ip") if kind == "Pod" else None
                if ip:
                    occupied.add(ip)
                resource = identify_resource(kind, data.get("metadata") or {}, self.pod_name, ip)
                if resource:
                    resources.append(resource)
                else:
                    ignored += 1
        return SessionInventory(tuple(resources), frozenset(occupied), ignored)

    async def delete_session_resource(self, resource):
        if self.simulate_deletion_failure:
            return False
        entries = self.pods if resource.kind == "Pod" else self.policies
        data = entries.get(resource.name)
        if data is None:
            return True
        current = identify_resource(resource.kind, data.get("metadata") or {}, self.pod_name,
                                    data.get("ip") if resource.kind == "Pod" else None)
        if current != resource:
            return False
        del entries[resource.name]
        return True
    
    async def provision_player_pod(self, session_id: str, user_id: str, username: str, player_vpn_ip: Optional[str] = None) -> Tuple[str, str, str]:
        if self.simulate_creation_failure:
            raise RuntimeError("Simulated creation failure")
            
        pod_name = self.pod_name(session_id)
        
        self.pods[pod_name] = {
            "phase": "Creating",
            "player_vpn_ip": player_vpn_ip,
            "ip": None,
            "ready": False,
            "start_time": time.time(),
            "labels": {
                "app": "mirrage-session",
                "app.kubernetes.io/name": "mirrage-session",
                "session": str(session_id),
                "mirrage.io/session-id": str(session_id),
                "mirrage.io/user-id": str(user_id),
            },
            "session_id": str(session_id),
            "user_id": str(user_id),
        }
        labels = self.pods[pod_name]["labels"]
        self.pods[pod_name]["metadata"] = self._mock_metadata(pod_name, labels)
        self.policies["access-" + pod_name] = {"metadata": self._mock_metadata(
            "access-" + pod_name, {**labels, "mirrage.io/purpose": "player-access"})}
        
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.3, 0.5))
        
        if self.simulate_readiness_timeout:
            self.pods[pod_name]["phase"] = "Failed"
            self.pods[pod_name]["ready"] = False
            raise TimeoutError(f"Pod {pod_name} did not become ready in time.")
            
        ip = f"10.42.0.{self._next_ip}"
        self._next_ip += 1
        
        self.pods[pod_name].update({
            "phase": "Running",
            "ip": ip,
            "ready": True,
        })
        
        logger.info(f"Mock provisioned pod {pod_name} with IP {ip}")
        return pod_name, ip, ip
        
    async def delete_player_pod(self, pod_name: str) -> bool:
        if self.simulate_deletion_failure:
            return False
            
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.1, 0.2))
        
        self.policies.pop("access-" + pod_name, None)
        if pod_name in self.pods:
            self.pods[pod_name]["phase"] = "Terminated"
            self.pods[pod_name]["ready"] = False
            del self.pods[pod_name]
            logger.info(f"Mock deleted pod {pod_name}")
            return True
            
        logger.info(f"Mock pod {pod_name} already deleted or not found")
        return True
        
    async def get_pod_status(self, pod_name: str) -> Optional[dict]:
        return self.pods.get(pod_name)


def get_k8s_service() -> KubernetesService:
    from backend.app.core.config import settings
    if getattr(settings, "K8S_MODE", "mock").lower() == "production":
        return ProductionKubernetesService()
    return MockKubernetesService()

k8s_provisioner = get_k8s_service()
