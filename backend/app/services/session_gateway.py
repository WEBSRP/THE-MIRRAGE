"""Unprivileged API adapter for the root-owned session-access helper."""
import asyncio
from datetime import datetime, timezone
import ipaddress
import json

from backend.app.core.config import settings


class SessionGateway:
    async def _run(self, *args):
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/sudo", "-n", "--", settings.SESSION_GATEWAY_HELPER, *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("Session gateway timed out") from None
        if process.returncode:
            raise RuntimeError("Session gateway operation failed")
        return stdout

    async def check(self):
        actual = json.loads(await self._run("check"))
        expected = {
            "vpn_interface": settings.OPENVPN_TUN_INTERFACE,
            "pod_interface": settings.SESSION_POD_INTERFACE,
            "node_name": settings.K8S_SESSION_NODE_NAME,
            "vpn_cidr": settings.VPN_CLIENT_CIDR,
            "pod_cidr": settings.SESSION_POD_CIDR,
            "callback_ports": settings.SESSION_CALLBACK_PORTS,
            "max_lease_seconds": settings.SESSION_MAX_DURATION_MINUTES * 60,
        }
        if any(actual.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Backend and gateway network configuration differ")

    async def grant(self, session_id: str, vpn_ip: str, pod_ip: str, expires_at: datetime):
        if ipaddress.IPv4Address(vpn_ip) not in ipaddress.IPv4Network(settings.VPN_CLIENT_CIDR):
            raise ValueError("Invalid player address")
        if ipaddress.IPv4Address(pod_ip) not in ipaddress.IPv4Network(settings.SESSION_POD_CIDR):
            raise ValueError("Invalid pod address")
        await self.check()
        await self._run("grant", "--session", session_id, "--vpn-ip", vpn_ip,
                        "--pod-ip", pod_ip, "--expires-at", str(int(expires_at.timestamp())))

    async def revoke(self, session_id: str):
        await self._run("revoke", "--session", session_id)

    async def active(self, session_id, vpn_ip, pod_ip, expires_at):
        result = json.loads(await self._run("status", "--session", session_id))
        binding = result.get("binding") or {}
        return (result.get("active") is True and binding.get("vpn_ip") == vpn_ip
                and binding.get("pod_ip") == pod_ip
                and binding.get("expires_at", 0) >= int(expires_at.timestamp()))

    async def renew(self, session_id: str, vpn_ip: str, pod_ip: str, expires_at: datetime):
        await self.check()
        await self._run("renew", "--session", session_id, "--vpn-ip", vpn_ip,
                        "--pod-ip", pod_ip, "--expires-at", str(int(expires_at.timestamp())))

    async def forget(self, session_id: str):
        await self._run("forget", "--session", session_id)

    async def inventory(self):
        await self.check()
        return json.loads(await self._run("inventory"))


class MockSessionGateway:
    def __init__(self):
        self.bindings = {}

    async def check(self):
        return None

    async def grant(self, session_id, vpn_ip, pod_ip, expires_at):
        self.bindings[session_id] = (vpn_ip, pod_ip, expires_at)

    async def revoke(self, session_id):
        if session_id in self.bindings:
            vpn_ip, pod_ip, _ = self.bindings[session_id]
            self.bindings[session_id] = (vpn_ip, pod_ip, datetime.fromtimestamp(0, timezone.utc))

    async def active(self, session_id, vpn_ip, pod_ip, expires_at):
        binding = self.bindings.get(session_id)
        return binding is not None and binding[:2] == (vpn_ip, pod_ip) and binding[2] >= expires_at

    async def renew(self, session_id, vpn_ip, pod_ip, expires_at):
        if session_id not in self.bindings or self.bindings[session_id][2].timestamp() <= datetime.now(timezone.utc).timestamp():
            raise RuntimeError("Cannot renew revoked access")
        self.bindings[session_id] = (vpn_ip, pod_ip, expires_at)

    async def forget(self, session_id):
        self.bindings.pop(session_id, None)

    async def inventory(self):
        return {key: {"vpn_ip": vpn, "pod_ip": pod, "expires_at": int(expiry.timestamp())}
                for key, (vpn, pod, expiry) in self.bindings.items()}


session_gateway = SessionGateway() if settings.K8S_MODE == "production" else MockSessionGateway()
