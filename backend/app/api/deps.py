from typing import AsyncGenerator, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.services.auth_service import auth_service

http_bearer = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Enter JWT access token. Swagger automatically prefixes it with 'Bearer '.",
    auto_error=False
)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token and retrieve current authenticated user."""
    # Extract token from HTTPBearer credentials or raw Authorization header
    token_str = credentials.credentials if credentials else None
    if not token_str and authorization:
        if authorization.startswith("Bearer "):
            token_str = authorization.split(" ", 1)[1]
        else:
            token_str = authorization

    if not token_str:
        raise AuthenticationError("Authorization token is missing")

    payload = decode_access_token(token_str)
    if not payload or not payload.get("sub"):
        raise AuthenticationError("Invalid or expired authentication token")

    user_id = payload["sub"]
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise AuthenticationError("User associated with token no longer exists")

    if not user.is_active:
        raise AuthenticationError("User account is disabled")

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure current user has administrative privileges."""
    if not current_user.is_admin:
        raise PermissionDeniedError("Administrative privileges required")
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Retrieve user if token is provided, otherwise return None."""
    if not credentials and not authorization:
        return None
    try:
        return await get_current_user(credentials=credentials, authorization=authorization, db=db)
    except Exception:
        return None
