import time
import threading
import subprocess
import requests
from app.core.config import settings, ensure_adb_binary
from app.core.state import get_tenant_dispatch_state, write_log
from app.services.quota_service import quota_service
from app.services.gateway_service import gateway_service
from app.services.ai_service import evaluate_spintax

def clean_phone_number(raw_phone: str) -> str:
    cleaned = "".join(c for c in str(raw_phone) if c.isdigit())
    if len(cleaned) == 10:
        cleaned = "91" + cleaned
    elif len(cleaned) == 11 and cleaned.startswith("0"):
        cleaned = "91" + cleaned[1:]
    return f"+{cleaned}" if not cleaned.startswith("+") else cleaned

def send_via_adb(phone: str, text: str, sim_slot: int = 0) -> tuple:
    adb_bin = ensure_adb_binary()
    if not adb_bin:
        return False, "ADB binary not found."
    try:
        clean_text = text.replace('"', '\\"').replace("'", "\\'")
        cmd = [
            adb_bin, "shell", "service", "call", "isms", "7",
            "i32", str(sim_slot),
            "s16", "com.android.mms.service",
            "s16", "null",
            "s16", phone,
            "s16", "null",
            "s16", f"'{clean_text}'",
            "s16", "null", "s16", "null", "i32", "0", "i64", "0"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return True, "SMS dispatched via ADB Hardware Relay."
    except Exception as e:
        return False, f"ADB Dispatch Error: {e}"

def run_campaign_thread(job_id: str, template: str, candidates: list, sim_slot: int, delay: int, pairing_code: str, auto_spin: bool):
    st = get_tenant_dispatch_state(pairing_code)
    st["is_running"] = True
    st["stop_requested"] = False
    st["current_index"] = 0
    st["sent_count"] = 0
    st["failed_count"] = 0
    st["total"] = len(candidates)
    st["active_job_id"] = job_id
    st["logs"] = []

    p_code = (pairing_code or "JR-DEFAULT").strip().upper()
    log_line = f"🚀 [Campaign Started] Recruiter: {p_code} | Target: {st['total']} candidates | Pacing: {delay}s"
    st["logs"].append(log_line)
    write_log(log_line)

    for i, c in enumerate(candidates):
        if st.get("stop_requested"):
            stop_msg = f"⏹️ [Campaign Stopped] Paused at {i}/{st['total']} by recruiter."
            st["logs"].append(stop_msg)
            write_log(stop_msg)
            break

        st["current_index"] = i + 1
        name = c.get("name") or c.get("candidate_name") or "Candidate"
        raw_phone = c.get("phone") or c.get("mobile") or ""
        phone = clean_phone_number(raw_phone)

        # Spintax & Personalization
        msg_body = evaluate_spintax(template, seed=i) if auto_spin else template
        msg_body = msg_body.replace("{name}", name).replace("{candidate_name}", name).replace("{job_title}", c.get("job_title", "Position"))

        # Quota Check
        if not quota_service.can_send():
            quota_err = f"⚠️ [Daily Quota Exceeded] Limit of {quota_service.limit} reached. Campaign paused."
            st["logs"].append(quota_err)
            st["failed_count"] += 1
            break

        # Check Android Gateway Relay vs ADB
        dev_status = gateway_service.get_device_status(p_code)
        if dev_status.get("connected"):
            # Queue to Android Phone
            gateway_service.queue_job(p_code, {
                "id": f"sms_{int(time.time()*1000)}_{i}",
                "phone": phone,
                "message": msg_body,
                "name": name,
                "sim_slot": sim_slot
            })
            ok = True
            res_msg = f"Queued to Android Phone ({dev_status.get('device')})"
        else:
            # Send via ADB
            ok, res_msg = send_via_adb(phone, msg_body, sim_slot)

        if ok:
            st["sent_count"] += 1
            quota_service.record_sent()
            st_msg = f"✅ [{st['current_index']}/{st['total']}] Sent to {name} ({phone})"
        else:
            st["failed_count"] += 1
            st_msg = f"❌ [{st['current_index']}/{st['total']}] Failed for {name}: {res_msg}"
        
        st["logs"].append(st_msg)
        write_log(st_msg)

        if i < len(candidates) - 1 and not st.get("stop_requested"):
            time.sleep(max(1, delay))

    st["is_running"] = False
    done_msg = f"🏁 [Campaign Complete] Finished: {st['sent_count']} sent, {st['failed_count']} failed."
    st["logs"].append(done_msg)
    write_log(done_msg)

class DispatchService:
    def start_campaign(self, req_data: dict) -> dict:
        p_code = (req_data.get("pairing_code") or "JR-DEFAULT").strip().upper()
        st = get_tenant_dispatch_state(p_code)
        
        if st.get("is_running"):
            return {"ok": False, "message": "A campaign is already running for this recruiter workspace."}
        
        candidates = req_data.get("candidates", [])
        if not candidates:
            return {"ok": False, "message": "No candidates selected for dispatch."}

        t = threading.Thread(
            target=run_campaign_thread,
            args=(
                req_data.get("job_id", "JOB_DISPATCH"),
                req_data.get("template_body", ""),
                candidates,
                req_data.get("sim_slot", 0),
                req_data.get("delay_seconds", 5),
                p_code,
                req_data.get("auto_spin", False)
            ),
            daemon=True
        )
        st["thread"] = t
        t.start()
        return {"ok": True, "message": f"Campaign started for {len(candidates)} candidates.", "pairing_code": p_code}

    def stop_campaign(self, pairing_code: str) -> dict:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        st = get_tenant_dispatch_state(p_code)
        if st.get("is_running"):
            st["stop_requested"] = True
            return {"ok": True, "message": f"Stop signal dispatched for recruiter {p_code}."}
        return {"ok": False, "message": "No active campaign running for this workspace."}

    def get_status(self, pairing_code: str) -> dict:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        st = get_tenant_dispatch_state(p_code)
        return {
            "is_running": st.get("is_running", False),
            "current_index": st.get("current_index", 0),
            "total": st.get("total", 0),
            "sent_count": st.get("sent_count", 0),
            "failed_count": st.get("failed_count", 0),
            "active_job_id": st.get("active_job_id"),
            "logs": st.get("logs", [])[-30:] # Return last 30 logs
        }

dispatch_service = DispatchService()
