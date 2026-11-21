"""One policy contract for the namespace guard and each player session."""
import ipaddress

from backend.app.core.config import settings

DEFAULT_DENY_NAME = "isolate-player-sessions"


def default_deny_policy() -> dict:
    return {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": DEFAULT_DENY_NAME, "namespace": settings.K8S_NAMESPACE},
        "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"], "ingress": [], "egress": []},
    }


def player_network_policy(pod_name: str, session_id: str, user_id: str, vpn_ip: str) -> dict:
    address = ipaddress.IPv4Address(vpn_ip)
    network = ipaddress.IPv4Network(settings.VPN_CLIENT_CIDR)
    if address not in network or address in (network.network_address, network.broadcast_address):
        raise ValueError("Session requires a reserved IPv4 VPN address")
    peer = {"ipBlock": {"cidr": f"{address}/32"}}
    labels = {"mirrage.io/session-id": session_id, "mirrage.io/user-id": user_id}
    egress = []
    if settings.SESSION_CALLBACK_PORTS:
        egress = [{"to": [peer], "ports": [
            {"protocol": "TCP", "port": port} for port in settings.SESSION_CALLBACK_PORTS
        ]}]
    return {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {
            "name": f"access-{pod_name}", "namespace": settings.K8S_NAMESPACE,
            "labels": {**labels, "mirrage.io/purpose": "player-access"},
            "annotations": {"mirrage.io/vpn-ip": str(address)},
        },
        "spec": {
            "podSelector": {"matchLabels": labels}, "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": [peer], "ports": [
                {"protocol": "TCP", "port": port} for port in (22, 80, 2222)
            ]}],
            "egress": egress,
        },
    }


def normalize_spec(value):
    """Kubernetes serializes absent optional lists as either null or empty."""
    if isinstance(value, dict):
        return {key: normalize_spec(item) for key, item in value.items()
                if item is not None and item != [] and item != {}}
    if isinstance(value, list):
        return [normalize_spec(item) for item in value]
    return value
