"""Persistent address allocation and private OpenVPN client configuration."""
import asyncio
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.app.core.config import settings
from backend.app.core.exceptions import MirrageException, VpnConfigurationError
from backend.app.models.vpn import VpnAddressReservation, VpnProfile, VpnRevocation
from backend.app.models.user import User

_allocation_lock = asyncio.Lock()


async def vpn_access_revoked(db, user_id: str) -> bool:
    denied = (await db.execute(select(VpnRevocation.client_name).where(
        VpnRevocation.user_id == user_id
    ).limit(1))).scalar_one_or_none()
    if denied is not None:
        return True
    return (await db.execute(select(VpnProfile.id).where(
        VpnProfile.user_id == user_id, VpnProfile.revoked_at.is_not(None)
    ))).scalar_one_or_none() is not None


async def require_vpn_access(db, user_id: str, *, lock=False) -> None:
    if lock:
        # Recheck the durable deny after acquiring the same user row lock used by
        # admin requests. Do this immediately before any grant/renew/profile write.
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    if await vpn_access_revoked(db, user_id):
        raise MirrageException(403, "VPN access has been revoked; contact an administrator", "VPN_REVOKED")


def validate_player_ip(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    network = ipaddress.IPv4Network(settings.VPN_CLIENT_CIDR)
    if address not in network or address in (network.network_address, network.broadcast_address, network.network_address + 1):
        raise ValueError("Player IP is outside the VPN client network")
    return str(address)


async def reserve_address(db, user_id: str, client_name: str) -> str:
    """Unique constraints arbitrate cross-process races; never recycle a lease."""
    start = ipaddress.IPv4Address(settings.VPN_CLIENT_IP_START)
    end = ipaddress.IPv4Address(settings.VPN_CLIENT_IP_END)
    validate_player_ip(str(start))
    validate_player_ip(str(end))
    if end < start:
        raise ValueError("Invalid VPN address pool")
    dialect = db.bind.dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError("VPN allocation requires PostgreSQL or SQLite")
    async with _allocation_lock:
        existing = (await db.execute(select(VpnAddressReservation).where(
            VpnAddressReservation.user_id == user_id
        ))).scalar_one_or_none()
        if existing:
            if existing.client_name != client_name:
                raise VpnConfigurationError("VPN certificate identity does not match its reservation")
            return validate_player_ip(existing.address)
        used = set((await db.execute(select(VpnAddressReservation.address))).scalars().all())
        for candidate in range(int(start), int(end) + 1):
            address = str(ipaddress.IPv4Address(candidate))
            if address in used:
                continue
            result = await db.execute(insert(VpnAddressReservation).values(
                address=address, user_id=user_id, client_name=client_name
            ).on_conflict_do_nothing().returning(VpnAddressReservation.address))
            allocated = result.scalar_one_or_none()
            # Persist before writing CCDs/issuing certificates. A later failure must
            # not make this address available to another certificate.
            await db.commit()
            if allocated:
                return allocated
            existing = (await db.execute(select(VpnAddressReservation).where(
                VpnAddressReservation.user_id == user_id
            ))).scalar_one_or_none()
            if existing:
                if existing.client_name != client_name:
                    raise VpnConfigurationError("VPN certificate identity conflict")
                return validate_player_ip(existing.address)
        raise VpnConfigurationError("VPN address pool is full")


def write_client_config(client_name: str, address: str, *, certificate=None) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", client_name):
        raise ValueError("Invalid VPN client name")
    address = validate_player_ip(address)
    directory = Path(settings.OPENVPN_CCD_DIR)
    netmask = ipaddress.IPv4Network(settings.VPN_CLIENT_CIDR).netmask
    content = f"ifconfig-push {address} {netmask}\n"
    if certificate is not None:
        from backend.app.services.vpn_credentials import PROFILE_SECONDS
        validity = (certificate.expires_at - certificate.issued_at).total_seconds()
        if not 0 < validity <= PROFILE_SECONDS:
            raise ValueError("VPN certificate exceeds 24-hour policy")
        binding = dict(issued_at=int(certificate.issued_at.timestamp()),
                       expires_at=int(certificate.expires_at.timestamp()), serial=certificate.serial)
        content += "# mirrage-profile-v1 " + json.dumps(binding, sort_keys=True) + "\n"
    directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    destination = directory / client_name
    if (destination.is_file() and not destination.is_symlink()
            and destination.stat().st_mode & 0o777 == 0o640 and destination.read_text() == content):
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o640)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
