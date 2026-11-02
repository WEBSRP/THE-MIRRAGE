import asyncio
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class KubernetesService(ABC):
    @abstractmethod
    async def provision_player_pod(self, session_id: str, user_id: str, username: str) -> Tuple[str, str, str]:
        """Returns (pod_name, mirage_ip, ctf_ip)"""
        pass
    
    @abstractmethod
    async def delete_player_pod(self, pod_name: str) -> bool:
        pass
    
    @abstractmethod
    async def get_pod_status(self, pod_name: str) -> Optional[dict]:
        pass

class ProductionKubernetesService(KubernetesService):
    def __init__(self):
        loaded = False
        kubeconfig_path = getattr(settings, "K8S_KUBECONFIG_PATH", None)
        if kubeconfig_path:
            kubeconfig_path = os.path.expanduser(kubeconfig_path)
            if os.path.exists(kubeconfig_path):
                try:
                    config.load_kube_config(config_file=kubeconfig_path)
                    loaded = True
                except Exception as e:
                    logger.warning(f"Could not load kubeconfig from {kubeconfig_path}: {e}")
        if not loaded:
            for default_path in [os.path.expanduser("~/.kube/config"), "/etc/rancher/k3s/k3s.yaml"]:
                if os.path.exists(default_path):
                    try:
                        config.load_kube_config(config_file=default_path)
                        loaded = True
                        break
                    except Exception:
                        pass
        if not loaded:
            try:
                config.load_incluster_config()
                loaded = True
            except config.ConfigException:
                pass
        if not loaded:
            try:
                config.load_kube_config()
                loaded = True
            except config.ConfigException:
                logger.warning("Could not load Kubernetes configuration. K8s features will fail.")
        
        self.core_v1 = client.CoreV1Api()
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
    
    async def provision_player_pod(self, session_id: str, user_id: str, username: str) -> Tuple[str, str, str]:
        self._ensure_namespace_and_sa()
        pod_name = f"player-{session_id.lower()}-{int(time.time())}"
        
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
            tcp_socket=client.V1TCPSocketAction(port=80),
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
                containers=[mirage_container, ctf_container],
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
            self.core_v1.create_namespaced_pod(namespace=self.namespace, body=pod)
            logger.info(f"Created pod {pod_name} in namespace {self.namespace}")
        except ApiException as e:
            logger.error(f"Exception when creating pod: {e}")
            raise

        for _ in range(60):
            try:
                current_pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
                phase = current_pod.status.phase
                pod_ip = current_pod.status.pod_ip
                if phase == "Running" and pod_ip:
                    conditions = current_pod.status.conditions or []
                    ready_cond = any(c.type == "Ready" and c.status == "True" for c in conditions)
                    c_statuses = current_pod.status.container_statuses or []
                    all_c_ready = len(c_statuses) >= 2 and all(cs.ready for cs in c_statuses)

                    if ready_cond and all_c_ready:
                        logger.info(f"Pod {pod_name} is running and ready with IP {pod_ip}")
                        return pod_name, pod_ip, pod_ip
                elif phase in ("Failed", "Unknown"):
                    raise RuntimeError(f"Pod {pod_name} entered terminal phase: {phase}")
                await asyncio.sleep(2)
            except ApiException as e:
                logger.error(f"Error checking pod status: {e}")
                await asyncio.sleep(2)
        
        raise TimeoutError(f"Pod {pod_name} did not become ready in time.")
    
    async def delete_player_pod(self, pod_name: str) -> bool:
        try:
            self.core_v1.delete_namespaced_pod(
                name=pod_name, 
                namespace=self.namespace,
                body=client.V1DeleteOptions(grace_period_seconds=0)
            )
            logger.info(f"Deleted pod {pod_name}")
            return True
        except ApiException as e:
            if e.status == 404:
                return True
            logger.error(f"Exception when deleting pod: {e}")
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
    simulate_creation_failure: bool = False
    simulate_readiness_timeout: bool = False
    simulate_deletion_failure: bool = False

    def __init__(self):
        self.pods: Dict[str, Dict[str, Any]] = {}
        self._next_ip = 10
    
    async def provision_player_pod(self, session_id: str, user_id: str, username: str) -> Tuple[str, str, str]:
        if self.simulate_creation_failure:
            raise RuntimeError("Simulated creation failure")
            
        pod_name = f"mock-player-{session_id.lower()}-{int(time.time())}"
        
        self.pods[pod_name] = {
            "phase": "Creating",
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
