from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from backend.app.api.deps import get_current_user, get_db
from backend.app.core.config import settings
from backend.app.core.exceptions import MirrageException
from backend.app.models.user import User
from backend.app.schemas.user import Token, UserLogin, UserOut, UserRegister
from backend.app.schemas.otp import OtpRequest, OtpResend, OtpResponse, OtpTokenResponse, OtpVerify
from backend.app.services.auth_service import auth_service

logger = logging.getLogger("mirrage.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new player account"
)
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new player account on the MIRRAGE platform.
    Automatically initializes the player's unique OpenVPN identity.
    """
    user = await auth_service.register_user(db=db, user_in=user_in)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Player Login"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate with username or email + password.
    Returns a JWT access token valid for 24 hours.
    """
    token = await auth_service.authenticate_user(db=db, credentials=credentials)
    return token


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
    "/dev-login",
    response_model=Token,
    summary="Development Test Access"
)
async def dev_login(
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate as the development fixture test user ('dev_player').
    STRICT SECURITY GUARD:
    Only accessible when ENVIRONMENT is 'development'.
    Fails closed with 403 Forbidden in production, testing, or any non-development environment.
    """
    if settings.ENVIRONMENT != "development":
        raise MirrageException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development access is disabled in this environment.",
            code="DEV_ACCESS_FORBIDDEN"
        )
    return await auth_service.get_or_create_dev_user(db=db)


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
    try:
        await auth_service.request_otp(db=db, email=data.email)
    except MirrageException as e:
        # Re-raise rate limit errors (these don't reveal email existence)
        if e.code == "OTP_RATE_LIMIT":
            raise
        logger.error("OTP request failed with MirrageException: %s", e.code)
    except Exception:
        logger.exception("OTP request failed unexpectedly")
    return OtpResponse(message="If this email can receive an OTP, a verification code has been sent.")


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
    return OtpResponse(message="If this email can receive an OTP, a new verification code has been sent.")
