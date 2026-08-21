import pytest
import time
from datetime import datetime, timedelta
from web_ui import SupabaseAuditService, get_user_pairing_code

@pytest.fixture
def auth_service():
    service = SupabaseAuditService()
    service.enabled = False  # Test high-availability deterministic local engine
    # Reset test state
    users = service._get_local_users()
    test_emails = ["test_new_recruiter@jobrecruitment.in", "test_signin_recruiter@jobrecruitment.in"]
    for em in test_emails:
        if em in users:
            del users[em]
    service._save_local_users(users)
    return service

def test_registration_request_and_verification_flow(auth_service):
    email = "test_new_recruiter@jobrecruitment.in"
    name = "Test Recruiter"
    role = "recruiter"

    # Step 1: Request Registration OTP
    ok, res = auth_service.request_registration_otp(email, name, role)
    assert ok is True
    otp_code = res.get("token")
    assert otp_code is not None
    assert len(otp_code) == 6

    # Step 2: Verify with Wrong Code
    ok_bad, res_bad = auth_service.verify_registration_otp(email, "000000")
    assert ok_bad is False

    # Step 3: Verify with Correct Code
    ok_good, user = auth_service.verify_registration_otp(email, otp_code)
    assert ok_good is True
    assert user["email"] == email
    assert user["name"] == name
    assert user["pairing_code"].startswith("JR-")

    # Step 4: Prevent Replay Attack (Used Code)
    ok_replay, msg_replay = auth_service.verify_registration_otp(email, otp_code)
    assert ok_replay is False

def test_duplicate_registration_prevention(auth_service):
    email = "test_signin_recruiter@jobrecruitment.in"
    name = "Existing User"
    
    # First Register
    ok1, res1 = auth_service.request_registration_otp(email, name, "recruiter")
    auth_service.verify_registration_otp(email, res1["token"])

    # Second Register with same email
    ok2, res2 = auth_service.request_registration_otp(email, name, "recruiter")
    assert ok2 is False
    assert "already exists" in res2

def test_signin_otp_flow(auth_service):
    email = "test_signin_recruiter@jobrecruitment.in"
    name = "Sign In User"

    # 1. Register user first
    ok_reg, res_reg = auth_service.request_registration_otp(email, name, "recruiter")
    assert ok_reg is True
    auth_service.verify_registration_otp(email, res_reg["token"])
    
    # 2. Request Login OTP
    ok_login, res_login = auth_service.request_login_otp(email)
    assert ok_login is True
    login_otp = res_login.get("token")
    assert len(login_otp) == 6

    # 3. Verify Login OTP
    ok_verify, user = auth_service.verify_login_otp(email, login_otp)
    assert ok_verify is True
    assert user["email"] == email
    assert user["pairing_code"].startswith("JR-")

def test_otp_attempt_capping(auth_service):
    email = "test_capping@jobrecruitment.in"
    ok, res = auth_service.request_registration_otp(email, "Capping Test", "recruiter")
    
    # 5 Failed Attempts
    for i in range(5):
        auth_service.verify_registration_otp(email, f"99999{i}")
    
    # 6th attempt with CORRECT code should fail due to attempt limit
    otp_code = res.get("token")
    ok_final, msg_final = auth_service.verify_registration_otp(email, otp_code)
    assert ok_final is False
    assert "attempts exceeded" in msg_final.lower()
