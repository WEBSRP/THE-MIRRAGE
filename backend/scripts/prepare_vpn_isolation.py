#!/usr/bin/env python3
"""Offline migration: reserve IPs/write CCDs for active existing real profiles.

Run during maintenance with API/VPN clients drained. Default is read-only; --apply
requires migrations at head and writes reservations/CCDs. Existing certificates stay valid.
Mock and revoked profiles are excluded. No private profile material is printed.
"""
import argparse
import asyncio

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.models.user import User
from backend.app.models.vpn import VpnProfile
from backend.app.services.vpn_service import ProductionVPNService


async def prepare(apply: bool):
    if settings.VPN_MODE != "production":
        raise RuntimeError("This migration requires VPN_MODE=production")
    if apply:
        await init_db()
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).join(VpnProfile).where(
            User.is_active.is_(True), VpnProfile.revoked_at.is_(None),
            ~VpnProfile.client_name.startswith("mock-"),
        ))).scalars().all()
        print(f"Existing active real profiles to prepare: {len(users)}")
        if not apply:
            print("Read-only preview. Re-run with --apply during maintenance to write reservations and CCDs.")
            return
        service = ProductionVPNService()
        for user in users:
            await service.generate_or_get_profile(db, user)
        print(f"Prepared {len(users)} certificate/address bindings. Reconnect clients after server configuration is updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(prepare(parser.parse_args().apply))
