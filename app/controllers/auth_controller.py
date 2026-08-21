from fastapi import APIRouter, HTTPException, Query, status
from app.models.auth import (
    RegisterRequest, LoginOtpRequest, VerifyOtpRequest, ResendOtpRequest,
    PasswordLoginRequest, ForgotPasswordRequest, ResetPasswordRequest, AuthResponse
)
from app.services.auth_service import auth_service
from app.services.email_service import email_service

router = APIRouter(prefix="/api/auth", tags=["Authentication Microservice"])

@router.post("/register", response_model=AuthResponse)
def register_recruiter(req: RegisterRequest):
    ok, res = auth_service.request_registration_otp(str(req.email), req.full_name, req.role)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=res)
    return AuthResponse(ok=True, message=res.get("message"), token=res.get("token"))

@router.post("/register/verify", response_model=AuthResponse)
def verify_registration(req: VerifyOtpRequest):
    ok, res = auth_service.verify_registration_otp(str(req.email), req.otp)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return AuthResponse(ok=True, user=res)

@router.post("/login/request_otp", response_model=AuthResponse)
@router.post("/send_otp", response_model=AuthResponse)
def request_login_otp(req: LoginOtpRequest):
    ok, res = auth_service.request_login_otp(str(req.email))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res)
    return AuthResponse(ok=True, message=res.get("message"), token=res.get("token"))

@router.post("/login/verify_otp", response_model=AuthResponse)
@router.post("/verify_otp", response_model=AuthResponse)
def verify_login_otp(req: VerifyOtpRequest):
    ok, res = auth_service.verify_login_otp(str(req.email), req.otp)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return AuthResponse(ok=True, user=res)

@router.post("/otp/resend", response_model=AuthResponse)
def resend_otp(req: ResendOtpRequest):
    if req.purpose == "register":
        ok, res = auth_service.request_registration_otp(str(req.email), req.full_name or "", req.role)
    else:
        ok, res = auth_service.request_login_otp(str(req.email))
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return AuthResponse(ok=True, message=res.get("message"), token=res.get("token"))

@router.post("/login", response_model=AuthResponse)
def password_login(req: PasswordLoginRequest):
    ok, res = auth_service.login_user(str(req.email), req.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=res)
    return AuthResponse(ok=True, user=res)

@router.post("/signup", response_model=AuthResponse)
def password_signup(req: RegisterRequest):
    pwd = req.password or "DEFAULT_PASS"
    ok, res = auth_service.signup_user(str(req.email), pwd, req.full_name, req.role)
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=res)
    return AuthResponse(ok=True, user=res)

@router.post("/forgot_password", response_model=AuthResponse)
def forgot_password(req: ForgotPasswordRequest):
    ok, res = auth_service.create_password_reset(str(req.email))
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return AuthResponse(ok=True, message=res.get("message"), token=res.get("token"))

@router.post("/reset_password", response_model=AuthResponse)
def reset_password(req: ResetPasswordRequest):
    ok, res = auth_service.reset_password_with_token(str(req.email), req.token, req.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res)
    return AuthResponse(ok=True, message=res)

@router.get("/test_email")
def test_email_endpoint(to: str = Query("hire@jobrecruitment.in")):
    ok, msg = email_service.send_otp_email(to, "889900", purpose="Diagnostic Test")
    return {"ok": ok, "message": msg, "target": to}
