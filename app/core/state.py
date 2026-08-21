import os
import threading
import time
from datetime import datetime
from app.core.config import LOG_FILE

# Global multi-tenant concurrency locks
relay_lock = threading.Lock()

# Multi-tenant state registries keyed by UPPERCASE pairing_code (e.g. 'JR-635287')
user_relay_devices = {}
user_relay_jobs = {}
user_dispatch_states = {}

def get_tenant_dispatch_state(pairing_code: str):
    """Retrieves or initializes an isolated tenant execution state bucket."""
    p_code = (pairing_code or "JR-DEFAULT").strip().upper()
    with relay_lock:
        if p_code not in user_dispatch_states:
            user_dispatch_states[p_code] = {
                "is_running": False,
                "current_index": 0,
                "total": 0,
                "sent_count": 0,
                "failed_count": 0,
                "active_job_id": None,
                "logs": [],
                "stop_requested": False,
                "thread": None
            }
        return user_dispatch_states[p_code]

def write_log(msg: str):
    """Appends thread-safe structured log entry with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except Exception:
        try:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
