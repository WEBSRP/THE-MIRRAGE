from pydantic import BaseModel, EmailStr, Field
from backend.app.schemas.user import UserOut


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OtpResend(BaseModel):
    email: EmailStr


class OtpResponse(BaseModel):
    message: str
    resend_after_seconds: int = 0


class OtpTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool
    user: UserOut
