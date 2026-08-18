#!/usr/bin/env python3
"""
================================================================================
  JobRecruitment — Unified Standalone AI SMS Campaign Studio & Hardware Bridge
  Architecture: Single-File Production Microservice with Built-in Hot-Reloading
  Port: http://localhost:8050
================================================================================
"""

import os
import sys
import json
import time
import re
import shutil
import urllib.parse
import urllib.request
import threading
import subprocess
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ensure UTF-8 output encoding on Windows consoles
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ==============================================================================
# 1. SELF-BOOTSTRAPPING & AUTO-INSTALLER (Zero-Manual-Setup)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLATFORM_TOOLS_DIR = os.path.join(BASE_DIR, "platform-tools")
ENV_FILE = os.path.join(BASE_DIR, ".env")
LOG_FILE = os.path.join(BASE_DIR, "sms_dispatch.log")
QUOTA_FILE = os.path.join(BASE_DIR, "quota_state.json")
SERVER_START_TIME = str(time.time())

# Prepend local platform-tools to PATH
if os.path.exists(PLATFORM_TOOLS_DIR):
    os.environ["PATH"] = PLATFORM_TOOLS_DIR + os.pathsep + os.environ.get("PATH", "")

def ensure_dependencies():
    """Installs required Python packages automatically if missing."""
    needed = []
    try:
        import requests
    except ImportError:
        needed.append("requests")
    try:
        import dotenv
    except ImportError:
        needed.append("python-dotenv")

    if needed:
        print(f"[*] Bootstrapping missing dependencies: {', '.join(needed)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *needed, "--quiet"])
            print("[+] Dependencies installed successfully.")
        except Exception as e:
            print(f"[!] Warning: Automatic pip install encountered an issue: {e}")

ensure_dependencies()

try:
    import requests
    from dotenv import load_dotenv
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
except Exception:
    pass

def ensure_environment_config():
    """Ensures .env exists with production default values."""
    if not os.path.exists(ENV_FILE):
        default_env = (
            "WORKER_API_URL=https://jobrecruitment.in/backend/api/worker-api.php\n"
            "WORKER_API_KEY=\n"
            "GROQ_API_KEY=\n"
            "GEMINI_API_KEY=\n"
            "NVIDIA_API_KEY=\n"
            "SMS_MODE=adb\n"
            "ANDROID_GATEWAY_URL=http://192.168.1.100:8080/send\n"
            "DAILY_SMS_LIMIT=180\n"
            "DISPATCH_DELAY_SECONDS=5\n"
        )
        try:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(default_env)
            print("[+] Created initial .env configuration.")
        except Exception as e:
            print(f"[!] Could not write .env: {e}")

ensure_environment_config()

def ensure_adb_binary():
    """Locates or downloads Google's official portable ADB platform-tools."""
    if shutil.which("adb"):
        return shutil.which("adb")
    
    local_adb = os.path.join(PLATFORM_TOOLS_DIR, "adb.exe" if sys.platform == "win32" else "adb")
    if os.path.exists(local_adb):
        return local_adb
    
    sdk_adb = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    if os.path.exists(sdk_adb):
        return sdk_adb

    if sys.platform == "win32":
        print("[*] ADB not found. Downloading Google Portable Platform-Tools (~12MB)...")
        zip_path = os.path.join(BASE_DIR, "platform-tools.zip")
        try:
            urllib.request.urlretrieve("https://dl.google.com/android/repository/platform-tools-latest-windows.zip", zip_path)
            import zipfile
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(BASE_DIR)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            print("[+] Portable ADB extracted successfully!")
            if os.path.exists(local_adb):
                return local_adb
        except Exception as e:
            print(f"[!] Auto-download ADB failed: {e}")

    return "adb"

ADB_BIN = ensure_adb_binary()

# ==============================================================================
# 2. LOGGING ENGINE (Dual Sink: Disk + Memory Queue)
# ==============================================================================
def write_log(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {text}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass
    return entry

# ==============================================================================
# 3. SERVICE LAYER: QUOTA & TRAI COMPLIANCE (180 SMS/Day + Midnight Reset)
# ==============================================================================
class QuotaService:
    def __init__(self, limit=180, storage_file=QUOTA_FILE):
        self.limit = int(limit)
        self.storage_file = storage_file
        self.state = self._load_state()

    def _get_today_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def _load_state(self):
        today = self._get_today_str()
        default_state = {
            "current_date": today,
            "sent_today": 0,
            "last_reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reset_history": []
        }
        if not os.path.exists(self.storage_file):
            self._save_state(default_state)
            return default_state
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("current_date") != today:
                reset_entry = {
                    "from_date": data.get("current_date"),
                    "to_date": today,
                    "final_count": data.get("sent_today", 0),
                    "reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "MIDNIGHT_RESET_SUCCESS"
                }
                data["current_date"] = today
                data["sent_today"] = 0
                data["last_reset_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history = data.get("reset_history", [])
                history.append(reset_entry)
                data["reset_history"] = history[-30:]
                self._save_state(data)
            return data
        except Exception:
            self._save_state(default_state)
            return default_state

    def _save_state(self, data):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def check_quota(self, requested_count=1):
        self.state = self._load_state()
        sent = self.state.get("sent_today", 0)
        remaining = max(0, self.limit - sent)
        if remaining <= 0:
            return False, 0, f"Daily TRAI limit ({self.limit}/day) reached. Auto-resets at midnight."
        if requested_count > remaining:
            return False, remaining, f"Requested {requested_count} exceeds remaining quota ({remaining}/{self.limit})."
        return True, remaining, f"Quota OK: {sent}/{self.limit} sent today."

    def record_sent(self, count=1):
        self.state = self._load_state()
        self.state["sent_today"] = self.state.get("sent_today", 0) + count
        self._save_state(self.state)
        return self.state["sent_today"]

    def manual_reset(self):
        today = self._get_today_str()
        reset_entry = {
            "from_date": today,
            "to_date": today,
            "final_count": self.state.get("sent_today", 0),
            "reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "MANUAL_RESET_TRIGGERED"
        }
        self.state["sent_today"] = 0
        self.state["last_reset_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = self.state.get("reset_history", [])
        history.append(reset_entry)
        self.state["reset_history"] = history[-30:]
        self._save_state(self.state)
        return True, "Quota reset to 0/180."

# ==============================================================================
# 3.5. SERVICE LAYER: SUPABASE POSTGRESQL CLOUD AUDIT LEDGER
# ==============================================================================
class SupabaseAuditService:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv("SUPABASE_DB_URL")
        self.enabled = bool(self.db_url)

    def log_dispatch(self, cand_name, phone, role, msg, status, carrier="Jio True5G", gateway_mode="adb", error_reason=None, campaign_id=None):
        if not self.enabled:
            return
        def _bg_insert():
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=8)
                conn.autocommit = True
                cur = conn.cursor()
                char_cnt = len(msg or "")
                credit_units = 1 if char_cnt <= 160 else 2
                cur.execute("""
                    INSERT INTO sms_dispatch_logs 
                    (campaign_id, candidate_name, candidate_phone, candidate_role, message_body, char_count, credit_units, gateway_mode, sim_carrier, status, error_reason, dispatched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    campaign_id, cand_name, phone, role, msg, char_cnt, credit_units, gateway_mode, carrier, status, error_reason
                ))
                conn.close()
            except Exception as e:
                write_log(f"Supabase logging error: {e}")

        threading.Thread(target=_bg_insert, daemon=True).start()

    def create_campaign(self, title, template_body, total_cands, role=None, location=None):
        if not self.enabled:
            import uuid
            return str(uuid.uuid4())
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sms_campaigns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title TEXT NOT NULL,
                    template_body TEXT NOT NULL,
                    total_candidates INT DEFAULT 0,
                    sent_count INT DEFAULT 0,
                    failed_count INT DEFAULT 0,
                    role TEXT,
                    location TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                INSERT INTO sms_campaigns (title, template_body, total_candidates, role, location)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (title, template_body, total_cands, role, location))
            row = cur.fetchone()
            conn.close()
            return str(row[0]) if row else None
        except Exception as e:
            write_log(f"create_campaign error: {e}")
            import uuid
            return str(uuid.uuid4())

    def update_campaign_stats(self, campaign_id, sent_count, failed_count):
        if not self.enabled or not campaign_id:
            return
        def _bg_update():
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=8)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    UPDATE sms_campaigns
                    SET sent_count = %s, failed_count = %s
                    WHERE id = %s
                """, (sent_count, failed_count, campaign_id))
                conn.close()
            except Exception:
                pass
        threading.Thread(target=_bg_update, daemon=True).start()

    def fetch_campaign_history(self, limit=30):
        if not self.enabled:
            return []
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, template_body, total_candidates, sent_count, failed_count, role, location, created_at
                FROM sms_campaigns
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            campaigns = []
            for r in rows:
                campaigns.append({
                    "id": str(r[0]),
                    "title": r[1],
                    "template": r[2],
                    "total": r[3],
                    "sent": r[4],
                    "failed": r[5],
                    "role": r[6] or "General",
                    "location": r[7] or "India",
                    "timestamp": r[8].strftime("%Y-%m-%d %H:%M") if r[8] else "N/A"
                })
            conn.close()
            return campaigns
        except Exception as e:
            write_log(f"fetch_campaign_history error: {e}")
            return []

    def fetch_recent_logs(self, limit=50):
        if not self.enabled:
            return []
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, candidate_name, candidate_phone, candidate_role, message_body, status, sim_carrier, gateway_mode, dispatched_at, error_reason
                FROM sms_dispatch_logs
                ORDER BY dispatched_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "id": str(r[0]),
                    "name": r[1],
                    "phone": r[2],
                    "role": r[3],
                    "message": r[4],
                    "status": r[5],
                    "carrier": r[6],
                    "gateway": r[7],
                    "timestamp": r[8].strftime("%Y-%m-%d %H:%M:%S") if r[8] else "N/A",
                    "error": r[9]
                })
            conn.close()
            return logs
        except Exception as e:
            write_log(f"Supabase fetch_recent_logs error: {e}")
            return []

    # --- TEAM AUTH METHODS (With High-Availability SQLite/JSON Fallback) ---
    def _get_local_users(self):
        uf = os.path.join(BASE_DIR, "studio_users.json")
        if os.path.exists(uf):
            try:
                with open(uf, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_local_users(self, users):
        uf = os.path.join(BASE_DIR, "studio_users.json")
        try:
            with open(uf, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2)
        except Exception:
            pass

    def signup_user(self, email, password, full_name, role="recruiter"):
        email_clean = email.lower().strip()
        name_clean = full_name.strip()
        import hashlib, uuid
        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        # 1. Try Supabase Cloud DB
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS studio_users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR(150) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        full_name VARCHAR(100) NOT NULL,
                        role VARCHAR(20) NOT NULL DEFAULT 'recruiter',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    INSERT INTO studio_users (email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, full_name, role
                """, (email_clean, pwd_hash, name_clean, role))
                user = cur.fetchone()
                conn.close()
                return True, {"id": str(user[0]), "email": user[1], "name": user[2], "role": user[3]}
            except Exception as e:
                err = str(e)
                if "unique" in err.lower():
                    return False, "Email is already registered. Please sign in."
                write_log(f"[Auth] Supabase direct error: {err}. Switching to Local High-Availability Store...")

        # 2. Resilient Local Fallback
        users = self._get_local_users()
        if email_clean in users:
            return False, "Email is already registered. Please sign in."
        
        uid = str(uuid.uuid4())
        user_record = {
            "id": uid,
            "email": email_clean,
            "name": name_clean,
            "role": role,
            "password_hash": pwd_hash,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        users[email_clean] = user_record
        self._save_local_users(users)
        return True, {"id": uid, "email": email_clean, "name": name_clean, "role": role}

    def login_user(self, email, password):
        email_clean = email.lower().strip()
        import hashlib
        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        # 1. Try Supabase Cloud DB
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, email, full_name, role, password_hash
                    FROM studio_users
                    WHERE email = %s
                """, (email_clean,))
                user = cur.fetchone()
                conn.close()
                if user:
                    if user[4] != pwd_hash:
                        return False, "Invalid password. Please try again."
                    return True, {"id": str(user[0]), "email": user[1], "name": user[2], "role": user[3]}
            except Exception as e:
                write_log(f"[Auth] Supabase query error: {e}. Checking Local Store...")

        # 2. Local Fallback
        users = self._get_local_users()
        if email_clean in users:
            u = users[email_clean]
            if u.get("password_hash") != pwd_hash:
                return False, "Invalid password. Please try again."
            return True, {"id": u["id"], "email": u["email"], "name": u["name"], "role": u.get("role", "recruiter")}

        return False, "No account found with this email. Please register first."

    # --- CLOUD TEMPLATE METHODS ---
    def fetch_templates(self, user_id=None):
        if not self.enabled:
            return []
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            cur = conn.cursor()
            if user_id:
                cur.execute("""
                    SELECT id, title, category, visibility, template_body, char_count, usage_count, user_id
                    FROM sms_templates
                    WHERE visibility = 'public' OR user_id = %s
                    ORDER BY usage_count DESC, created_at DESC
                """, (user_id,))
            else:
                cur.execute("""
                    SELECT id, title, category, visibility, template_body, char_count, usage_count, user_id
                    FROM sms_templates
                    WHERE visibility = 'public'
                    ORDER BY usage_count DESC, created_at DESC
                """)
            rows = cur.fetchall()
            templates = []
            for r in rows:
                templates.append({
                    "id": str(r[0]),
                    "title": r[1],
                    "category": r[2],
                    "visibility": r[3],
                    "body": r[4],
                    "char_count": r[5],
                    "usage_count": r[6],
                    "is_mine": str(r[7]) == str(user_id) if user_id and r[7] else False
                })
            conn.close()
            return templates
        except Exception as e:
            write_log(f"Supabase fetch_templates error: {e}")
            return []

    def save_template(self, title, category, body, visibility="public", user_id=None):
        if not self.enabled:
            return False, "Database connection not available."
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sms_templates (user_id, title, category, visibility, template_body, char_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, title.strip(), category.strip(), visibility, body.strip(), len(body.strip())))
            new_id = cur.fetchone()[0]
            conn.close()
            return True, str(new_id)
        except Exception as e:
            return False, f"Save Template Error: {str(e)}"

    def delete_template(self, template_id, user_id=None):
        if not self.enabled:
            return False, "Database connection not available."
        try:
            import psycopg2
            conn = psycopg2.connect(self.db_url, connect_timeout=8)
            conn.autocommit = True
            cur = conn.cursor()
            if user_id:
                cur.execute("DELETE FROM sms_templates WHERE id = %s AND (user_id = %s OR user_id IS NULL)", (template_id, user_id))
            else:
                cur.execute("DELETE FROM sms_templates WHERE id = %s", (template_id,))
            conn.close()
            return True, "Template deleted."
        except Exception as e:
            return False, f"Delete Error: {str(e)}"

# ==============================================================================
# 4. SERVICE LAYER: HARDWARE RADIO BRIDGE (Android ADB / Wi-Fi Gateway)
# ==============================================================================
class SMSGatewayService:
    def __init__(self, mode="adb", gateway_url="http://192.168.1.100:8080/send"):
        self.mode = mode.lower()
        self.gateway_url = gateway_url

    @staticmethod
    def clean_phone(phone_str):
        if not phone_str:
            return None
        cleaned = re.sub(r'[^0-9]', '', str(phone_str))
        if cleaned.startswith('91') and len(cleaned) == 12:
            cleaned = cleaned[2:]
        elif cleaned.startswith('0') and len(cleaned) == 11:
            cleaned = cleaned[1:]
        if len(cleaned) == 10 and cleaned[0] in ['6', '7', '8', '9']:
            return cleaned
        return None

    def check_phone_connection(self):
        diag = self.get_full_diagnostics()
        if diag.get("all_ok"):
            return True, f"Ready: {diag.get('device_name')} ({diag.get('carrier')})"
        return False, diag.get("status_message", "Hardware not ready")

    def get_full_diagnostics(self):
        """Performs comprehensive 5-point hardware health check."""
        diag = {
            "all_ok": False,
            "adb_connected": False,
            "device_id": "None",
            "device_name": "Unknown",
            "android_version": "Unknown",
            "screen_width": 1080,
            "screen_height": 2340,
            "is_screen_locked": False,
            "screen_state_text": "Unknown",
            "carrier": "Unknown",
            "is_sim_ready": False,
            "status_message": "Checking..."
        }

        if self.mode != "adb":
            try:
                res = requests.get(self.gateway_url.replace('/send', '/status'), timeout=3)
                if res.status_code in [200, 404]:
                    diag["all_ok"] = True
                    diag["device_name"] = "Wi-Fi HTTP Gateway"
                    diag["carrier"] = "Connected via LAN/Wi-Fi"
                    diag["is_sim_ready"] = True
                    diag["status_message"] = "HTTP Gateway APK is active."
                    return diag
                diag["status_message"] = f"HTTP Gateway returned {res.status_code}"
                return diag
            except Exception as e:
                diag["status_message"] = f"HTTP Gateway unreachable: {e}"
                return diag

        adb_cmd = ensure_adb_binary()
        try:
            res_dev = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=3)
            lines = [l for l in res_dev.stdout.strip().split('\n')[1:] if l.strip()]
            attached = [l.split()[0] for l in lines if '\tdevice' in l]
            offline_devs = [l.split()[0] for l in lines if '\toffline' in l]
            unauth = [l.split()[0] for l in lines if '\tunauthorized' in l]

            # Auto-Heal: Reconnect offline sockets
            if not attached and offline_devs:
                target = offline_devs[0]
                subprocess.run([adb_cmd, "disconnect", target], capture_output=True, timeout=2)
                subprocess.run([adb_cmd, "connect", target], capture_output=True, timeout=3)
                res_dev2 = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=2)
                lines2 = [l for l in res_dev2.stdout.strip().split('\n')[1:] if l.strip()]
                attached = [l.split()[0] for l in lines2 if '\tdevice' in l]

            if unauth:
                diag["status_message"] = "Phone attached but unauthorized. Unlock screen and tap 'Allow USB debugging'."
                return diag
            if not attached:
                diag["status_message"] = "No Android phone detected. Plug USB cable or reconnect Wi-Fi Debugging."
                return diag

            dev_id = attached[0]
            diag["adb_connected"] = True
            diag["device_id"] = dev_id

            # O(1) Single-Pass Multi-Property Batch Probe (< 200ms)
            # Extracts: mfg, model, release, battery, wm size, keyguard, telephony
            probe_script = "getprop ro.product.manufacturer; echo '===P1==='; getprop ro.product.model; echo '===P2==='; getprop ro.build.version.release; echo '===P3==='; dumpsys battery; echo '===P4==='; wm size; echo '===P5==='; dumpsys window; echo '===P6==='; dumpsys telephony.registry"
            probe_res = subprocess.run([adb_cmd, "-s", dev_id, "shell", probe_script], capture_output=True, text=True, timeout=5)
            parts = probe_res.stdout.split('===P')
            
            p_mfg = parts[0].strip().title() if len(parts) > 0 else "Android"
            p_model = parts[1].replace('1===', '').strip() if len(parts) > 1 else "Device"
            p_ver = parts[2].replace('2===', '').strip() if len(parts) > 2 else "14"
            p_bat = parts[3].replace('3===', '') if len(parts) > 3 else ""
            p_wm = parts[4].replace('4===', '') if len(parts) > 4 else ""
            p_win = parts[5].replace('5===', '') if len(parts) > 5 else ""
            p_tel = parts[6].replace('6===', '') if len(parts) > 6 else ""

            # 1. Device Info
            diag["device_name"] = f"{p_mfg} {p_model}".strip() or "Android Device"
            diag["android_version"] = f"Android {p_ver}" if p_ver else "Android OS"

            # 2. Battery & Thermal Status
            bat_lvl_m = re.search(r'level:\s*(\d+)', p_bat)
            bat_temp_m = re.search(r'temperature:\s*(\d+)', p_bat)
            bat_ac_m = re.search(r'AC powered:\s*(true|false)', p_bat, re.I)
            bat_usb_m = re.search(r'USB powered:\s*(true|false)', p_bat, re.I)

            bat_level = int(bat_lvl_m.group(1)) if bat_lvl_m else 100
            raw_temp = int(bat_temp_m.group(1)) if bat_temp_m else 300
            temp_c = round(raw_temp / 10.0, 1)
            is_charging = (bat_ac_m and bat_ac_m.group(1).lower() == 'true') or (bat_usb_m and bat_usb_m.group(1).lower() == 'true')

            diag["battery_level"] = bat_level
            diag["battery_text"] = f"{bat_level}% ({'Charging ⚡' if is_charging else 'Discharging'})"
            diag["temperature_c"] = temp_c
            diag["temperature_text"] = f"{temp_c}°C ({'Cool ❄️' if temp_c < 36 else 'Warm ♨️'})"

            # 3. Screen Size & Calibrated Coordinates
            size_m = re.search(r'(\d+)x(\d+)', p_wm)
            if size_m:
                diag["screen_width"] = int(size_m.group(1))
                diag["screen_height"] = int(size_m.group(2))
            diag["tap_coords"] = f"X: {int(diag['screen_width']*0.91)}, Y: {int(diag['screen_height']*0.94)}"

            # 4. Lockscreen & Display State
            is_locked = "mDreamingLockscreen=true" in p_win or "mShowingDream=true" in p_win or "keyguard_upper_fingerprint_indication" in p_win
            diag["is_screen_locked"] = is_locked
            diag["screen_state_text"] = "⚠️ Screen Locked (Click Unlock Below)" if is_locked else "🟢 Screen ON & Unlocked (Ready)"

            # 5. Carrier & SIM
            carriers = list(set(re.findall(r'mOperatorAlphaLong=([^,\n]+)', p_tel)))
            carriers = [c.strip() for c in carriers if c.strip() and "null" not in c.lower()]
            if carriers:
                diag["carrier"] = " / ".join(carriers)
                diag["is_sim_ready"] = True
            else:
                diag["carrier"] = "SIM Active / Cellular Radio"
                diag["is_sim_ready"] = True

            # 6. Supabase Cloud DB Ping Latency
            db_ping_ms = 0
            if supabase_service.enabled:
                try:
                    import psycopg2
                    t0 = time.time()
                    conn = psycopg2.connect(supabase_service.db_url, connect_timeout=3)
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    conn.close()
                    db_ping_ms = int((time.time() - t0) * 1000)
                except Exception:
                    db_ping_ms = -1
            diag["db_latency_ms"] = db_ping_ms
            diag["db_status_text"] = f"{db_ping_ms}ms (Connected)" if db_ping_ms > 0 else "Disconnected"

            diag["all_ok"] = True
            if is_locked:
                diag["status_message"] = "Device connected! Please keep phone screen UNLOCKED for automatic SMS clicking."
            else:
                diag["status_message"] = f"All systems GO! Ready to dispatch via {diag['device_name']} ({diag['carrier']})."

            return diag
        except Exception as e:
            diag["status_message"] = f"Diagnostic probe error: {e}"
            return diag

    def send_sms(self, phone, message):
        clean_num = self.clean_phone(phone)
        if not clean_num:
            return False, f"Invalid Indian mobile: {phone}"
        if not message or not message.strip():
            return False, "Message body cannot be empty"

        if self.mode == "adb":
            return self._send_via_adb(clean_num, message.strip())
        return self._send_via_http(clean_num, message.strip())

    def _send_via_adb(self, phone, message):
        adb_cmd = ensure_adb_binary()
        try:
            diag = self.get_full_diagnostics()
            if not diag.get("adb_connected"):
                return False, diag.get("status_message")

            dev_id = diag.get("device_id")
            s_flags = ["-s", dev_id] if dev_id and dev_id != "None" else []

            # 1. Wake Screen & Dismiss Keyguard
            subprocess.run([adb_cmd] + s_flags + ["shell", "input", "keyevent", "224"], timeout=3)
            subprocess.run([adb_cmd] + s_flags + ["shell", "wm", "dismiss-keyguard"], timeout=3)
            subprocess.run([adb_cmd] + s_flags + ["shell", "input", "keyevent", "82"], timeout=2) # Menu/Unlock fallback

            # 2. Launch SMS conversation draft in default messaging app
            encoded_msg = urllib.parse.quote(message)
            am_cmd = f'"{adb_cmd}" {"-s " + dev_id if dev_id else ""} shell am start -a android.intent.action.SENDTO -d "sms:{phone}?body={encoded_msg}" --ez exit_on_sent true'
            subprocess.run(am_cmd, shell=True, capture_output=True, timeout=6)
            
            # Wait for activity to transition and render send button
            time.sleep(0.9)

            # 3. Precision Multi-Point Send Triggers (Calibrated for Samsung OneUI & Google Messages)
            w = diag.get("screen_width", 1080)
            h = diag.get("screen_height", 2400)
            
            # Button Location 1: Below input (Keyboard closed) -> e.g. (980, 2260) on 1080x2400
            tap_x1 = int(w * 0.91)
            tap_y1 = int(h * 0.94)

            # Button Location 2: Above Samsung Keyboard -> e.g. (980, 1350)
            tap_x2 = int(w * 0.91)
            tap_y2 = int(h * 0.56)

            # Trigger 1: Tap primary send button position
            subprocess.run([adb_cmd] + s_flags + ["shell", "input", "tap", str(tap_x1), str(tap_y1)], timeout=3)
            time.sleep(0.15)
            # Trigger 2: Tap above keyboard send button position
            subprocess.run([adb_cmd] + s_flags + ["shell", "input", "tap", str(tap_x2), str(tap_y2)], timeout=3)
            time.sleep(0.15)
            # Trigger 3: Send Keyevent 66 (Enter/Submit)
            subprocess.run([adb_cmd] + s_flags + ["shell", "input", "keyevent", "66"], timeout=2)

            return True, f"Dispatched via Physical SIM ({diag.get('carrier')})"
        except FileNotFoundError:
            return False, "ADB binary not found."
        except Exception as e:
            return False, f"ADB Dispatch Error: {str(e)}"

    def _send_via_http(self, phone, message):
        try:
            payload = {"to": f"+91{phone}", "message": message}
            res = requests.post(self.gateway_url, json=payload, timeout=8)
            if res.status_code in [200, 201, 202]:
                return True, "Dispatched via HTTP Gateway APK"
            return False, f"Gateway Error {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Gateway Network Error: {str(e)}"

