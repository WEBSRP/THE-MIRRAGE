import asyncio
import ipaddress
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.core.config import settings
from backend.app.core.exceptions import VpnConfigurationError
from backend.app.models.user import User
from backend.app.models.vpn import VpnProfile
from backend.app.schemas.vpn import VpnStatusOut, VpnDownloadOut

logger = logging.getLogger("mirrage.vpn.service")


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
    """Production VPN service backed by real Easy-RSA certificate operations.

    - Generates real client certificates using Easy-RSA
    - Builds inline .ovpn profiles with CA cert, client cert/key, and TLS-crypt key
    - Parses OpenVPN status log for live connection telemetry
    - Supports certificate revocation via Easy-RSA CRL
    - Stores .ovpn profiles in the database
    - One profile per user (idempotent)
    """

    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        """Generate or retrieve the user's VPN profile.

        Idempotent: if a non-revoked profile exists, return it.
        Otherwise, generate a new client certificate and .ovpn profile.
        """
        from backend.app.services.vpn_provisioner import (
            create_client_certificate,
            build_ovpn_profile,
            generate_client_name,
            VPNProvisionerError,
        )

        # Check for existing non-revoked profile
        result = await db.execute(
            select(VpnProfile).where(
                VpnProfile.user_id == user.id,
                VpnProfile.revoked_at.is_(None),
            )
        )
        profile = result.scalars().first()

        if profile:
            # If the profile was created as a mock profile in development, upgrade it to production
            if profile.client_name.startswith("mock-"):
                client_name = generate_client_name(user.id)
                try:
                    await create_client_certificate(client_name)
                    config_data = build_ovpn_profile(client_name)
                    profile.client_name = client_name
                    profile.config_data = config_data
                    profile.assigned_ip = None
                    profile.is_connected = False
                    await db.commit()
                    await db.refresh(profile)
                    logger.info("Upgraded legacy mock VPN profile to production for user %s (%s)", user.id, client_name)
                    return profile
                except VPNProvisionerError as e:
                    logger.error("Failed to upgrade legacy mock VPN profile for user %s: %s", user.id, str(e))
                    raise VpnConfigurationError(
                        detail="Failed to generate VPN profile. Please try again or contact support."
                    )
            return profile

        # Generate client name from user ID
        client_name = generate_client_name(user.id)

        try:
            # Create certificate (idempotent — no-op if cert exists)
            await create_client_certificate(client_name)

            # Build the inline .ovpn profile
            config_data = build_ovpn_profile(client_name)

        except VPNProvisionerError as e:
            logger.error("VPN provisioning failed for user %s: %s", user.id, str(e))
            raise VpnConfigurationError(
                detail="Failed to generate VPN profile. Please try again or contact support."
            )

        # Store in database
        new_profile = VpnProfile(
            user_id=user.id,
            client_name=client_name,
            config_data=config_data,
            assigned_ip=None,  # Assigned dynamically by OpenVPN server
            is_connected=False,
            bytes_received=0,
            bytes_sent=0,
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)

        logger.info("VPN profile created for user %s (client: %s)", user.id, client_name)
        return new_profile

    async def get_vpn_status(self, db: AsyncSession, user: User) -> VpnStatusOut:
        """Get live VPN connection status by parsing the OpenVPN status log."""
        from backend.app.services.vpn_provisioner import parse_openvpn_status_log

        # Get or create profile
        profile = await self.generate_or_get_profile(db, user)

        if profile.revoked_at is not None:
            return VpnStatusOut(
                is_connected=False,
                assigned_ip=None,
                bytes_received=0,
                bytes_sent=0,
                indicator="disconnected",
            )

        # Parse live status from OpenVPN
        try:
            status_data = parse_openvpn_status_log()
        except Exception:
            logger.warning("Failed to parse OpenVPN status log")
            status_data = {}

        # Look up this client in the status data
        client_info = status_data.get(profile.client_name)

        if client_info:
            # Update profile with live telemetry
            profile.is_connected = True
            profile.assigned_ip = client_info.get("virtual_address")
            profile.bytes_received = client_info.get("bytes_received", 0)
            profile.bytes_sent = client_info.get("bytes_sent", 0)
            profile.last_seen_at = datetime.now(timezone.utc)

            connected_since_str = client_info.get("connected_since")
            if connected_since_str:
                try:
                    profile.connected_since = datetime.strptime(
                        connected_since_str, "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            await db.commit()

            return VpnStatusOut(
                is_connected=True,
                assigned_ip=profile.assigned_ip,
                bytes_received=profile.bytes_received,
                bytes_sent=profile.bytes_sent,
                connected_since=profile.connected_since,
                last_seen_at=profile.last_seen_at,
                indicator="connected",
            )
        else:
            # Client not currently connected
            if profile.is_connected:
                profile.is_connected = False
                await db.commit()

            return VpnStatusOut(
                is_connected=False,
                assigned_ip=profile.assigned_ip,
                bytes_received=profile.bytes_received,
                bytes_sent=profile.bytes_sent,
                connected_since=None,
                last_seen_at=profile.last_seen_at,
                indicator="disconnected",
            )

    async def get_download_profile(self, db: AsyncSession, user: User) -> VpnDownloadOut:
        """Return the downloadable .ovpn profile."""
        profile = await self.generate_or_get_profile(db, user)

        if profile.revoked_at is not None:
            raise VpnConfigurationError(
                detail="Your VPN profile has been revoked. Please contact an administrator."
            )

        filename = f"{profile.client_name}.ovpn"
        return VpnDownloadOut(
            filename=filename,
            config_data=profile.config_data,
            client_ip=profile.assigned_ip,
        )

    async def revoke_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> bool:
        """Revoke the user's VPN profile and certificate."""
        from backend.app.services.vpn_provisioner import (
            revoke_client_certificate,
            VPNProvisionerError,
        )

        result = await db.execute(
            select(VpnProfile).where(
                VpnProfile.user_id == user.id,
                VpnProfile.revoked_at.is_(None),
            )
        )
        profile = result.scalars().first()

        if not profile:
            return False

        try:
            await revoke_client_certificate(profile.client_name)
        except VPNProvisionerError as e:
            logger.error("Certificate revocation failed for %s: %s", profile.client_name, str(e))
            raise VpnConfigurationError(
                detail="Failed to revoke VPN certificate. Please try again or contact support."
            )

        profile.revoked_at = datetime.now(timezone.utc)
        profile.is_connected = False
        await db.commit()

        logger.info("VPN profile revoked for user %s (client: %s)", user.id, profile.client_name)
        return True


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
