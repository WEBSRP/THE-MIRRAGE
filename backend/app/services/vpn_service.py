import asyncio
import hashlib
import ipaddress
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text

from backend.app.core.config import settings
from backend.app.core.exceptions import VpnConfigurationError
from backend.app.models.user import User
from backend.app.models.vpn import VpnProfile
from backend.app.schemas.vpn import VpnStatusOut, VpnDownloadOut
from backend.app.services.vpn_access import require_vpn_access

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

    def __init__(self):
        self._profile_lock = asyncio.Lock()

    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        from pathlib import Path
        import secrets
        from backend.app.models.vpn import VpnAddressReservation
        from backend.app.services.vpn_access import reserve_address, write_client_config
        from backend.app.services.vpn_credentials import certificate_details
        from backend.app.services.vpn_control import vpn_control
        from backend.app.services.vpn_provisioner import (
            create_client_certificate, build_ovpn_profile, generate_client_name,
            revoke_client_certificate, VPNProvisionerError,
        )
        async with self._profile_lock:
            await require_vpn_access(db, user.id)
            if db.bind.dialect.name == "postgresql":
                # Serialize before reading the certificate/address binding. The
                # allocation may commit, so reacquire below before locking the user.
                await db.execute(text("SELECT pg_advisory_xact_lock(74291825)"))
            prior = (await db.execute(select(VpnProfile).where(VpnProfile.user_id == user.id))).scalars().first()
            reserved_name = (prior.client_name if prior and not prior.client_name.startswith("mock-")
                             else generate_client_name(user.id))
            # Allocation commits before certificate work; failures retain the address.
            address = await reserve_address(db, user.id, reserved_name)
            if db.bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(74291825)"))
            await require_vpn_access(db, user.id, lock=True)
            profile = (await db.execute(select(VpnProfile).where(
                VpnProfile.user_id == user.id
            ).with_for_update().execution_options(populate_existing=True))).scalars().first()
            reservation = (await db.execute(select(VpnAddressReservation).where(
                VpnAddressReservation.user_id == user.id
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            old_certificate = None
            if profile and not profile.client_name.startswith("mock-"):
                try:
                    old_certificate = certificate_details(profile.config_data, profile.client_name)
                except ValueError:
                    pass
            rotate = old_certificate is None or not old_certificate.usable()
            created_name = None
            try:
                if rotate:
                    # Fresh identity/key per issuance; never overwrite an old certificate
                    # or remove the account's permanent administrator-deny records.
                    new_name = generate_client_name(user.id)[:47] + "-" + secrets.token_hex(8)
                    await create_client_certificate(new_name)
                    config_data = build_ovpn_profile(new_name)
                    certificate = certificate_details(config_data, new_name)
                    if not certificate.usable():
                        raise ValueError("New VPN certificate violates expiry policy")
                    config_data = ("# MIRRAGE VPN expires at " + certificate.expires_at.isoformat()
                                   + " (24 hours after issuance)\n" + config_data)
                    if profile and not profile.client_name.startswith("mock-"):
                        await vpn_control.block(profile.client_name,
                                                public_certificate=old_certificate.pem if old_certificate else None)
                        await revoke_client_certificate(profile.client_name)
                        await vpn_control.publish(profile.client_name)
                    if profile is None:
                        profile = VpnProfile(user_id=user.id, client_name=new_name,
                                             config_data=config_data, is_connected=False)
                        db.add(profile)
                    else:
                        profile.client_name = new_name
                        profile.config_data = config_data
                        profile.is_connected = False
                        profile.connected_since = None
                    reservation.client_name = new_name
                    created_name = new_name
                else:
                    certificate = old_certificate
                    if reservation.client_name != profile.client_name:
                        raise ValueError("VPN reservation identity mismatch")
                await asyncio.to_thread(write_client_config, profile.client_name, address,
                                        certificate=certificate)
                profile.assigned_ip = address
                await db.commit()
            except BaseException as error:
                await db.rollback()
                if created_name:
                    # No caller has received this uncommitted bundle. Remove its CCD;
                    # retain the durable address and old profile for a safe retry.
                    (Path(settings.OPENVPN_CCD_DIR) / created_name).unlink(missing_ok=True)
                if isinstance(error, (VPNProvisionerError, OSError, ValueError, RuntimeError)):
                    logger.error("Cannot provision VPN credentials; retry after resolving PKI/control failure")
                    raise VpnConfigurationError("Cannot provision VPN address/configuration") from None
                raise
            await db.refresh(profile)
            return profile

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

        from backend.app.services.vpn_credentials import certificate_details
        expires_at = certificate_details(profile.config_data, profile.client_name).expires_at

        # Parse live status from OpenVPN
        try:
            status_data = parse_openvpn_status_log()
        except Exception:
            logger.warning("Failed to parse OpenVPN status log")
            status_data = {}

        # Look up this client in the status data
        client_info = status_data.get(profile.client_name)

        if client_info and client_info.get("virtual_address") != profile.assigned_ip:
            logger.error("VPN address mismatch for user %s; reconnect after checking CCD configuration", user.id)
            client_info = None

        if client_info:
            # The certificate/address reservation, not the status log, is authoritative.
            profile.is_connected = True
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
                connected_clients=len(status_data),
                expires_at=expires_at,
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
                connected_clients=len(status_data),
                expires_at=expires_at,
            )

    async def get_download_profile(self, db: AsyncSession, user: User) -> VpnDownloadOut:
        """Return the downloadable .ovpn profile."""
        profile = await self.generate_or_get_profile(db, user)

        if profile.revoked_at is not None:
            raise VpnConfigurationError(
                detail="Your VPN profile has been revoked. Please contact an administrator."
            )

        from backend.app.services.vpn_credentials import certificate_details
        expires_at = certificate_details(profile.config_data, profile.client_name).expires_at
        filename = f"{profile.client_name}.ovpn"
        return VpnDownloadOut(
            filename=filename,
            config_data=profile.config_data,
            client_ip=profile.assigned_ip,
            expires_at=expires_at,
        )

    async def revoke_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> bool:
        from backend.app.services.vpn_revocation import vpn_revocation_service
        await vpn_revocation_service.request(db, user.id, user.id)
        return True


class MockVPNService(VPNService):
    async def generate_or_get_profile(self, db: AsyncSession, user: User, session_id: Optional[str] = None) -> VpnProfile:
        await require_vpn_access(db, user.id, lock=True)
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

        count = await db.execute(select(func.count(VpnProfile.id)).where(VpnProfile.is_connected.is_(True), VpnProfile.revoked_at.is_(None)))
        connected_clients = count.scalar() or 0
        indicator = "connected" if profile.is_connected else "disconnected"
        return VpnStatusOut(
            is_connected=profile.is_connected,
            assigned_ip=profile.assigned_ip,
            bytes_received=profile.bytes_received,
            bytes_sent=profile.bytes_sent,
            connected_since=profile.connected_since,
            last_seen_at=profile.last_seen_at,
            indicator=indicator,
            connected_clients=connected_clients,
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
        from backend.app.services.vpn_revocation import vpn_revocation_service
        await vpn_revocation_service.request(db, user.id, user.id)
        return True


def get_vpn_service() -> VPNService:
    from backend.app.core.config import settings
    if settings.VPN_MODE == "production":
        return ProductionVPNService()
    return MockVPNService()


vpn_service = get_vpn_service()