# ==============================================================================
# 5. SERVICE LAYER: LIVE CANDIDATE & PORTAL API CLIENT
# ==============================================================================
class CandidateService:
    def __init__(self, api_url, api_key=""):
        self.api_url = (api_url or "https://jobrecruitment.in/backend/api/worker-api.php").rstrip('?')
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def fetch_admin_jobs(self, status=""):
        try:
            params = {"action": "get_admin_jobs"}
            if status:
                params["status"] = status
            r = requests.get(self.api_url, headers=self.headers, params=params, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("jobs", [])
        except Exception as e:
            write_log(f"CandidateService fetch_admin_jobs error: {e}")
        return []

    def fetch_job_applicants(self, job_id, status_filter=None):
        try:
            params = {"action": "get_job_applicants_data", "job_id": job_id}
            if status_filter:
                params["status"] = status_filter
            r = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    cands = []
                    for c in data.get("cands", []):
                        cleaned_phone = SMSGatewayService.clean_phone(c.get("phone"))
                        if cleaned_phone:
                            c["phone"] = cleaned_phone
                            cands.append(c)
                    return cands, data.get("job", {})
        except Exception as e:
            write_log(f"CandidateService fetch_job_applicants error: {e}")
        return [], {}

    def fetch_global_candidates(self, role=None, city=None, status=None, limit=100):
        try:
            params = {"action": "get_all_campaign_cands", "limit": limit}
            if role:
                params["role"] = role
            if city:
                params["city"] = city
            if status:
                params["status"] = status
            r = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    cands = []
                    for c in data.get("cands", []):
                        cleaned_phone = SMSGatewayService.clean_phone(c.get("phone"))
                        if cleaned_phone:
                            c["phone"] = cleaned_phone
                            cands.append(c)
                    return cands, len(cands)
        except Exception as e:
            write_log(f"CandidateService fetch_global_candidates error: {e}")
        return [], 0

# ==============================================================================
# 6. SERVICE LAYER: AI COPYWRITER & PROMPT COMPILER
# ==============================================================================
class AIService:
    def __init__(self, groq_key=None, gemini_key=None, nvidia_key=None, openai_key=None):
        self.groq_key = groq_key
        self.gemini_key = gemini_key
        self.nvidia_key = nvidia_key
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")

    def get_available_models(self):
        models = []
        # Groq Models
        if self.groq_key:
            models.extend([
                {"id": "groq/llama-3.3-70b-versatile", "name": "Llama 3.3 70B (Groq Fast)", "provider": "groq", "model": "llama-3.3-70b-versatile"},
                {"id": "groq/llama-3.1-8b-instant", "name": "Llama 3.1 8B (Groq Instant)", "provider": "groq", "model": "llama-3.1-8b-instant"},
                {"id": "groq/qwen-2.5-32b", "name": "Qwen 2.5 32B (Groq HR)", "provider": "groq", "model": "qwen/qwen3.6-27b"},
                {"id": "groq/mixtral-8x7b-32768", "name": "Mixtral 8x7B (Groq)", "provider": "groq", "model": "mixtral-8x7b-32768"}
            ])
        # Google Gemini Models
        if self.gemini_key:
            models.extend([
                {"id": "gemini/gemini-2.5-flash", "name": "Gemini 2.5 Flash (Google)", "provider": "gemini", "model": "gemini-2.5-flash"},
                {"id": "gemini/gemini-1.5-flash", "name": "Gemini 1.5 Flash (Google)", "provider": "gemini", "model": "gemini-1.5-flash"},
                {"id": "gemini/gemini-1.5-pro", "name": "Gemini 1.5 Pro (Google Deep)", "provider": "gemini", "model": "gemini-1.5-pro"}
            ])
        # NVIDIA NIM Models
        if self.nvidia_key:
            models.extend([
                {"id": "nvidia/meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B (NVIDIA NIM)", "provider": "nvidia", "model": "meta/llama-3.3-70b-instruct"},
                {"id": "nvidia/deepseek-ai/deepseek-r1", "name": "DeepSeek R1 (NVIDIA)", "provider": "nvidia", "model": "deepseek-ai/deepseek-r1"}
            ])
        # OpenAI Models
        if self.openai_key:
            models.extend([
                {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini (OpenAI)", "provider": "openai", "model": "gpt-4o-mini"},
                {"id": "openai/gpt-4o", "name": "GPT-4o (OpenAI Flagship)", "provider": "openai", "model": "gpt-4o"}
            ])
        if not models:
            models.append({"id": "default", "name": "Built-in Rule Engine (Free)", "provider": "default", "model": "default"})
        return models

    def generate_sms_template(self, prompt, job_role=None, location=None, company="Job Recruitment", model_id=None):
        extracted_urls = re.findall(r'https?://[^\s]+', prompt)
        url_text = extracted_urls[0] if extracted_urls else "https://jobrecruitment.in/jobs"

        if model_id and "/" in model_id:
            provider, model_name = model_id.split("/", 1)
            if provider == "groq" and self.groq_key:
                res = self._call_groq(prompt, job_role, location, company, url_text, specific_model=model_name)
                if res: return res
            elif provider == "gemini" and self.gemini_key:
                res = self._call_gemini(prompt, job_role, location, company, url_text, specific_model=model_name)
                if res: return res
            elif provider == "nvidia" and self.nvidia_key:
                res = self._call_nvidia(prompt, job_role, location, company, url_text, specific_model=model_name)
                if res: return res
            elif provider == "openai" and self.openai_key:
                res = self._call_openai(prompt, job_role, location, company, url_text, specific_model=model_name)
                if res: return res

        # Default fallback cascade
        if self.groq_key:
            res = self._call_groq(prompt, job_role, location, company, url_text)
            if res: return res
        if self.gemini_key:
            res = self._call_gemini(prompt, job_role, location, company, url_text)
            if res: return res
        if self.nvidia_key:
            res = self._call_nvidia(prompt, job_role, location, company, url_text)
            if res: return res

        if "whatsapp" in prompt.lower() and extracted_urls:
            return f"Dear {{name}}, join Job Recruitment's official WhatsApp jobs group for instant job alerts in {location or 'Ahmedabad'}: {extracted_urls[0]}"
        if extracted_urls:
            return f"Dear {{name}}, opening for {job_role or 'Candidate'} in {location or 'Ahmedabad'}. Check details: {extracted_urls[0]}"
        return f"Dear {{name}}, Job Recruitment has an urgent opening for {job_role or 'Candidate'} in {location or 'Ahmedabad'}. Apply here: https://jobrecruitment.in/jobs"

    def _get_anti_spam_system_prompt(self, url_text):
        return (
            "You are a professional HR Communication Engine for JobRecruitment.in. "
            "Your sole objective is to write polite, clean, human-like SMS interview and job notifications for candidates. "
            "CRITICAL ANTI-SPAM COMPLIANCE RULES: "
            "1. NO spam trigger keywords: Do NOT use 'URGENT', 'HURRY', 'EARN MONEY', 'CLICK NOW', or words in ALL CAPS. "
            "2. Tone must be professional, courteous, and authentic (e.g. 'Job opportunity', 'Interview invitation', 'Application update'). "
            f"3. Must include the exact official URL: {url_text}. "
            "4. Must include dynamic tag {name} for candidate personalization. "
            "5. Keep total length strictly between 90 and 140 characters so dynamic tags and signature fit into 1 single SMS credit. "
            "6. Output ONLY the raw SMS message body. Do NOT include quotation marks, markdown, explanations, notes, or intros."
        )

    def _call_groq(self, prompt, job_role, location, company, url_text, specific_model=None):
        try:
            headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            system_msg = self._get_anti_spam_system_prompt(url_text)
            models_to_try = [specific_model] if specific_model else ["llama-3.3-70b-versatile", "qwen/qwen3.6-27b", "llama-3.1-8b-instant"]
            for m in models_to_try:
                payload = {
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": f"Candidate notification requirement: {prompt}. Target Job: {job_role} in {location}."}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 100
                }
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=6)
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"].strip()
                    clean = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip().strip('"\' \n')
                    if clean and 10 < len(clean) < 180:
                        return clean
        except Exception:
            pass
        return None

    def _call_gemini(self, prompt, job_role, location, company, url_text, specific_model="gemini-2.5-flash"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{specific_model}:generateContent?key={self.gemini_key}"
            sys_text = self._get_anti_spam_system_prompt(url_text)
            payload = {
                "contents": [{
                    "parts": [{"text": f"{sys_text}\n\nTask: Draft SMS for {prompt}, Role: {job_role}, Location: {location}."}]
                }]
            }
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=6)
            if r.status_code == 200:
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"\' \n')
                if text and len(text) < 180:
                    return text
        except Exception:
            pass
        return None

    def _call_nvidia(self, prompt, job_role, location, company, url_text, specific_model="meta/llama-3.3-70b-instruct"):
        try:
            headers = {"Authorization": f"Bearer {self.nvidia_key}", "Content-Type": "application/json"}
            system_msg = self._get_anti_spam_system_prompt(url_text)
            payload = {
                "model": specific_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Task: {prompt} for {job_role} in {location}."}
                ],
                "max_tokens": 100,
                "temperature": 0.2
            }
            r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip().strip('"\' \n')
        except Exception:
            pass
        return None

    def _call_openai(self, prompt, job_role, location, company, url_text, specific_model="gpt-4o-mini"):
        try:
            headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
            system_msg = self._get_anti_spam_system_prompt(url_text)
            payload = {
                "model": specific_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Task: {prompt} for {job_role} in {location}."}
                ],
                "max_tokens": 100,
                "temperature": 0.2
            }
            r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip().strip('"\' \n')
        except Exception:
            pass
        return None

