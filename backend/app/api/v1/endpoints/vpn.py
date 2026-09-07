from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.vpn import VpnDownloadOut, VpnStatusOut
from backend.app.services.vpn_service import vpn_service

router = APIRouter(prefix="/vpn", tags=["OpenVPN & Connectivity"])


@router.get(
    "/status",
    response_model=VpnStatusOut,
    summary="Get player VPN connection status and telemetry"
)
async def get_vpn_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get live OpenVPN connection telemetry for the player:
    - Connected vs Disconnected indicator
    - Assigned Tunnel IP (e.g. 10.8.0.X)
    - Data transferred (bytes sent / received)
    - Active connection duration
    """
    return await vpn_service.get_vpn_status(db=db, user=current_user)


@router.get(
    "/profile",
    response_model=VpnDownloadOut,
    summary="Get OpenVPN configuration data"
)
async def get_vpn_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the player's full OpenVPN profile configuration and metadata."""
    return await vpn_service.get_download_profile(db=db, user=current_user)


@router.get(
    "/download",
    summary="Download .ovpn configuration file"
)
async def download_ovpn_file(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Directly download the player's unique .ovpn client profile file as an attachment.
    """
    profile_data = await vpn_service.get_download_profile(db=db, user=current_user)
    return Response(
        content=profile_data.config_data,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{profile_data.filename}"',
        },
    )
