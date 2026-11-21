"""Validated resource identities shared by inventory and conditional deletion."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SessionResource:
    kind: str
    name: str
    session_id: str
    user_id: str
    uid: str
    resource_version: str
    pod_ip: str | None = None


@dataclass(frozen=True)
class SessionInventory:
    resources: tuple[SessionResource, ...]
    occupied_ips: frozenset[str]
    ignored: int = 0


def identify_resource(kind, metadata, pod_name, pod_ip=None):
    """Names alone never authorize deletion; require the controller's labels."""
    labels = metadata.get("labels") or {}
    session_id = labels.get("mirrage.io/session-id", "")
    user_id = labels.get("mirrage.io/user-id", "")
    if (not re.fullmatch(r"[a-z0-9-]{1,100}", session_id)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id)):
        return None
    expected = pod_name(session_id)
    if kind == "Pod":
        if labels.get("app") != "mirrage-session":
            return None
    elif kind == "NetworkPolicy":
        if labels.get("mirrage.io/purpose") != "player-access":
            return None
        expected = "access-" + expected
    else:
        return None
    uid, version = metadata.get("uid"), metadata.get("resourceVersion")
    if metadata.get("name") != expected or not isinstance(uid, str) or not uid or not isinstance(version, str) or not version:
        return None
    return SessionResource(kind, expected, session_id, user_id, uid, version, pod_ip)