# ==============================================================================
# 7. ORCHESTRATION & STATE CONTAINER
# ==============================================================================
def reload_app_config():
    global WORKER_URL, WORKER_KEY, GROQ_KEY, GEMINI_KEY, NVIDIA_KEY, OPENAI_KEY, SMS_MODE, GATEWAY_URL, DAILY_LIMIT, DISPATCH_DELAY
    global candidate_service, ai_service, gateway_service, quota_service, supabase_service

    if os.path.exists(ENV_FILE):
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE, override=True)
        except Exception:
            pass

    WORKER_URL = os.getenv("WORKER_API_URL", "https://jobrecruitment.in/backend/api/worker-api.php")
    WORKER_KEY = os.getenv("WORKER_API_KEY", "")
    GROQ_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
    NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
    SMS_MODE = os.getenv("SMS_MODE", "adb")
    GATEWAY_URL = os.getenv("ANDROID_GATEWAY_URL", "http://192.168.1.100:8080/send")
    DAILY_LIMIT = int(os.getenv("DAILY_SMS_LIMIT", "180"))
    DISPATCH_DELAY = int(os.getenv("DISPATCH_DELAY_SECONDS", "5"))

    candidate_service = CandidateService(WORKER_URL, WORKER_KEY)
    ai_service = AIService(GROQ_KEY, GEMINI_KEY, NVIDIA_KEY, OPENAI_KEY)
    gateway_service = SMSGatewayService(SMS_MODE, GATEWAY_URL)
    quota_service = QuotaService(DAILY_LIMIT)
    supabase_service = SupabaseAuditService(os.getenv("SUPABASE_DB_URL"))

