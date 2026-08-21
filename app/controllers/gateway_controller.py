import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, Header, Request, Path, status
from app.models.gateway import DeviceRegisterRequest, DeviceHeartbeatRequest, DeliveryReportRequest, QueueJobRequest
from app.services.gateway_service import gateway_service
from app.core.state import get_tenant_dispatch_state, user_relay_devices, user_relay_jobs, relay_lock, write_log

router = APIRouter(tags=["Android Mobile Gateway (Capcom SMS Gate Compatible)"])

def extract_pairing_code(req: Request, explicit_code: Optional[str] = None) -> str:
    if explicit_code and explicit_code.strip():
        return explicit_code.strip().upper()
    auth_header = req.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token_val = auth_header[7:].strip().upper()
        if token_val.startswith("JR-"):
            return token_val
    return "JR-DEFAULT"

# 1. Device Registration (Supports Capcom SMS Gateway, Custom APK, & WebUSB)
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
async def register_device(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    p_code = (
        data.get("username")
        or data.get("login")
        or data.get("pairing_code")
        or data.get("code")
        or data.get("login_code")
        or extract_pairing_code(request)
    )
    if not p_code.startswith("JR-") and len(p_code) >= 4:
        p_code = f"JR-{p_code}" if not p_code.startswith("JR") else p_code
    
    dev_id = data.get("id") or data.get("device_id") or "Android-SM-G781B"
    dev_name = data.get("name") or data.get("device_name") or "Samsung Galaxy"
    sim_slot = data.get("sim_slot", 0)
    
    with relay_lock:
        user_relay_devices[p_code] = {
            "last_heartbeat": time.time(),
            "is_online": True,
            "device_id": dev_id,
            "device_name": dev_name,
            "carrier": data.get("carrier", f"SIM {sim_slot+1}"),
            "battery": data.get("battery", "95%"),
            "token": p_code,
            "android_version": data.get("version", data.get("android_version", "Android 13")),
            "screen_state_text": "Active Cloud Gateway"
        }
    
    write_log(f"[MobileGateway] Device '{dev_name}' successfully registered for Pairing Code: {p_code}")
    
    # Return response compatible with Capcom SMS Gateway APK spec
    return {
        "ok": True,
        "id": dev_id,
        "device_id": dev_id,
        "token": p_code,
        "access_token": p_code,
        "login": p_code,
        "username": p_code,
        "password": "n/a",
        "pairing_code": p_code,
        "message": "Device registered successfully!"
    }

# 2. Heartbeat Telemetry
@router.post("/api/gateway/heartbeat")
@router.post("/mobile/v1/heartbeat")
@router.post("/mobile/v1/device/{device_id}/state")
async def record_heartbeat(request: Request, device_id: Optional[str] = None):
    try:
        data = await request.json()
    except Exception:
        data = {}
    p_code = data.get("pairing_code") or extract_pairing_code(request)
    return gateway_service.record_heartbeat(p_code, data)

# 3. Message Drainage for Capcom SMS Gate (/mobile/v1/messages)
@router.get("/mobile/v1/messages")
@router.get("/api/gateway/poll")
@router.get("/api/relay/drain_jobs")
@router.get("/mobile/v1/jobs")
def drain_messages(request: Request, pairing_code: str = Query(None), code: str = Query(None)):
    p_code = pairing_code or code or extract_pairing_code(request)
    jobs = gateway_service.drain_jobs(p_code)
    
    # If caller is Capcom SMS Gate format:
    capcom_messages = []
    for j in jobs:
        msg_id = j.get("id") or f"msg_{int(time.time()*1000)}"
        phones = [j.get("phone")] if j.get("phone") else []
        capcom_messages.append({
            "id": msg_id,
            "phoneNumbers": phones,
            "message": j.get("message", ""),
            "simNumber": (j.get("sim_slot", 0) + 1),
            "withDeliveryReport": True
        })
    
    if "poll" in request.url.path:
        return {"ok": True, "has_job": len(jobs) > 0, "jobs": jobs, "pairing_code": p_code}
    
    # Capcom app expects JSON array of messages or dict
    if "mobile/v1/messages" in request.url.path:
        return capcom_messages

    return {"ok": True, "count": len(jobs), "jobs": jobs, "pairing_code": p_code}

# 4. Message Status / Delivery Report (/mobile/v1/message/{id}/status or PATCH /mobile/v1/messages/{id})
@router.patch("/mobile/v1/messages/{message_id}")
@router.post("/mobile/v1/message/{message_id}/status")
@router.post("/api/gateway/report")
@router.post("/mobile/v1/report")
async def report_message_status(request: Request, message_id: Optional[str] = None):
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    p_code = (data.get("pairing_code") or data.get("code") or extract_pairing_code(request)).strip().upper()
    st = get_tenant_dispatch_state(p_code)
    status_val = str(data.get("status", "SENT")).upper()
    
    if "SENT" in status_val or "DELIVERED" in status_val:
        st["sent_count"] = st.get("sent_count", 0) + 1
        st["logs"].append(f"📱 [Phone Gateway] SMS delivered via SIM ({data.get('phone', 'recipient')})")
    elif "FAILED" in status_val or "ERROR" in status_val:
        st["failed_count"] = st.get("failed_count", 0) + 1
        st["logs"].append(f"❌ [Phone Gateway] SMS delivery failed: {data.get('error', 'Carrier error')}")
    
    if data.get("is_finished"):
        st["is_running"] = False
        
    return {"ok": True, "status": "ACK", "pairing_code": p_code}

# 5. Live Hardware Status Monitor
@router.get("/api/relay/status")
def relay_status(request: Request, pairing_code: str = Query("JR-DEFAULT"), user_id: str = Query(None)):
    p_code = pairing_code if pairing_code != "JR-DEFAULT" else extract_pairing_code(request)
    return gateway_service.get_device_status(p_code)

# 6. Manual Job Enqueue
@router.post("/api/relay/queue_job")
def queue_job(req: QueueJobRequest):
    gateway_service.queue_job(req.pairing_code, req.dict())
    return {"ok": True, "message": "Job queued successfully."}
