import hashlib
import secrets

def hash_string(raw: str) -> str:
    """Computes SHA-256 hex digest of a string."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def generate_numeric_otp(digits: int = 6) -> str:
    """Generates a secure cryptographically random numeric OTP code."""
    min_val = 10 ** (digits - 1)
    max_val = (10 ** digits) - 1
    return str(secrets.randbelow(max_val - min_val + 1) + min_val)

def generate_pairing_code(user_id: str) -> str:
    """Derives a clean, deterministic, tenant-isolated pairing code (e.g. JR-635287)."""
    if not user_id:
        return "JR-DEFAULT"
    clean_id = str(user_id).strip().replace("-", "").upper()
    if clean_id.startswith("JR"):
        clean_id = clean_id[2:]
    if len(clean_id) >= 6:
        # Use deterministic hash of UUID to produce a clean 6-digit number
        h = hashlib.sha256(clean_id.encode("utf-8")).hexdigest()
        numeric_suffix = str(int(h[:8], 16))[:6].zfill(6)
        return f"JR-{numeric_suffix}"
    return f"JR-{clean_id.ljust(6, '0')}"