reload_app_config()

dispatch_lock = threading.Lock()
current_dispatch = {
    "is_running": False,
    "total": 0,
    "current_index": 0,
    "sent_count": 0,
    "failed_count": 0,
    "logs": []
}

# ==============================================================================
# 8. PRESENTATION LAYER: HIGH-PERFORMANCE WEB UI & INTERACTIVE MODALS
# ==============================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobRecruitment AI SMS Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-4 md:p-6 antialiased">
    <div class="max-w-6xl mx-auto space-y-6">
        
        <!-- Header & Nav Menu -->
        <header class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-5 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-400 flex items-center justify-center text-slate-950 shadow-lg shadow-teal-500/20 font-black text-xl">
                    JR
                </div>
                <div>
                    <h1 class="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                        AI SMS Campaign Studio
                        <span class="text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                            Hot Reload Active
                        </span>
                    </h1>
                    <p class="text-xs text-slate-400">100% Free Physical Android Phone SIM Radio Gateway</p>
                </div>
            </div>

            <!-- Top Navigation Menu -->
            <div class="flex flex-wrap items-center gap-2 w-full md:w-auto justify-end">
                <!-- 1. Quick Guide Button -->
                <button onclick="openModal('modal-guide')" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-teal-400 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm" title="Step-by-Step Prerequisites Guide">
                    <span class="material-symbols-outlined text-base">menu_book</span>
                    <span>Quick Guide</span>
                </button>

                <!-- 2. Quota History Button -->
                <button onclick="openQuotaModal()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm" title="TRAI Quota & Reset History">
                    <span class="material-symbols-outlined text-base text-emerald-400">stacked_bar_chart</span>
                    <span id="nav-quota-badge">0 / 180</span>
                </button>

                <!-- 3. Logs Viewer Button -->
                <button onclick="openLogsModal()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm" title="View Full System Logs">
                    <span class="material-symbols-outlined text-base text-amber-400">terminal</span>
                    <span>Logs</span>
                </button>

                <!-- 4. Settings Button -->
                <button onclick="openSettingsModal()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm" title="Configure API Keys & Settings">
                    <span class="material-symbols-outlined text-base text-purple-400">settings</span>
                    <span>Config</span>
                </button>

                <!-- 5. Phone Test Button -->
                <button onclick="checkHardware()" class="p-2 bg-slate-800 hover:bg-slate-700 text-teal-400 rounded-xl border border-slate-700 transition shadow-sm" title="Test Phone Connection">
                    <span class="material-symbols-outlined text-base">phone_android</span>
                </button>
            </div>
        </header>

        <!-- Main Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            <!-- Left: Audience & Candidate Selector -->
            <div class="lg:col-span-7 space-y-6">
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-lg">
                    <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <span class="material-symbols-outlined text-teal-400 text-base">group</span>
                        1. Select Target Audience
                    </h2>

                    <div class="grid grid-cols-3 gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800/80">
                        <button onclick="switchSource('jobs')" id="tab-jobs" class="py-2 text-xs font-bold rounded-lg transition text-slate-200 bg-slate-800 shadow">Manage Jobs</button>
                        <button onclick="switchSource('search')" id="tab-search" class="py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-slate-200">Global Search</button>
                        <button onclick="switchSource('single')" id="tab-single" class="py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-slate-200">Single Test</button>
                    </div>

                    <div id="section-jobs" class="space-y-3">
                        <label class="text-xs font-semibold text-slate-300">Select Job Posting from Portal:</label>
                        <div class="flex gap-2">
                            <select id="job-select" onchange="loadJobApplicants()" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-200 focus:border-teal-500 outline-none">
                                <option value="">Loading live jobs...</option>
                            </select>
                            <button onclick="loadAdminJobs()" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 text-xs font-semibold flex items-center gap-1" title="Refresh Jobs">
                                <span class="material-symbols-outlined text-sm">refresh</span>
                            </button>
                        </div>
                    </div>

                    <div id="section-search" class="space-y-3 hidden">
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="text-[11px] font-semibold text-slate-400">Role Filter</label>
                                <input type="text" id="filter-role" placeholder="e.g. Accountant, HR" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-teal-500 outline-none mt-1">
                            </div>
                            <div>
                                <label class="text-[11px] font-semibold text-slate-400">City / Location</label>
                                <input type="text" id="filter-city" placeholder="e.g. Ahmedabad" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-teal-500 outline-none mt-1">
                            </div>
                        </div>
                        <button onclick="searchGlobalCandidates()" class="w-full py-2.5 bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5">
                            <span class="material-symbols-outlined text-sm font-bold">search</span> Search Live Database
                        </button>
                    </div>

                    <div id="section-single" class="space-y-3 hidden">
                        <div>
                            <label class="text-[11px] font-semibold text-slate-400">10-Digit Mobile Number</label>
                            <input type="text" id="single-phone" oninput="updateSingleCandidate()" placeholder="e.g. 9099960782" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-teal-500 outline-none mt-1 font-mono">
                        </div>
                        <div>
                            <label class="text-[11px] font-semibold text-slate-400">Candidate Name (Optional)</label>
                            <input type="text" id="single-name" oninput="updateSingleCandidate()" placeholder="e.g. Ayaan" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-teal-500 outline-none mt-1">
                        </div>
                    </div>
                </div>

                <!-- Candidates Table -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-lg">
                    <div class="flex items-center justify-between">
                        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <span class="material-symbols-outlined text-teal-400 text-base">checklist</span>
                            2. Candidates (<span id="cand-count" class="text-teal-400">0</span> Selected)
                        </h2>
                        <div class="flex items-center gap-2 text-xs">
                            <button onclick="toggleSelectAll(true)" class="text-slate-400 hover:text-teal-400 transition">Select All</button>
                            <span class="text-slate-700">|</span>
                            <button onclick="toggleSelectAll(false)" class="text-slate-400 hover:text-red-400 transition">Deselect</button>
                        </div>
                    </div>

                    <div class="max-h-[340px] overflow-y-auto custom-scroll border border-slate-800/80 rounded-xl bg-slate-950">
                        <table class="w-full text-left text-xs">
                            <thead class="sticky top-0 bg-slate-900/90 backdrop-blur border-b border-slate-800 text-slate-400 font-semibold">
                                <tr>
                                    <th class="p-2.5 w-8 text-center"><input type="checkbox" id="check-master" onchange="toggleSelectAll(this.checked)"></th>
                                    <th class="p-2.5">Candidate Name</th>
                                    <th class="p-2.5">Mobile</th>
                                    <th class="p-2.5">Role</th>
                                    <th class="p-2.5">Status</th>
                                </tr>
                            </thead>
                            <tbody id="cand-tbody" class="divide-y divide-slate-800/50 text-slate-300">
                                <tr><td colspan="5" class="p-6 text-center text-slate-500">No candidates loaded yet. Select a job or search above.</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Right: AI Copywriting & Dispatch -->
            <div class="lg:col-span-5 space-y-6">
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-lg">
                    <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <span class="material-symbols-outlined text-purple-400 text-base">auto_awesome</span>
                        3. AI Message Copywriter
                    </h2>

                    <div class="space-y-2">
                        <label class="text-xs font-semibold text-slate-300">Describe what you want to send in Hindi/English:</label>
                        <textarea id="ai-prompt" rows="2" placeholder="e.g. Join WhatsApp group for job alerts https://whatsapp.com/channel/0029Va5h1CTAe5VzQcW60V2p..." class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:border-purple-500 outline-none resize-none"></textarea>
                        
                        <div class="flex flex-wrap gap-1.5 text-[11px]">
                            <button onclick="setPrompt('Send WhatsApp jobs channel link to join for latest updates: https://whatsapp.com/channel/0029Va5h1CTAe5VzQcW60V2p')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-teal-400 rounded-lg border border-slate-700/80 transition">💬 WhatsApp Invite</button>
                            <button onclick="setPrompt('Urgent interview call for {role} in {location}. Immediate joining.')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700/80 transition">⚡ Urgent Interview</button>
                            <button onclick="setPrompt('Update regarding your application. Confirm interview availability.')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700/80 transition">📋 Status Followup</button>
                        </div>

                        <button onclick="generateAiDraft()" id="btn-generate-ai" class="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-purple-600/20 transition flex items-center justify-center gap-1.5">
                            <span class="material-symbols-outlined text-sm">bolt</span> Generate with AI (Groq/Gemini)
                        </button>
                    </div>

                    <div class="space-y-2 pt-2 border-t border-slate-800">
                        <div class="flex items-center justify-between text-xs font-semibold">
                            <span class="text-slate-300">SMS Template:</span>
                            <span id="char-count" class="text-slate-400 font-mono text-[11px]">0 chars (1 Credit)</span>
                        </div>
                        <textarea id="sms-body" rows="3" oninput="updatePreview()" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-emerald-400 focus:border-teal-500 outline-none leading-relaxed"></textarea>
                        <div class="text-[10px] text-slate-500 flex gap-2">
                            <span>Tags:</span>
                            <button onclick="insertTag('{name}')" class="text-teal-400 hover:underline">{name}</button>
                            <button onclick="insertTag('{role}')" class="text-teal-400 hover:underline">{role}</button>
                            <button onclick="insertTag('{location}')" class="text-teal-400 hover:underline">{location}</button>
                        </div>
                    </div>

                    <div class="bg-slate-950/80 border border-slate-800 p-3 rounded-xl space-y-1">
                        <div class="text-[10px] uppercase font-bold tracking-wider text-slate-500">Live Sample Preview:</div>
                        <p id="sample-preview" class="text-xs text-slate-300 italic">"Sample preview will appear here..."</p>
                    </div>
                </div>

                <!-- Controls & Live Console -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-lg">
                    <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <span class="material-symbols-outlined text-emerald-400 text-base">send</span>
                        4. Dispatch Controls (Android SIM)
                    </h2>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <button onclick="startDispatch(5)" id="btn-test-run" class="py-3 px-4 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs rounded-xl shadow-lg shadow-amber-500/20 transition flex items-center justify-center gap-2 cursor-pointer">
                            <span class="material-symbols-outlined text-base">science</span>
                            TEST RUN (FIRST 5)
                        </button>
                        <button onclick="startDispatch(0)" id="btn-send-all" class="py-3 px-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition flex items-center justify-center gap-2 cursor-pointer">
                            <span class="material-symbols-outlined text-base">rocket_launch</span>
                            SEND ALL SELECTED
                        </button>
                    </div>

                    <!-- Live Progress & Console Box -->
                    <div id="progress-container" class="space-y-2.5 hidden">
                        <div class="flex items-center justify-between text-xs font-bold">
                            <span id="progress-label" class="text-slate-300">Dispatching via SIM...</span>
                            <span id="progress-stats" class="text-teal-400 font-mono">0 / 0</span>
                        </div>
                        <div class="w-full bg-slate-950 rounded-full h-2.5 border border-slate-800 overflow-hidden">
                            <div id="progress-bar" class="bg-gradient-to-r from-teal-500 to-emerald-400 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                        <div id="live-log" class="text-[11px] font-mono text-slate-400 truncate">Ready.</div>
                        <div class="space-y-1 pt-1">
                            <div class="flex items-center justify-between text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
                                <span>📜 Execution Logs (sms_dispatch.log)</span>
                            </div>
                            <div id="log-console" class="bg-slate-950 border border-slate-800/90 rounded-xl p-2.5 max-h-36 overflow-y-auto custom-scroll font-mono text-[11px] space-y-1">
                                <div class="text-slate-500 italic">Logs will appear here...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- MODALS -->
    <!-- MODAL 1: STEP-BY-STEP PREREQUISITES & GUIDE -->
    <div id="modal-guide" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto custom-scroll p-6 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <div class="flex items-center gap-2 text-teal-400 font-bold text-base">
                    <span class="material-symbols-outlined">menu_book</span>
                    <h3>How to Setup & Run SMS Automation (Step-by-Step)</h3>
                </div>
                <button onclick="closeModal('modal-guide')" class="text-slate-400 hover:text-white p-1 rounded-lg">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="space-y-4 text-xs text-slate-300 leading-relaxed">
                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
                    <div class="font-bold text-teal-400 flex items-center gap-1.5">
                        <span class="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 flex items-center justify-center text-[10px]">1</span>
                        Phone Developer Options Unlock Karein
                    </div>
                    <p class="text-slate-400">Settings ➔ About Phone ➔ <b>Build Number</b> (ya OS version) par 7 baar tap karein jab tak "You are a developer" na aaye.</p>
                </div>

                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
                    <div class="font-bold text-teal-400 flex items-center gap-1.5">
                        <span class="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 flex items-center justify-center text-[10px]">2</span>
                        USB Debugging Enable Karein
                    </div>
                    <p class="text-slate-400">Settings ➔ Developer Options me <b>USB Debugging</b> ko <b>ON</b> karein.<br>
                    <span class="text-amber-400 font-semibold">⚠️ Xiaomi / Realme / Oppo users:</span> "USB Debugging (Security settings)" ko bhi ON karein.</p>
                </div>

                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
                    <div class="font-bold text-teal-400 flex items-center gap-1.5">
                        <span class="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 flex items-center justify-center text-[10px]">3</span>
                        USB Cable Connect & Permission Allow Karein
                    </div>
                    <p class="text-slate-400">Phone ko USB cable se PC me lagayein. Screen par popup aane par <b>"Always allow from this computer"</b> tick karke <b>Allow</b> karein.</p>
                </div>

                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1.5">
                    <div class="font-bold text-teal-400 flex items-center gap-1.5">
                        <span class="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 flex items-center justify-center text-[10px]">4</span>
                        Single Test Run Karein
                    </div>
                    <p class="text-slate-400">"Single Test" tab me apna number dalein aur <b>TEST RUN</b> button dabayein taaki SIM se instant SMS test ho jaye.</p>
                </div>
            </div>

            <div class="pt-2 flex justify-end">
                <button onclick="closeModal('modal-guide')" class="px-5 py-2.5 bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold rounded-xl text-xs transition">Got It, Let's Start!</button>
            </div>
        </div>
    </div>

    <!-- MODAL 2: TRAI QUOTA & RESET HISTORY -->
    <div id="modal-quota" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto custom-scroll p-6 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <div class="flex items-center gap-2 text-emerald-400 font-bold text-base">
                    <span class="material-symbols-outlined">stacked_bar_chart</span>
                    <h3>TRAI Daily Quota & Midnight Reset History</h3>
                </div>
                <button onclick="closeModal('modal-quota')" class="text-slate-400 hover:text-white p-1 rounded-lg">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-3">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 text-center">
                        <div class="text-[11px] text-slate-400 uppercase font-semibold">Sent Today</div>
                        <div class="text-2xl font-black text-emerald-400 mt-1" id="modal-quota-sent">0</div>
                        <div class="text-[10px] text-slate-500 mt-1">Limit: 180 SMS/day</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 text-center">
                        <div class="text-[11px] text-slate-400 uppercase font-semibold">Remaining Quota</div>
                        <div class="text-2xl font-black text-teal-400 mt-1" id="modal-quota-remaining">180</div>
                        <div class="text-[10px] text-slate-500 mt-1">Midnight auto-reset</div>
                    </div>
                </div>

                <div class="text-xs text-slate-400 bg-slate-950/60 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
                    <span>Last Reset Timestamp:</span>
                    <span class="font-mono text-slate-200" id="modal-quota-last-reset">-</span>
                </div>

                <div class="space-y-2">
                    <div class="text-xs font-bold text-slate-300">Last 30 Days Reset Ledger:</div>
                    <div class="max-h-40 overflow-y-auto custom-scroll border border-slate-800 rounded-xl bg-slate-950">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-900 border-b border-slate-800 text-slate-400">
                                <tr>
                                    <th class="p-2">Date</th>
                                    <th class="p-2">Sent Count</th>
                                    <th class="p-2">Reset At</th>
                                    <th class="p-2">Status</th>
                                </tr>
                            </thead>
                            <tbody id="quota-history-tbody" class="divide-y divide-slate-800/50 text-slate-300">
                                <tr><td colspan="4" class="p-4 text-center text-slate-500">No previous reset logs found.</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="pt-2 flex justify-between items-center">
                    <button onclick="manualResetQuota()" class="px-4 py-2 bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 rounded-xl text-xs font-semibold transition flex items-center gap-1">
                        <span class="material-symbols-outlined text-sm">restart_alt</span>
                        Manual Reset to 0 (Switch SIM)
                    </button>
                    <button onclick="closeModal('modal-quota')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs transition">Close</button>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL 3: CONFIGURATION & SETTINGS -->
    <div id="modal-settings" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto custom-scroll p-6 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <div class="flex items-center gap-2 text-purple-400 font-bold text-base">
                    <span class="material-symbols-outlined">settings</span>
                    <h3>Studio Settings & API Configuration</h3>
                </div>
                <button onclick="closeModal('modal-settings')" class="text-slate-400 hover:text-white p-1 rounded-lg">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="space-y-3.5 text-xs">
                <div>
                    <label class="font-semibold text-slate-300">Worker API Endpoint (JobRecruitment Portal)</label>
                    <input type="text" id="cfg-worker-url" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                </div>
                <div>
                    <label class="font-semibold text-slate-300">Worker API Key</label>
                    <input type="password" id="cfg-worker-key" placeholder="Optional bearer key" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="font-semibold text-slate-300">Groq API Key (AI Copywriter)</label>
                        <input type="password" id="cfg-groq-key" placeholder="gsk_..." class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                    </div>
                    <div>
                        <label class="font-semibold text-slate-300">Nvidia NIM API Key</label>
                        <input type="password" id="cfg-nvidia-key" placeholder="nvapi-..." class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="font-semibold text-slate-300">Daily SMS Limit (TRAI Cap)</label>
                        <input type="number" id="cfg-daily-limit" value="180" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                    </div>
                    <div>
                        <label class="font-semibold text-slate-300">Dispatch Delay Pacing (Seconds)</label>
                        <input type="number" id="cfg-delay" value="5" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 font-mono mt-1">
                    </div>
                </div>
                <div>
                    <label class="font-semibold text-slate-300">SMS Mode</label>
                    <select id="cfg-sms-mode" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200 outline-none focus:border-purple-500 mt-1">
                        <option value="adb">Android ADB Mode (Native USB / Wi-Fi Debugging)</option>
                        <option value="http">Android HTTP Gateway APK (Local Wi-Fi)</option>
                    </select>
                </div>
            </div>

            <div class="pt-2 flex justify-end gap-2">
                <button onclick="closeModal('modal-settings')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs transition">Cancel</button>
                <button onclick="saveSettings()" class="px-5 py-2 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl text-xs transition">Save Settings</button>
            </div>
        </div>
    </div>

    <!-- MODAL 4: SYSTEM LOGS VIEWER -->
    <div id="modal-logs" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto custom-scroll p-6 space-y-4 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <div class="flex items-center gap-2 text-amber-400 font-bold text-base">
                    <span class="material-symbols-outlined">terminal</span>
                    <h3>Full Dispatch & System Audit Logs (sms_dispatch.log)</h3>
                </div>
                <button onclick="closeModal('modal-logs')" class="text-slate-400 hover:text-white p-1 rounded-lg">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="flex items-center justify-between gap-2">
                <input type="text" id="logs-search" oninput="filterLogs()" placeholder="Search logs (e.g. phone, SUCCESS, ERROR)..." class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 outline-none">
                <button onclick="loadFullLogs()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold flex items-center gap-1">
                    <span class="material-symbols-outlined text-sm">refresh</span> Refresh
                </button>
                <button onclick="clearLogsFile()" class="px-3 py-2 bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 rounded-xl text-xs font-semibold flex items-center gap-1">
                    <span class="material-symbols-outlined text-sm">delete</span> Clear
                </button>
            </div>

            <pre id="full-logs-content" class="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300 max-h-96 overflow-y-auto custom-scroll whitespace-pre-wrap leading-relaxed">Loading logs...</pre>

            <div class="pt-2 flex justify-end">
                <button onclick="closeModal('modal-logs')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs transition">Close</button>
            </div>
        </div>
    </div>

    <div id="toast" class="fixed bottom-5 right-5 bg-slate-900 border border-slate-700 text-white px-4 py-3 rounded-xl shadow-2xl text-xs font-semibold transition-all duration-300 transform translate-y-10 opacity-0 pointer-events-none z-50"></div>

    <script>
        let currentCandidates = [];
        let activeJobContext = { role: 'Candidate', location: 'Ahmedabad', company: 'Job Recruitment' };
        let rawLogText = "";

        document.addEventListener('DOMContentLoaded', () => {
            loadAdminJobs();
            loadQuota();
            updatePreview();
            startHeartbeat();
        });

        function startHeartbeat() {
            // Heartbeat to keep connection active and handle automatic hot reload seamlessly
            setInterval(async () => {
                try {
                    await fetch('/api/quota', { cache: 'no-store' });
                } catch(e) {}
            }, 5000);
        }

        function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
        function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

        function showToast(msg, isError = false) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = `fixed bottom-5 right-5 px-4 py-3 rounded-xl shadow-2xl text-xs font-semibold transition-all duration-300 z-50 border ${isError ? 'bg-red-950 border-red-800 text-red-200' : 'bg-slate-900 border-slate-700 text-emerald-400'}`;
            t.style.opacity = '1';
            t.style.transform = 'translateY(0)';
            setTimeout(() => {
                t.style.opacity = '0';
                t.style.transform = 'translateY(10px)';
            }, 3500);
        }

        async function loadQuota() {
            try {
                const res = await fetch('/api/quota');
                const data = await res.json();
                document.getElementById('quota-sent').textContent = data.sent_today;
                document.getElementById('quota-limit').textContent = data.limit;
                document.getElementById('nav-quota-badge').textContent = `${data.sent_today} / ${data.limit} Sent`;
            } catch (e) {}
        }

        async function openQuotaModal() {
            openModal('modal-quota');
            try {
                const res = await fetch('/api/quota_history');
                const data = await res.json();
                document.getElementById('modal-quota-sent').textContent = data.sent_today;
                document.getElementById('modal-quota-remaining').textContent = Math.max(0, data.limit - data.sent_today);
                document.getElementById('modal-quota-last-reset').textContent = data.last_reset || 'N/A';

                const tbody = document.getElementById('quota-history-tbody');
                tbody.innerHTML = '';
                if (!data.history || data.history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No reset entries recorded yet.</td></tr>';
                } else {
                    data.history.slice().reverse().forEach(h => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td class="p-2 font-mono">${escapeHtml(h.to_date || h.from_date || '-')}</td>
                            <td class="p-2 font-bold text-emerald-400">${h.final_count || 0}</td>
                            <td class="p-2 font-mono text-[11px] text-slate-400">${escapeHtml(h.reset_at || '-')}</td>
                            <td class="p-2"><span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-teal-300 border border-slate-700">${escapeHtml(h.status || 'OK')}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            } catch (e) { showToast("Failed to load quota ledger.", true); }
        }

        async function manualResetQuota() {
            if (!confirm("Are you sure you want to reset today's quota to 0/180? (Useful if you switched physical SIM).")) return;
            try {
                const res = await fetch('/api/reset_quota', { method: 'POST' });
                const data = await res.json();
                showToast(data.message || "Quota reset!");
                loadQuota();
                openQuotaModal();
            } catch (e) { showToast("Reset failed.", true); }
        }

        async function openSettingsModal() {
            openModal('modal-settings');
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                document.getElementById('cfg-worker-url').value = data.WORKER_API_URL || '';
                document.getElementById('cfg-worker-key').value = data.WORKER_API_KEY || '';
                document.getElementById('cfg-groq-key').value = data.GROQ_API_KEY || '';
                document.getElementById('cfg-nvidia-key').value = data.NVIDIA_API_KEY || '';
                document.getElementById('cfg-daily-limit').value = data.DAILY_SMS_LIMIT || 180;
                document.getElementById('cfg-delay').value = data.DISPATCH_DELAY_SECONDS || 5;
                document.getElementById('cfg-sms-mode').value = data.SMS_MODE || 'adb';
            } catch (e) { showToast("Could not load config.", true); }
        }

        async function saveSettings() {
            const payload = {
                WORKER_API_URL: document.getElementById('cfg-worker-url').value.trim(),
                WORKER_API_KEY: document.getElementById('cfg-worker-key').value.trim(),
                GROQ_API_KEY: document.getElementById('cfg-groq-key').value.trim(),
                NVIDIA_API_KEY: document.getElementById('cfg-nvidia-key').value.trim(),
                DAILY_SMS_LIMIT: document.getElementById('cfg-daily-limit').value.trim(),
                DISPATCH_DELAY_SECONDS: document.getElementById('cfg-delay').value.trim(),
                SMS_MODE: document.getElementById('cfg-sms-mode').value
            };
            try {
                const res = await fetch('/api/save_settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                showToast(data.message || "Settings saved successfully!");
                closeModal('modal-settings');
                loadQuota();
            } catch (e) { showToast("Error saving settings.", true); }
        }

        async function openLogsModal() {
            openModal('modal-logs');
            loadFullLogs();
        }

        async function loadFullLogs() {
            const el = document.getElementById('full-logs-content');
            el.textContent = "Loading logs...";
            try {
                const res = await fetch('/api/logs');
                rawLogText = await res.text();
                el.textContent = rawLogText || "(No logs recorded yet)";
                el.scrollTop = el.scrollHeight;
            } catch (e) { el.textContent = "Failed to load log file."; }
        }

        function filterLogs() {
            const q = document.getElementById('logs-search').value.toLowerCase();
            const el = document.getElementById('full-logs-content');
            if (!q) {
                el.textContent = rawLogText;
                return;
            }
            const nlRegex = new RegExp('[\\r\\n]+');
            const lines = rawLogText.split(nlRegex).filter(l => l.toLowerCase().includes(q));
            el.textContent = lines.join(String.fromCharCode(10)) || "(No matching log entries found)";
        }

        async function clearLogsFile() {
            if (!confirm("Are you sure you want to clear sms_dispatch.log?")) return;
            try {
                await fetch('/api/clear_logs', { method: 'POST' });
                showToast("Logs cleared!");
                loadFullLogs();
            } catch (e) { showToast("Error clearing logs.", true); }
        }

        async function checkHardware() {
            showToast("Testing Android Phone connection...");
            try {
                const res = await fetch('/api/check_hardware');
                const data = await res.json();
                showToast(data.message, !data.ok);
            } catch (e) { showToast("Error connecting to hardware server.", true); }
        }

        function updateSingleCandidate() {
            const phone = document.getElementById('single-phone').value.trim() || '9898012345';
            const name = document.getElementById('single-name').value.trim() || 'Candidate';
            currentCandidates = [{ name: name, phone: phone, role: 'Candidate', status: 'Test' }];
            renderCandidates(currentCandidates);
            updatePreview();
        }

        function switchSource(type) {
            ['jobs', 'search', 'single'].forEach(t => {
                document.getElementById(`tab-${t}`).className = t === type ? 'py-2 text-xs font-bold rounded-lg transition text-slate-200 bg-slate-800 shadow' : 'py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-slate-200';
                document.getElementById(`section-${t}`).classList.toggle('hidden', t !== type);
            });
            if (type === 'single') {
                updateSingleCandidate();
            }
        }

        async function loadAdminJobs() {
            const sel = document.getElementById('job-select');
            sel.innerHTML = '<option value="">Loading live jobs...</option>';
            try {
                const res = await fetch('/api/jobs');
                const data = await res.json();
                sel.innerHTML = '<option value="">-- Select a Job Posting --</option>';
                (data.jobs || []).forEach(j => {
                    const opt = document.createElement('option');
                    opt.value = j.id;
                    opt.textContent = `${j.jobRole} @ ${j.companyName} (${j.location}) — ${j.total_applicants} applicants [${j.status}]`;
                    opt.dataset.role = j.jobRole;
                    opt.dataset.location = j.location;
                    opt.dataset.company = j.companyName;
                    sel.appendChild(opt);
                });
            } catch (e) {
                sel.innerHTML = '<option value="">Error loading jobs</option>';
                showToast("Failed to fetch jobs.", true);
            }
        }

        async function loadJobApplicants() {
            const sel = document.getElementById('job-select');
            const jobId = sel.value;
            if (!jobId) return;

            const selectedOpt = sel.options[sel.selectedIndex];
            activeJobContext = {
                role: selectedOpt.dataset.role || 'Candidate',
                location: selectedOpt.dataset.location || 'Ahmedabad',
                company: selectedOpt.dataset.company || 'Job Recruitment'
            };

            showToast("Fetching candidates for " + activeJobContext.role + "...");
            try {
                const res = await fetch(`/api/job_applicants?job_id=${encodeURIComponent(jobId)}`);
                const data = await res.json();
                currentCandidates = data.cands || [];
                renderCandidates(currentCandidates);
                updatePreview();
            } catch (e) { showToast("Error loading applicants.", true); }
        }

        async function searchGlobalCandidates() {
            const role = document.getElementById('filter-role').value.trim();
            const city = document.getElementById('filter-city').value.trim();
            activeJobContext = { role: role || 'Candidate', location: city || 'Ahmedabad', company: 'Job Recruitment' };

            showToast("Searching database...");
            try {
                const res = await fetch(`/api/search_candidates?role=${encodeURIComponent(role)}&city=${encodeURIComponent(city)}`);
                const data = await res.json();
                currentCandidates = data.cands || [];
                renderCandidates(currentCandidates);
                updatePreview();
            } catch (e) { showToast("Search failed.", true); }
        }

        function renderCandidates(cands) {
            const tbody = document.getElementById('cand-tbody');
            tbody.innerHTML = '';
            if (!cands || cands.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500">No candidates with valid mobile numbers found.</td></tr>';
                document.getElementById('cand-count').textContent = '0';
                return;
            }

            cands.forEach((c, idx) => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-900/60 transition';
                tr.innerHTML = `
                    <td class="p-2.5 text-center"><input type="checkbox" class="cand-checkbox" data-idx="${idx}" checked onchange="updateSelectedCount()"></td>
                    <td class="p-2.5 font-semibold text-slate-200">${escapeHtml(c.name || 'Candidate')}</td>
                    <td class="p-2.5 font-mono text-teal-400">+91-${escapeHtml(c.phone || '')}</td>
                    <td class="p-2.5 text-slate-400">${escapeHtml(c.role || '-')}</td>
                    <td class="p-2.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">${escapeHtml(c.status || 'Active')}</span></td>
                `;
                tbody.appendChild(tr);
            });
            updateSelectedCount();
        }

        function updateSelectedCount() {
            const checked = document.querySelectorAll('.cand-checkbox:checked').length;
            document.getElementById('cand-count').textContent = checked;
        }

        function toggleSelectAll(checked) {
            document.querySelectorAll('.cand-checkbox').forEach(cb => cb.checked = checked);
            document.getElementById('check-master').checked = checked;
            updateSelectedCount();
        }

        function setPrompt(text) {
            document.getElementById('ai-prompt').value = text;
            generateAiDraft();
        }

        async function generateAiDraft() {
            const prompt = document.getElementById('ai-prompt').value.trim() || `Urgent opening for ${activeJobContext.role} in ${activeJobContext.location}. Salary competitive.`;
            const btn = document.getElementById('btn-generate-ai');
            btn.disabled = true;
            btn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">refresh</span> Generating...';

            try {
                const res = await fetch('/api/ai_draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt, role: activeJobContext.role, location: activeJobContext.location, company: activeJobContext.company })
                });
                const data = await res.json();
                if (data.template) {
                    document.getElementById('sms-body').value = data.template;
                    updatePreview();
                    showToast("AI Template Generated!");
                }
            } catch (e) { showToast("AI generation failed.", true); }
            finally {
                btn.disabled = false;
                btn.innerHTML = '<span class="material-symbols-outlined text-sm">bolt</span> Generate with AI (Groq/Gemini)';
            }
        }

        function updatePreview() {
            const body = document.getElementById('sms-body').value || `Dear {name}, Job Recruitment has an opening for {role} in {location}. Apply here: https://jobrecruitment.in/jobs`;
            if (!document.getElementById('sms-body').value) document.getElementById('sms-body').value = body;
            
            document.getElementById('char-count').textContent = `${body.length} chars (1 Credit)`;

            const sampleCand = currentCandidates[0] || { name: 'Rahul Verma', phone: '9898011223' };
            const preview = body
                .replace('{name}', sampleCand.name || 'Candidate')
                .replace('{role}', activeJobContext.role || 'Senior Accountant')
                .replace('{location}', activeJobContext.location || 'Ahmedabad')
                .replace('{company}', activeJobContext.company || 'Job Recruitment');

            document.getElementById('sample-preview').textContent = `"${preview}"`;
        }

        function insertTag(tag) {
            const textarea = document.getElementById('sms-body');
            textarea.value += tag;
            updatePreview();
        }

        async function startDispatch(limitCount = 0) {
            const selectedIndices = Array.from(document.querySelectorAll('.cand-checkbox:checked')).map(cb => parseInt(cb.dataset.idx));
            if (selectedIndices.length === 0) {
                showToast("Please select at least 1 candidate!", true);
                return;
            }

            let toSend = selectedIndices.map(idx => currentCandidates[idx]);
            if (limitCount > 0) {
                toSend = toSend.slice(0, limitCount);
            }

            const template = document.getElementById('sms-body').value.trim();
            if (!template) {
                showToast("SMS message body cannot be empty!", true);
                return;
            }

            const isTest = limitCount > 0;
            const isSingle = toSend.length === 1;
            const confirmMsg = isSingle
                ? `Send test SMS to +91-${toSend[0].phone} (${toSend[0].name}) via Android SIM?`
                : (isTest 
                    ? `Run TEST DISPATCH to first ${toSend.length} candidates via Android SIM?`
                    : `DISPATCH TO ALL ${toSend.length} CANDIDATES via Android SIM?`);

            if (!confirm(confirmMsg)) return;

            document.getElementById('progress-container').classList.remove('hidden');
            document.getElementById('btn-test-run').disabled = true;
            document.getElementById('btn-send-all').disabled = true;

            const res = await fetch('/api/start_dispatch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    candidates: toSend,
                    template: template,
                    role: activeJobContext.role,
                    location: activeJobContext.location,
                    company: activeJobContext.company
                })
            });

            pollDispatchProgress();
        }

        async function pollDispatchProgress() {
            const interval = setInterval(async () => {
                try {
                    const res = await fetch('/api/dispatch_status');
                    const data = await res.json();
                    
                    const pct = data.total > 0 ? Math.round((data.current_index / data.total) * 100) : 0;
                    document.getElementById('progress-bar').style.width = pct + '%';
                    document.getElementById('progress-stats').textContent = `${data.current_index} / ${data.total}`;
                    document.getElementById('live-log').textContent = data.last_log || 'Processing...';

                    if (data.logs && data.logs.length) {
                        const consoleEl = document.getElementById('log-console');
                        consoleEl.innerHTML = data.logs.map(l => {
                            const isFail = l.includes('Failed') || l.includes('ERROR');
                            return `<div class="${isFail ? 'text-red-400 font-semibold' : 'text-emerald-400'}">${escapeHtml(l)}</div>`;
                        }).join('');
                        consoleEl.scrollTop = consoleEl.scrollHeight;
                    }

                    if (!data.is_running) {
                        clearInterval(interval);
                        document.getElementById('btn-test-run').disabled = false;
                        document.getElementById('btn-send-all').disabled = false;
                        loadQuota();
                        showToast(`Dispatch Complete! ${data.sent_count} sent, ${data.failed_count} failed.`);
                    }
                } catch (e) { console.error('Poll error:', e); }
            }, 1200);
        }

        function escapeHtml(s) {
            return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# 9. CONTROLLER LAYER: EMBEDDED HTTP REST API & DISPATCH ROUTER
# ==============================================================================
class StudioHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            idx_file = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(idx_file):
                with open(idx_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        elif path == "/api/quota":
            quota_service.check_quota(0)
            self._send_json({
                "sent_today": quota_service.state.get("sent_today", 0),
                "limit": quota_service.limit,
                "last_reset": quota_service.state.get("last_reset_at")
            })
            return

        elif path == "/api/quota_history":
            quota_service.check_quota(0)
            self._send_json({
                "sent_today": quota_service.state.get("sent_today", 0),
                "limit": quota_service.limit,
                "last_reset": quota_service.state.get("last_reset_at"),
                "history": quota_service.state.get("reset_history", [])
            })
            return

        elif path == "/api/settings":
            self._send_json({
                "WORKER_API_URL": WORKER_URL,
                "WORKER_API_KEY": WORKER_KEY,
                "GROQ_API_KEY": GROQ_KEY,
                "NVIDIA_API_KEY": NVIDIA_KEY,
                "DAILY_SMS_LIMIT": DAILY_LIMIT,
                "DISPATCH_DELAY_SECONDS": DISPATCH_DELAY,
                "SMS_MODE": SMS_MODE
            })
            return

        elif path in ["/api/health_check", "/healthz"]:
            diag = gateway_service.get_full_diagnostics()
            self._send_json(diag)
            return

        elif path == "/api/adb_wifi_qr_params":
            # Active mDNS Zeroconf Advertiser for Native QR Scanning
            import socket, random, string
            try:
                from zeroconf import Zeroconf, ServiceInfo
                global _active_zeroconf, _active_service_info
                
                # Get local Wi-Fi IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.connect(('8.8.8.8', 80))
                    local_ip = s.getsockname()[0]
                except Exception:
                    local_ip = '127.0.0.1'
                finally:
                    s.close()

                service_id = "JR-Studio-" + "".join(random.choices(string.digits, k=4))
                password = "".join(random.choices(string.ascii_letters + string.digits, k=8))
                port = 5555

                desc = {'name': service_id}
                info = ServiceInfo(
                    "_adb-tls-pairing._tcp.local.",
                    f"{service_id}._adb-tls-pairing._tcp.local.",
                    addresses=[socket.inet_aton(local_ip)],
                    port=port,
                    properties=desc,
                    server=f"{service_id}.local."
                )

                if '_active_zeroconf' in globals() and _active_zeroconf:
                    try:
                        _active_zeroconf.unregister_all_services()
                        _active_zeroconf.close()
                    except Exception:
                        pass

                _active_zeroconf = Zeroconf()
                _active_zeroconf.register_service(info)

                qr_payload = f"WIFI:T:ADB;S:{service_id};P:{password};;"
                self._send_json({
                    "ok": True,
                    "service_name": service_id,
                    "password": password,
                    "local_ip": local_ip,
                    "qr_payload": qr_payload
                })
            except Exception as e:
                # Fallback payload
                service_id = "JR-Studio-ADB"
                pwd = "".join(random.choices(string.ascii_letters + string.digits, k=8))
                self._send_json({
                    "ok": True,
                    "service_name": service_id,
                    "password": pwd,
                    "local_ip": "127.0.0.1",
                    "qr_payload": f"WIFI:T:ADB;S:{service_id};P:{pwd};;"
                })
            return

        elif path == "/api/jobs":
            jobs = candidate_service.fetch_admin_jobs(status="")
            self._send_json({"jobs": jobs})
            return

        elif path == "/api/filter_options":
            jobs = candidate_service.fetch_admin_jobs(status="")
            roles = sorted(list(set([j.get('jobRole') for j in jobs if j.get('jobRole')])))
            cities = sorted(list(set([j.get('location') for j in jobs if j.get('location')])))
            self._send_json({"roles": roles, "cities": cities})
            return

        elif path == "/api/job_applicants":
            job_id = query.get("job_id", [""])[0]
            cands, job = candidate_service.fetch_job_applicants(job_id)
            self._send_json({"cands": cands, "job": job})
            return

        elif path == "/api/search_candidates":
            role = query.get("role", [""])[0]
            city = query.get("city", [""])[0]
            cands, total = candidate_service.fetch_global_candidates(role=role, city=city, limit=100)
            self._send_json({"cands": cands, "total": total})
            return

        elif path == "/api/dispatch_status":
            with dispatch_lock:
                last_log = current_dispatch["logs"][-1] if current_dispatch["logs"] else "Idle"
                self._send_json({
                    "is_running": current_dispatch["is_running"],
                    "total": current_dispatch["total"],
                    "current_index": current_dispatch["current_index"],
                    "sent_count": current_dispatch["sent_count"],
                    "failed_count": current_dispatch["failed_count"],
                    "last_log": last_log,
                    "logs": current_dispatch["logs"]
                })
            return

        elif path == "/api/supabase_logs":
            logs = supabase_service.fetch_recent_logs(limit=50)
            self._send_json({"logs": logs, "connected": supabase_service.enabled})
            return

        elif path == "/api/server_version":
            self._send_json({
                "server_start_time": SERVER_START_TIME,
                "max_mtime": get_watched_max_mtime()
            })
            return

        elif path == "/api/campaign_history":
            campaigns = supabase_service.fetch_campaign_history(limit=30)
            self._send_json({"campaigns": campaigns, "connected": supabase_service.enabled})
            return

        elif path == "/api/templates":
            user_id = query.get("user_id", [""])[0] or None
            templates = supabase_service.fetch_templates(user_id=user_id)
            self._send_json({"templates": templates})
            return

        elif path == "/api/ai_models":
            models = ai_service.get_available_models()
            self._send_json({"models": models})
            return

        elif path == "/api/logs":
            logs_content = ""
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as lf:
                        logs_content = lf.read()
                except Exception as e:
                    logs_content = str(e)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(logs_content.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_HEAD(self):
        # Render / uptime monitoring HEAD requests
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length).decode('utf-8')
        data = json.loads(body) if body else {}

        if path == "/api/auth/signup":
            email = data.get("email", "")
            password = data.get("password", "")
            name = data.get("full_name", "")
            role = data.get("role", "recruiter")
            if not email or not password or not name:
                self._send_json({"ok": False, "message": "Email, password, and name are required."}, code=400)
                return
            ok, res = supabase_service.signup_user(email, password, name, role)
            self._send_json({"ok": ok, "user" if ok else "message": res})
            return

        elif path == "/api/auth/login":
            email = data.get("email", "")
            password = data.get("password", "")
            if not email or not password:
                self._send_json({"ok": False, "message": "Email and password are required."}, code=400)
                return
            ok, res = supabase_service.login_user(email, password)
            self._send_json({"ok": ok, "user" if ok else "message": res})
            return

        elif path == "/api/templates/save":
            title = data.get("title", "")
            category = data.get("category", "recruitment")
            body_txt = data.get("template_body", "")
            visibility = data.get("visibility", "public")
            user_id = data.get("user_id") or None
            if not title or not body_txt:
                self._send_json({"ok": False, "message": "Title and template body are required."}, code=400)
                return
            ok, res = supabase_service.save_template(title, category, body_txt, visibility, user_id)
            self._send_json({"ok": ok, "id" if ok else "message": res})
            return

        elif path == "/api/unlock_screen":
            try:
                import subprocess
                adb_cmd = ensure_adb_binary()
                # Wake screen
                subprocess.run([adb_cmd, "shell", "input", "keyevent", "224"], timeout=3)
                # Dismiss keyguard
                subprocess.run([adb_cmd, "shell", "wm", "dismiss-keyguard"], timeout=3)
                self._send_json({"ok": True, "message": "Wake and unlock signals sent to phone!"})
            except Exception as e:
                self._send_json({"ok": False, "message": f"Unlock Error: {e}"})
            return

        elif path == "/api/adb_reconnect":
            try:
                import subprocess
                adb_cmd = ensure_adb_binary()
                res_dev = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=3)
                lines = [l for l in res_dev.stdout.strip().split('\n')[1:] if l.strip()]
                all_devs = [l.split()[0] for l in lines]
                reconnected = []
                for d in all_devs:
                    if ":" in d: # Wi-Fi IP:Port
                        subprocess.run([adb_cmd, "disconnect", d], capture_output=True, timeout=2)
                        subprocess.run([adb_cmd, "connect", d], capture_output=True, timeout=3)
                        reconnected.append(d)
                self._send_json({"ok": True, "message": f"Sockets refreshed: {', '.join(reconnected) if reconnected else 'Ready'}"})
            except Exception as e:
                self._send_json({"ok": False, "message": f"Reconnect Error: {e}"})
            return

        elif path == "/api/adb_wifi_pair":
            ip_port = data.get("ip_port", "").strip()
            code = data.get("code", "").strip()
            connect_ip_port = data.get("connect_ip_port", "").strip()
            if not ip_port or not code:
                self._send_json({"ok": False, "message": "IP:Port and Pairing Code are required."}, code=400)
                return
            try:
                import subprocess
                cmd = [ADB_BIN, "pair", ip_port, code]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                out = (res.stdout + "\n" + res.stderr).strip()
                if "Successfully paired" in out or "paired to" in out.lower():
                    # Automatic step 2: If connect_ip_port provided or using base IP
                    connect_target = connect_ip_port or ip_port
                    res_c = subprocess.run([ADB_BIN, "connect", connect_target], capture_output=True, text=True, timeout=6)
                    out_c = (res_c.stdout + "\n" + res_c.stderr).strip()
                    self._send_json({"ok": True, "message": f"Paired & Connected! ({out_c})", "details": out})
                else:
                    self._send_json({"ok": False, "message": out or "Pairing timed out."})
            except Exception as e:
                self._send_json({"ok": False, "message": f"Pairing Error: {e}"})
            return

        elif path == "/api/adb_wifi_connect":
            ip_port = data.get("ip_port", "").strip()
            if not ip_port:
                self._send_json({"ok": False, "message": "Connect IP:Port is required."}, code=400)
                return
            try:
                import subprocess
                cmd = [ADB_BIN, "connect", ip_port]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                out = (res.stdout + "\n" + res.stderr).strip()
                if "connected to" in out.lower() or "already connected" in out.lower():
                    self._send_json({"ok": True, "message": f"Connected: {out}"})
                else:
                    self._send_json({"ok": False, "message": out or "Connection failed."})
            except Exception as e:
                self._send_json({"ok": False, "message": f"Connect Error: {e}"})
            return

        if path == "/api/reset_quota":
            ok, msg = quota_service.manual_reset()
            self._send_json({"ok": ok, "message": msg})
            return

        elif path == "/api/clear_logs":
            try:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
                self._send_json({"ok": True, "message": "Logs cleared."})
            except Exception as e:
                self._send_json({"ok": False, "message": str(e)})
            return

        elif path == "/api/save_settings":
            # WORKER_API_KEY is locked to production .env and cannot be overwritten by client UI
            current_worker_url = os.getenv("WORKER_API_URL", "https://jobrecruitment.in/api/sms_worker.php")
            current_worker_key = os.getenv("WORKER_API_KEY", "")
            lines = [
                f"WORKER_API_URL={current_worker_url}\n",
                f"WORKER_API_KEY={current_worker_key}\n",
                f"GROQ_API_KEY={data.get('GROQ_API_KEY', '')}\n",
                f"GEMINI_API_KEY={data.get('GEMINI_API_KEY', GEMINI_KEY)}\n",
                f"NVIDIA_API_KEY={data.get('NVIDIA_API_KEY', '')}\n",
                f"OPENAI_API_KEY={data.get('OPENAI_API_KEY', '')}\n",
                f"SMS_MODE={data.get('SMS_MODE', 'adb')}\n",
                f"ANDROID_GATEWAY_URL={GATEWAY_URL}\n",
                f"DAILY_SMS_LIMIT={data.get('DAILY_SMS_LIMIT', '180')}\n",
                f"DISPATCH_DELAY_SECONDS={data.get('DISPATCH_DELAY_SECONDS', '5')}\n"
            ]
            try:
                with open(ENV_FILE, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                reload_app_config()
                self._send_json({"ok": True, "message": "AI configuration updated successfully!"})
            except Exception as e:
                self._send_json({"ok": False, "message": f"Save failed: {e}"}, code=500)
            return

        elif path == "/api/ai_draft":
            prompt = data.get("prompt", "")
            role = data.get("role", "")
            location = data.get("location", "")
            company = data.get("company", "Job Recruitment")
            model_id = data.get("model_id", "")
            template = ai_service.generate_sms_template(prompt, role, location, company, model_id=model_id)
            self._send_json({"template": template})
            return

        elif path == "/api/start_dispatch":
            candidates = data.get("candidates", [])
            template = data.get("template", "")
            role = data.get("role", "")
            location = data.get("location", "")
            company = data.get("company", "Job Recruitment")

            campaign_title = f"{role or 'Recruitment'} ({location or 'India'}) - {len(candidates)} SMS"
            campaign_id = supabase_service.create_campaign(
                title=campaign_title,
                template_body=template,
                total_cands=len(candidates),
                role=role,
                location=location
            )

            def run_dispatch():
                with dispatch_lock:
                    current_dispatch["is_running"] = True
                    current_dispatch["total"] = len(candidates)
                    current_dispatch["current_index"] = 0
                    current_dispatch["sent_count"] = 0
                    current_dispatch["failed_count"] = 0
                    current_dispatch["logs"] = []

                write_log(f"Starting SMS campaign '{campaign_title}' for {len(candidates)} candidate(s)...")

                greetings_pool = ["Hi", "Hello", "Dear", "Greetings"]

                for i, c in enumerate(candidates, 1):
                    c_name = c.get("name") or "Candidate"
                    c_phone = c.get("phone")
                    
                    # 1. Dynamic Spintax Salutation Rotation
                    chosen_salutation = greetings_pool[(i - 1) % len(greetings_pool)]
                    cand_msg = template.replace("{name}", c_name).replace("{role}", role).replace("{location}", location).replace("{company}", company)
                    
                    # Ensure dynamic greeting replacement if message starts with standard salutations
                    for g in ["Hi", "Hello", "Dear", "Greetings"]:
                        if cand_msg.startswith(f"{g} "):
                            cand_msg = f"{chosen_salutation} " + cand_msg[len(g) + 1:]
                            break
                    
                    # 2. Authentic Company Sign-Off (If not already present)
                    if "JobRecruitment" not in cand_msg and "HR" not in cand_msg:
                        cand_msg = f"{cand_msg} - HR Team, JobRecruitment.in"

                    final_msg = cand_msg

                    ok, resp = gateway_service.send_sms(c_phone, final_msg)
                    status_str = "SENT" if ok else "FAILED"
                    err_reason = None if ok else resp

                    # Record in Supabase Cloud Ledger
                    try:
                        supabase_service.log_dispatch(
                            cand_name=c_name,
                            phone=c_phone,
                            role=role or c.get("role", "Candidate"),
                            msg=final_msg,
                            status=status_str,
                            carrier="Jio True5G",
                            gateway_mode=SMS_MODE,
                            error_reason=err_reason,
                            campaign_id=campaign_id
                        )
                    except Exception:
                        pass
                    
                    with dispatch_lock:
                        current_dispatch["current_index"] = i
                        if ok:
                            current_dispatch["sent_count"] += 1
                            quota_service.record_sent(1)
                            log_line = f"[{i}/{len(candidates)}] Sent to {c_name} (+91-{c_phone})"
                            current_dispatch["logs"].append(log_line)
                            write_log(f"SUCCESS: {log_line}")
                        else:
                            current_dispatch["failed_count"] += 1
                            log_line = f"[{i}/{len(candidates)}] Failed for {c_name} (+91-{c_phone}): {resp}"
                            current_dispatch["logs"].append(log_line)
                            write_log(f"ERROR: {log_line}")

                    if i < len(candidates):
                        import random
                        # 3. Human Pacing Randomizer (Jio Firewall Anti-Throttling)
                        human_jitter = random.uniform(DISPATCH_DELAY, DISPATCH_DELAY + 4.0)
                        time.sleep(human_jitter)

                with dispatch_lock:
                    current_dispatch["is_running"] = False
                    supabase_service.update_campaign_stats(campaign_id, current_dispatch["sent_count"], current_dispatch["failed_count"])
                write_log(f"Campaign Finished: {current_dispatch['sent_count']} sent, {current_dispatch['failed_count']} failed.")

            t = threading.Thread(target=run_dispatch, daemon=True)
            t.start()
            self._send_json({"status": "started"})
            return

        self.send_response(404)
        self.end_headers()

def start_keep_alive_pinger(server_port):
    app_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")
    def _ping_loop():
        import time
        import urllib.request
        target_url = app_url.rstrip("/") if app_url else f"http://127.0.0.1:{server_port}"
        ping_endpoint = f"{target_url}/api/health_check"
        write_log(f"[*] 24/7 Keep-Alive Auto-Pinger active for: {ping_endpoint}")
        while True:
            time.sleep(480) # Every 8 minutes (before Render 15 min sleep)
            try:
                with urllib.request.urlopen(ping_endpoint, timeout=10) as resp:
                    if resp.status == 200:
                        write_log("[*] Keep-Alive Ping successful (Prevented Sleep)")
            except Exception as e:
                write_log(f"[!] Keep-Alive Ping check: {e}")
    threading.Thread(target=_ping_loop, daemon=True).start()

def start_server_worker(port=8050):
    try:
        from schema_migrator import SchemaMigrator
        SchemaMigrator.run_auto_migrations()
    except Exception as e:
        print(f" [!] Migration warning: {e}")

    env_port = int(os.getenv("PORT", port))
    server = HTTPServer(("0.0.0.0", env_port), StudioHTTPHandler)
    url = f"http://localhost:{env_port}"
    print("=" * 72)
    print(f" [*] JobRecruitment All-in-One AI SMS Studio is LIVE at: {url}")
    print(f" [*] Hardware Radio: {SMS_MODE.upper()} Mode (ADB: {ADB_BIN})")
    print(f" [*] Daily Safety Limit: {DAILY_LIMIT} SMS/day (Midnight Reset Active)")
    print("=" * 72)

    start_keep_alive_pinger(env_port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down SMS Studio worker...")
        server.server_close()

def get_watched_max_mtime():
    max_m = 0
    for root, dirs, files in os.walk(BASE_DIR):
        if "platform-tools" in root or "__pycache__" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith((".py", ".env", ".html", ".js", ".json")) and not f.startswith("sms_dispatch.log") and not f.startswith("quota_state.json"):
                fp = os.path.join(root, f)
                try:
                    m = os.path.getmtime(fp)
                    if m > max_m:
                        max_m = m
                except Exception:
                    pass
    return max_m

def run_hot_reloader(port=8050):
    url = f"http://localhost:{port}"
    print("=" * 72)
    print(" 🚀 [HOT-RELOAD ACTIVE] Watching files for changes (auto-reload on edit)...")
    print(f" 🌐 Studio URL: {url}")
    print("=" * 72)

    # Open browser on first launch
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    last_mtime = get_watched_max_mtime()

    while True:
        child_env = os.environ.copy()
        child_env["SMS_STUDIO_WORKER"] = "1"
        cmd = [sys.executable, os.path.abspath(__file__)]
        child = subprocess.Popen(cmd, env=child_env)

        reloaded = False
        try:
            while child.poll() is None:
                time.sleep(1.0)
                current_mtime = get_watched_max_mtime()
                if current_mtime > last_mtime:
                    last_mtime = current_mtime
                    print("\n[!] 🔄 Code change detected! Reloading SMS Studio automatically...")
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except Exception:
                        child.kill()
                    reloaded = True
                    break
        except KeyboardInterrupt:
            print("\n[!] Stopping Hot Reloader...")
            child.terminate()
            break

        if not reloaded and child.returncode != 0:
            time.sleep(1.5)

if __name__ == "__main__":
    if os.getenv("SMS_STUDIO_WORKER") == "1":
        start_server_worker()
    else:
        run_hot_reloader()
