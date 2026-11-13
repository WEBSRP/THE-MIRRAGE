from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from backend.app.api.deps import get_current_user, get_db
from backend.app.core.exceptions import MirrageException
from backend.app.models.user import User
from backend.app.schemas.user import UserOut
from backend.app.schemas.otp import OtpRequest, OtpResend, OtpResponse, OtpTokenResponse, OtpVerify
from backend.app.services.auth_service import auth_service

logger = logging.getLogger("mirrage.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current player profile"
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Retrieve details for the currently authenticated player."""
    return current_user


@router.post(
    "/request-otp",
    response_model=OtpResponse,
    summary="Request OTP verification code"
)
async def request_otp_endpoint(
    data: OtpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a 6-digit OTP verification code to the given email.
    Response is always generic to prevent email enumeration.
    """
    resend_after = 60
    try:
        resend_after = await auth_service.request_otp(db=db, email=data.email)
    except MirrageException as e:
        # Re-raise rate limit errors (these don't reveal email existence)
        if e.code in ("OTP_RATE_LIMIT", "OTP_COOLDOWN"):
            raise
        logger.error("OTP request failed with MirrageException: %s", e.code)
    except Exception:
        logger.exception("OTP request failed unexpectedly")
    return OtpResponse(message="If this email can receive an OTP, a verification code has been sent.", resend_after_seconds=resend_after)


@router.post(
    "/verify-otp",
    response_model=OtpTokenResponse,
    summary="Verify OTP and authenticate"
)
async def verify_otp_endpoint(
    data: OtpVerify,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP code and authenticate the user.
    Creates a new account if the email is not yet registered.
    Returns a JWT access token.
    """
    return await auth_service.verify_otp(db=db, email=data.email, otp=data.otp)


@router.post(
    "/resend-otp",
    response_model=OtpResponse,
    summary="Resend OTP verification code"
)
async def resend_otp_endpoint(
    data: OtpResend,
    db: AsyncSession = Depends(get_db)
):
    """
    Resend a new OTP verification code, invalidating any previous code.
    Enforces cooldown and rate limiting.
    """
    try:
        await auth_service.resend_otp(db=db, email=data.email)
    except MirrageException as e:
        # Re-raise rate limit/cooldown errors (these don't reveal email existence)
        if e.code in ("OTP_COOLDOWN", "OTP_RATE_LIMIT"):
            raise
        logger.error("OTP resend failed with MirrageException: %s", e.code)
    except Exception:
        logger.exception("OTP resend failed unexpectedly")
    return OtpResponse(message="If this email can receive an OTP, a new verification code has been sent.", resend_after_seconds=60)
