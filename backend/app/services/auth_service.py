from datetime import timedelta
from typing import Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.exceptions import AuthenticationError, MirrageException
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.models.user import User
from backend.app.schemas.user import Token, UserLogin, UserOut, UserRegister
from backend.app.services.vpn_service import vpn_service


class AuthService:
    async def register_user(self, db: AsyncSession, user_in: UserRegister) -> User:
        """Register a new player account, hash password, and generate VPN profile."""
        # Check existing email or username
        query = select(User).where(
            or_(User.email == user_in.email, User.username == user_in.username)
        )
        result = await db.execute(query)
        existing_user = result.scalars().first()

        if existing_user:
            if existing_user.email == user_in.email:
                raise MirrageException(
                    status_code=400,
                    detail="An account with this email address already exists",
                    code="EMAIL_ALREADY_EXISTS"
                )
            raise MirrageException(
                status_code=400,
                detail="This username is already taken",
                code="USERNAME_ALREADY_EXISTS"
            )

        # Create new user
        new_user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
            is_active=True,
            is_admin=False,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Generate unique OpenVPN profile for this player
        await vpn_service.generate_or_get_profile(db, new_user)

        return new_user

    async def authenticate_user(self, db: AsyncSession, credentials: UserLogin) -> Token:
        """Authenticate user by username or email and return JWT access token."""
        query = select(User).where(
            or_(
                User.username == credentials.username_or_email,
                User.email == credentials.username_or_email
            )
        )
        result = await db.execute(query)
        user = result.scalars().first()

        if not user or not verify_password(credentials.password, user.hashed_password):
            raise AuthenticationError(detail="Invalid username/email or password")

        if not user.is_active:
            raise AuthenticationError(detail="Account is currently deactivated")

        # Generate JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_str = create_access_token(
            subject=user.id,
            expires_delta=access_token_expires,
            extra_claims={"username": user.username, "is_admin": user.is_admin}
        )

        return Token(
            access_token=token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.model_validate(user)
        )

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch user by ID."""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().first()


auth_service = AuthService()
