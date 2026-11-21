from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_current_admin_user, get_db
from backend.app.models.user import User
from backend.app.schemas.vpn import VpnCrlHealthOut, VpnDownloadOut, VpnStatusOut, VpnRevokeResponse
from backend.app.models.vpn import VpnCrlMaintenance
from backend.app.services.vpn_revocation import vpn_revocation_service
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
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the player's full OpenVPN profile configuration and metadata."""
    response.headers["Cache-Control"] = "no-store"
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
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/revoke",
    response_model=VpnRevokeResponse,
    summary="Revoke player's VPN certificate"
)
async def revoke_vpn_profile(
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke the current user's VPN certificate. Admin only.
    After revocation, the user will need to contact support for a new profile.
    """
    return await _request_revocation(db, current_user.id, current_user.id, response, background_tasks)


def revocation_response(job):
    done = job.completed_at is not None
    return VpnRevokeResponse(
        message=("VPN certificate, tunnel and session revocation completed." if done
                 else "VPN access denied; external revocation is pending."),
        revoked_at=job.requested_at, user_id=job.user_id,
        status="completed" if done else "pending", completed_at=job.completed_at,
        attempts=job.attempts, last_error=job.last_error,
    )


async def _request_revocation(db, user_id, actor_id, response, background_tasks):
    job = await vpn_revocation_service.request(db, user_id, actor_id)
    response.status_code = 200 if job.completed_at else 202
    response.headers["Cache-Control"] = "no-store"
    if job.completed_at is None:
        background_tasks.add_task(vpn_revocation_service.run_background, job.client_name)
    return revocation_response(job)


@router.post("/users/{user_id}/revoke", response_model=VpnRevokeResponse,
             summary="Admin: revoke a selected player's VPN and session access")
async def revoke_player_vpn(
    user_id: UUID, response: Response, background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db),
):
    return await _request_revocation(db, str(user_id), current_user.id, response, background_tasks)


@router.get("/users/{user_id}/revocation", response_model=VpnRevokeResponse,
            summary="Admin: inspect durable VPN revocation progress")
async def get_player_revocation(
    user_id: UUID, response: Response,
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return revocation_response(await vpn_revocation_service.get(db, str(user_id)))


@router.get("/crl-health", response_model=VpnCrlHealthOut,
            summary="Admin: inspect CRL expiry and refresh health")
async def get_crl_health(
    response: Response,
    current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    record = await db.get(VpnCrlMaintenance, 1)
    if record is None:
        return VpnCrlHealthOut(last_error="NOT_CHECKED")
    return VpnCrlHealthOut(checked_at=record.checked_at, expires_at=record.expires_at,
                          last_error=record.last_error)
