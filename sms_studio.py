"""
JobRecruitment SMS Studio — Entry Point Runner
Bridges directly to FastAPI ASGI Engine for maximum performance & concurrency.
"""
import os
import sys
import uvicorn

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from main import app
from app.core.config import settings, ensure_adb_binary
from app.core.security import hash_string, generate_numeric_otp, generate_pairing_code
from app.core.state import user_relay_devices, user_relay_jobs, user_dispatch_states, relay_lock, get_tenant_dispatch_state, write_log
from app.services.auth_service import auth_service, AuthService
from app.services.quota_service import quota_service, QuotaTracker
from app.services.gateway_service import gateway_service, GatewayService
from app.services.job_service import candidate_service, CandidateService
from app.services.ai_service import ai_service, AiOrchestrator, evaluate_spintax, calculate_sms_encoding
from app.services.dispatch_service import dispatch_service, DispatchService, clean_phone_number

# Backward compatibility aliases
SupabaseAuditService = AuthService
supabase_service = auth_service
quota_tracker = quota_service
get_user_pairing_code = generate_pairing_code

def main():
    port = int(os.getenv("PORT", "5000"))
    print(f"[*] Starting {settings.PROJECT_NAME} v{settings.VERSION} on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
