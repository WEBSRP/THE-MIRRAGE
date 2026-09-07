import asyncio
import logging
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
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                logger.warning("Could not load Kubernetes configuration. K8s features will fail.")
        
        self.core_v1 = client.CoreV1Api()
        self.namespace = settings.K8S_NAMESPACE
    
    async def provision_player_pod(self, session_id: str, user_id: str, username: str) -> Tuple[str, str, str]:
        pod_name = f"player-{session_id.lower()}-{int(time.time())}"
        
        container_security_context = client.V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            read_only_root_filesystem=False,
            run_as_non_root=False
        )
        
        pod_security_context = client.V1PodSecurityContext(
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault")
        )

        mirage_container = client.V1Container(
            name="mirage",
            image=settings.MIRAGE_CONTAINER_IMAGE,
            image_pull_policy="IfNotPresent",
            resources=client.V1ResourceRequirements(
                limits={"cpu": "200m", "memory": "256Mi"}
            ),
            security_context=container_security_context,
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
            security_context=container_security_context
        )
        
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels={
                    "app.kubernetes.io/name": "mirrage-player",
                    "mirrage.io/session-id": session_id,
                    "mirrage.io/user-id": user_id
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
                if current_pod.status.phase == "Running" and current_pod.status.pod_ip:
                    pod_ip = current_pod.status.pod_ip
                    logger.info(f"Pod {pod_name} is running with IP {pod_ip}")
                    return pod_name, pod_ip, pod_ip
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
            return {
                "phase": pod.status.phase,
                "ip": pod.status.pod_ip,
                "start_time": pod.status.start_time
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Exception reading pod status: {e}")
            return None


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
            "start_time": time.time()
        }
        
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.3, 0.5))
        
        if self.simulate_readiness_timeout:
            self.pods[pod_name]["phase"] = "Failed"
            raise TimeoutError(f"Pod {pod_name} did not become ready in time.")
            
        ip = f"10.42.0.{self._next_ip}"
        self._next_ip += 1
        
        self.pods[pod_name].update({
            "phase": "Running",
            "ip": ip
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
