"""Restricted bridge to public-CRL installation and selected-client disconnect."""
import asyncio
import json
from backend.app.core.config import settings
from backend.app.services.vpn_provisioner import _validate_client_name


class VPNControl:
    async def _run(self, *arguments, public_certificate=None):
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/sudo", "-n", "--", settings.VPN_CONTROL_HELPER, *arguments,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if public_certificate is not None else asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(
                public_certificate.encode() if public_certificate is not None else None
            ), timeout=60)
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise RuntimeError("VPN control timed out") from None
        if process.returncode:
            raise RuntimeError("VPN control operation failed")
        return stdout

    async def block(self, client_name, public_certificate=None):
        arguments = ["block", "--client", _validate_client_name(client_name)]
        if public_certificate:
            arguments.append("--certificate-stdin")
        await self._run(*arguments, public_certificate=public_certificate)

    async def publish(self, client_name):
        return json.loads(await self._run("publish", "--client", _validate_client_name(client_name)))

    async def refresh(self):
        return json.loads(await self._run("refresh"))

    async def health(self):
        return json.loads(await self._run("health"))


vpn_control = VPNControl()
