import time
import uuid
from app.core.state import user_relay_devices, user_relay_jobs, relay_lock, write_log

class GatewayService:
    def register_device(self, pairing_code: str, device_data: dict) -> dict:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        if not p_code.startswith("JR-") and len(p_code) >= 4:
            p_code = f"JR-{p_code}" if not p_code.startswith("JR") else p_code
        
        dev_name = device_data.get("device_name") or device_data.get("name") or "Android Mobile Gateway"
        sim_slot = device_data.get("sim_slot", 0)
        token = str(uuid.uuid4())
        
        with relay_lock:
            user_relay_devices[p_code] = {
                "last_heartbeat": time.time(),
                "is_online": True,
                "device_id": device_data.get("device_id") or device_data.get("id") or "Mobile-App",
                "device_name": dev_name,
                "carrier": device_data.get("carrier", f"SIM {sim_slot+1}"),
                "battery": device_data.get("battery", "100%"),
                "token": token,
                "android_version": device_data.get("android_version", "Android"),
                "screen_state_text": "Native Background Service (Ready)"
            }
        
        write_log(f"[MobileGateway] Device registered successfully for code: {p_code} ({dev_name})")
        return {
            "ok": True,
            "token": token,
            "access_token": token,
            "id": p_code,
            "pairing_code": p_code,
            "message": "Device paired successfully!"
        }

    def record_heartbeat(self, pairing_code: str, heartbeat_data: dict) -> dict:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        if not p_code.startswith("JR-") and len(p_code) >= 4:
            p_code = f"JR-{p_code}" if not p_code.startswith("JR") else p_code
        
        with relay_lock:
            existing = user_relay_devices.get(p_code, {})
            dev_name = heartbeat_data.get("device_name") or heartbeat_data.get("name") or existing.get("device_name", "Android Mobile Gateway")
            dev_id = heartbeat_data.get("device_id") or heartbeat_data.get("id") or existing.get("device_id", "Mobile-Gateway")
            existing.update({
                "last_heartbeat": time.time(),
                "is_online": True,
                "device_name": dev_name,
                "device": dev_name,
                "device_id": dev_id,
                "battery": heartbeat_data.get("battery", existing.get("battery", "100%")),
                "carrier": heartbeat_data.get("carrier", existing.get("carrier", "SIM 1")),
                "signal_level": heartbeat_data.get("signal_level", existing.get("signal_level", 4)),
                "network_type": heartbeat_data.get("network_type", existing.get("network_type", "LTE")),
                "android_version": heartbeat_data.get("android_version", existing.get("android_version", "Android")),
                "screen_state_text": "Active" if heartbeat_data.get("is_screen_on") else "Screen Locked (Background Service OK)"
            })
            user_relay_devices[p_code] = existing
        return {"ok": True, "status": "ACK", "pairing_code": p_code}

    def drain_jobs(self, pairing_code: str) -> list:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        with relay_lock:
            if p_code in user_relay_jobs and user_relay_jobs[p_code]:
                jobs = user_relay_jobs[p_code]
                user_relay_jobs[p_code] = []
                return jobs
        return []

    def queue_job(self, pairing_code: str, job: dict) -> bool:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        with relay_lock:
            if p_code not in user_relay_jobs:
                user_relay_jobs[p_code] = []
            user_relay_jobs[p_code].append(job)
        return True

    def get_device_status(self, pairing_code: str) -> dict:
        p_code = (pairing_code or "JR-DEFAULT").strip().upper()
        with relay_lock:
            # 1. Direct match
            dev = user_relay_devices.get(p_code)
            
            # 2. Check without prefix or alternate formats
            if not dev:
                raw_code = p_code.replace("JR-", "").replace("JR", "").strip()
                for k, v in user_relay_devices.items():
                    clean_k = k.replace("JR-", "").replace("JR", "").strip()
                    if k == p_code or clean_k == raw_code or k == f"JR-{raw_code}":
                        dev = v
                        p_code = k
                        break
            
            # 3. Fallback: If only 1 phone is active on server in last 90 seconds, bind it
            if not dev and len(user_relay_devices) == 1:
                single_k = list(user_relay_devices.keys())[0]
                single_dev = user_relay_devices[single_k]
                if time.time() - single_dev.get("last_heartbeat", 0) < 90:
                    dev = single_dev
                    p_code = single_k

            if dev:
                time_diff = time.time() - dev.get("last_heartbeat", 0)
                is_active = time_diff < 45
                dev_name = dev.get("device_name") or dev.get("name") or "Android Mobile Gateway"
                carrier = dev.get("carrier") or "Physical SIM"
                battery = dev.get("battery") or "100%"
                return {
                    "ok": True,
                    "is_online": is_active,
                    "connected": is_active,
                    "device_name": dev_name,
                    "device": dev_name,
                    "device_id": dev.get("device_id") or "Mobile-Gateway",
                    "carrier": carrier,
                    "battery": battery,
                    "mode": "Cloud Mobile Gateway (Active)" if is_active else "Standby",
                    "screen_state": dev.get("screen_state_text", "Ready"),
                    "is_screen_locked": False,
                    "last_heartbeat": dev.get("last_heartbeat", 0),
                    "last_seen_seconds_ago": int(time_diff),
                    "pairing_code": p_code
                }
        return {
            "ok": True,
            "is_online": False,
            "connected": False,
            "device_name": None,
            "device": None,
            "mode": "Offline",
            "screen_state": "Awaiting App Connection",
            "pairing_code": p_code
        }

gateway_service = GatewayService()
