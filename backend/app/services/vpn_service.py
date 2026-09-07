import ipaddress
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.vpn import VpnProfile
from backend.app.schemas.vpn import VpnStatusOut, VpnDownloadOut


class VPNService(ABC):
    @abstractmethod
    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        ...

    @abstractmethod
    async def get_vpn_status(self, db: AsyncSession, user: User) -> VpnStatusOut:
        ...

    @abstractmethod
    async def get_download_profile(self, db: AsyncSession, user: User) -> VpnDownloadOut:
        ...

    @abstractmethod
    async def revoke_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> bool:
        ...


class ProductionVPNService(VPNService):
    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        # TODO: Implement Easy-RSA integration
        # Uses Easy-RSA to generate real client certificates
        # Reads the CA cert from settings.OPENVPN_CA_PATH
        # Creates unique client identities per user: mirrage-{username}-{user_id[:6]}
        # Generates real .ovpn files with actual CA cert + generated client cert/key
        # Parses OpenVPN status log for live connection telemetry
        # Supports certificate revocation via Easy-RSA CRL
        # The CA private key passphrase must NEVER be logged or exposed
        # Profile is per-user (not per-session) in production for simplicity
        # Stores the .ovpn config in the database
        raise NotImplementedError("Production VPN Service is not yet implemented (Requires EC2 setup)")

    async def get_vpn_status(self, db: AsyncSession, user: User) -> VpnStatusOut:
        raise NotImplementedError("Production VPN Service is not yet implemented (Requires EC2 setup)")

    async def get_download_profile(self, db: AsyncSession, user: User) -> VpnDownloadOut:
        raise NotImplementedError("Production VPN Service is not yet implemented (Requires EC2 setup)")

    async def revoke_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> bool:
        raise NotImplementedError("Production VPN Service is not yet implemented (Requires EC2 setup)")


class MockVPNService(VPNService):
    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        result = await db.execute(select(VpnProfile).where(VpnProfile.user_id == user.id))
        profile = result.scalars().first()

        if profile:
            return profile

        # Generate a deterministic mock client name
        client_name = f"mock-{user.username}-{str(user.id)[:6]}"

        # Allocate VPN IP from 10.8.0.10 onwards using sequential tracking
        all_profiles_result = await db.execute(select(VpnProfile))
        all_profiles = all_profiles_result.scalars().all()

        max_ip_int = int(ipaddress.IPv4Address("10.8.0.9"))
        for p in all_profiles:
            if p.assigned_ip:
                try:
                    ip_int = int(ipaddress.IPv4Address(p.assigned_ip))
                    if ip_int > max_ip_int:
                        max_ip_int = ip_int
                except Exception:
                    pass

        next_ip = str(ipaddress.IPv4Address(max_ip_int + 1))

        mock_config = (
            "# *** MOCK DEVELOPMENT PROFILE — NOT FOR PRODUCTION ***\n"
            "client\n"
            "dev tun\n"
            "proto udp\n"
            "remote mock.vpn.example.com 1194\n"
            "resolv-retry infinite\n"
            "nobind\n"
            "persist-key\n"
            "persist-tun\n"
            "route 10.42.0.0 255.255.0.0 10.8.0.1\n"
            "<ca>\n"
            "-----BEGIN CERTIFICATE-----\n"
            "MOCK-CA-CERTIFICATE\n"
            "-----END CERTIFICATE-----\n"
            "</ca>\n"
            "<cert>\n"
            "-----BEGIN CERTIFICATE-----\n"
            "MOCK-CLIENT-CERTIFICATE\n"
            "-----END CERTIFICATE-----\n"
            "</cert>\n"
            "<key>\n"
            "-----BEGIN PRIVATE KEY-----\n"
            "MOCK-PRIVATE-KEY\n"
            "-----END PRIVATE KEY-----\n"
            "</key>\n"
        )

        new_profile = VpnProfile(
            user_id=user.id,
            client_name=client_name,
            config_data=mock_config,
            assigned_ip=next_ip,
            is_connected=False,
            bytes_received=0,
            bytes_sent=0
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)

        return new_profile

    async def get_vpn_status(self, db: AsyncSession, user: User) -> VpnStatusOut:
        profile = await self.generate_or_get_profile(db, user)

        indicator = "connected" if profile.is_connected else "disconnected"
        return VpnStatusOut(
            is_connected=profile.is_connected,
            assigned_ip=profile.assigned_ip,
            bytes_received=profile.bytes_received,
            bytes_sent=profile.bytes_sent,
            connected_since=profile.connected_since,
            last_seen_at=profile.last_seen_at,
            indicator=indicator,
        )

    async def get_download_profile(self, db: AsyncSession, user: User) -> VpnDownloadOut:
        profile = await self.generate_or_get_profile(db, user)
        filename = f"{profile.client_name}.ovpn"
        return VpnDownloadOut(
            filename=filename,
            config_data=profile.config_data,
            client_ip=profile.assigned_ip
        )

    async def revoke_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> bool:
        result = await db.execute(select(VpnProfile).where(VpnProfile.user_id == user.id))
        profile = result.scalars().first()
        if profile:
            await db.delete(profile)
            await db.commit()
            return True
        return False


def get_vpn_service() -> VPNService:
    from backend.app.core.config import settings
    if settings.VPN_MODE == "production":
        return ProductionVPNService()
    return MockVPNService()


vpn_service = get_vpn_service()
