from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class MirrageException(HTTPException):
    """Base domain exception for MIRRAGE platform."""
    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str = "INTERNAL_ERROR",
        headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


class AuthenticationError(MirrageException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="AUTHENTICATION_FAILED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(MirrageException):
    def __init__(self, detail: str = "Not enough permissions to perform action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            code="PERMISSION_DENIED",
        )


class EntityNotFoundError(MirrageException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} with identifier '{entity_id}' was not found",
            code="ENTITY_NOT_FOUND",
        )


class SlotLimitExceededError(MirrageException):
    def __init__(self, max_slots: int):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All {max_slots} session slots are currently occupied. Please wait for an active session to complete.",
            code="SLOT_LIMIT_EXCEEDED",
        )


class ActiveSessionExistsError(MirrageException):
    def __init__(self, session_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already has an active session (ID: {session_id}). Stop the current session before starting a new one.",
            code="ACTIVE_SESSION_EXISTS",
        )


class SessionProvisioningError(MirrageException):
    def __init__(self, detail: str = "Failed to provision Kubernetes session pod"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="PROVISIONING_FAILED",
        )


class VpnConfigurationError(MirrageException):
    def __init__(self, detail: str = "Failed to generate OpenVPN profile"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="VPN_CONFIG_ERROR",
        )
