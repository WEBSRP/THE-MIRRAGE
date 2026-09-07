from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.user import Token, UserLogin, UserOut, UserRegister
from backend.app.services.auth_service import auth_service

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
