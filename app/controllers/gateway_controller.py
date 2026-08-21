from fastapi import APIRouter, Query, Request
from app.models.gateway import DeviceRegisterRequest, DeviceHeartbeatRequest, DeliveryReportRequest, QueueJobRequest
from app.services.gateway_service import gateway_service
from app.core.state import get_tenant_dispatch_state

router = APIRouter(tags=["Android Mobile Gateway & Relay"])

# 1. Device Registration Routes (Supports all legacy mobile APK variants)
@router.post("/api/gateway/register")
@router.post("/device")
@router.post("/v1/device")
@router.post("/api/v1/device")
@router.post("/mobile/v1/device")
@router.post("/mobile/v1/device/register")
@router.post("/auth/code")
@router.post("/auth/login")
@router.post("/mobile/v1/auth")
@router.post("/api/relay/register_device")
def register_device(req: DeviceRegisterRequest):
    p_code = req.pairing_code or req.code or req.login_code or req.id or "JR-DEFAULT"
    return gateway_service.register_device(p_code, req.dict())

# 2. Heartbeat Telemetry
@router.post("/api/gateway/heartbeat")
@router.post("/mobile/v1/heartbeat")
def record_heartbeat(req: DeviceHeartbeatRequest):
    p_code = req.pairing_code or "JR-DEFAULT"
    return gateway_service.record_heartbeat(p_code, req.dict())

# 3. Delivery Report
@router.post("/api/gateway/report")
@router.post("/mobile/v1/report")
def delivery_report(req: DeliveryReportRequest):
    p_code = (req.pairing_code or req.code or "JR-DEFAULT").strip().upper()
    st = get_tenant_dispatch_state(p_code)
    if req.status == "SENT":
        st["sent_count"] = st.get("sent_count", 0) + 1
        st["logs"].append(f"📱 [Phone Gateway] SMS delivered to {req.phone} (SIM {req.sim_slot+1})")
    elif req.status in ["FAILED", "ERROR"]:
        st["failed_count"] = st.get("failed_count", 0) + 1
        st["logs"].append(f"❌ [Phone Gateway] Failed for {req.phone}: {req.error or 'Unknown phone error'}")
    if req.is_finished:
        st["is_running"] = False
    return {"ok": True, "pairing_code": p_code}

# 4. Job Drainage (For Android Companion APK)
@router.get("/api/relay/drain_jobs")
@router.get("/mobile/v1/jobs")
def drain_jobs(pairing_code: str = Query("JR-DEFAULT"), code: str = Query(None)):
    p_code = code or pairing_code
    jobs = gateway_service.drain_jobs(p_code)
    return {"ok": True, "count": len(jobs), "jobs": jobs, "pairing_code": p_code}

# 5. Live Hardware Status Monitor
@router.get("/api/relay/status")
def relay_status(pairing_code: str = Query("JR-DEFAULT"), user_id: str = Query(None)):
    return gateway_service.get_device_status(pairing_code)

# 6. Manual Job Enqueue
@router.post("/api/relay/queue_job")
def queue_job(req: QueueJobRequest):
    gateway_service.queue_job(req.pairing_code, req.dict())
    return {"ok": True, "message": "Job queued successfully."}
