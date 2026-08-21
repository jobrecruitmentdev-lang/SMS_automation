import os
import sys
import shutil
import urllib.request
import zipfile
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(BASE_DIR, ".env")
PLATFORM_TOOLS_DIR = os.path.join(BASE_DIR, "platform-tools")
TEMPLATES_FILE = os.path.join(BASE_DIR, "sms_templates.json")
LOG_FILE = os.path.join(BASE_DIR, "sms_engine.log")

load_dotenv(ENV_FILE, override=True)

class Settings:
    PROJECT_NAME: str = "JobRecruitment AI SMS Studio"
    VERSION: str = "3.0.0"
    
    # Live Backend
    WORKER_API_URL: str = os.getenv("WORKER_API_URL", "https://jobrecruitment.in/backend/api/worker-api.php").strip()
    WORKER_API_KEY: str = os.getenv("WORKER_API_KEY", "jrk_a537e025205460bf1da0ec9765a0e192d2a33b6c773fbdaa").strip()
    
    # AI API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "").strip()
    
    # Dispatch & Quotas
    SMS_MODE: str = os.getenv("SMS_MODE", "adb").strip().lower()
    ANDROID_GATEWAY_URL: str = os.getenv("ANDROID_GATEWAY_URL", "http://192.168.1.100:8080/send").strip()
    DAILY_SMS_LIMIT: int = int(os.getenv("DAILY_SMS_LIMIT", "180"))
    DISPATCH_DELAY_SECONDS: int = int(os.getenv("DISPATCH_DELAY_SECONDS", "5"))
    
    # Supabase Database
    SUPABASE_DB_URL: str = (os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    
    # Hostinger / Email Settings
    PHP_EMAIL_BRIDGE_URL: str = os.getenv("PHP_EMAIL_BRIDGE_URL", "https://jobrecruitment.in/backend/api/send_email.php").strip()
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.hostinger.com").strip()
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "hire@jobrecruitment.in").strip()
    SMTP_PASS: str = (
        os.getenv("SMTP_PASS")
        or os.getenv("SMTP_PASSWORD")
        or os.getenv("HOSTINGER_EMAIL_PASS")
        or os.getenv("HOSTINGER_PASS")
        or ""
    ).strip()
    RESEND_API_KEY: str = (os.getenv("RESEND_API_KEY") or os.getenv("RESEND_KEY") or "").strip()
    BREVO_API_KEY: str = (os.getenv("BREVO_API_KEY") or os.getenv("BREVO_KEY") or "").strip()
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "JobRecruitment AI SMS Studio").strip()

settings = Settings()

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
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(BASE_DIR)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(local_adb):
                return local_adb
        except Exception as e:
            print(f"[!] Auto-download ADB failed: {e}")
    return None
