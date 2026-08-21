from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    full_name: str = Field(..., min_length=2)
    role: str = "recruiter"
    password: Optional[str] = None

class LoginOtpRequest(BaseModel):
    email: str = Field(..., min_length=3)

class VerifyOtpRequest(BaseModel):
    email: str = Field(..., min_length=3)
    otp: str = Field(..., min_length=4, max_length=10)

class ResendOtpRequest(BaseModel):
    email: str = Field(..., min_length=3)
    purpose: str = "login"
    full_name: Optional[str] = None
    role: str = "recruiter"

class PasswordLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3)

class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3)
    token: str
    new_password: str = Field(..., min_length=6)

class UserSession(BaseModel):
    id: str
    email: str
    name: str
    role: str
    pairing_code: str

class AuthResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    user: Optional[UserSession] = None
    token: Optional[str] = None
