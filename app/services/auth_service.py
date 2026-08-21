import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from app.core.config import BASE_DIR, settings
from app.core.security import hash_string, generate_numeric_otp, generate_pairing_code
from app.core.state import write_log
from app.services.email_service import email_service

class AuthService:
    def __init__(self):
        self.db_url = settings.SUPABASE_DB_URL
        self.enabled = bool(self.db_url)

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

    def _get_local_resets(self):
        rf = os.path.join(BASE_DIR, "studio_resets.json")
        if os.path.exists(rf):
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_local_resets(self, resets):
        rf = os.path.join(BASE_DIR, "studio_resets.json")
        try:
            with open(rf, "w", encoding="utf-8") as f:
                json.dump(resets, f, indent=2)
        except Exception:
            pass

    def request_registration_otp(self, email: str, full_name: str = "", role: str = "recruiter"):
        email_clean = email.lower().strip()
        name_clean = full_name.strip() if full_name else email_clean.split('@')[0].capitalize()

        # 1. Check if user already exists
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                cur = conn.cursor()
                cur.execute("SELECT id FROM studio_users WHERE email = %s", (email_clean,))
                if cur.fetchone():
                    conn.close()
                    return False, "An account with this email already exists. Please Sign In."
                conn.close()
            except Exception as e:
                write_log(f"[Auth] Supabase check user error: {e}")
        else:
            users = self._get_local_users()
            if email_clean in users:
                return False, "An account with this email already exists. Please Sign In."

        # 2. Generate and Hash OTP
        otp_code = generate_numeric_otp(6)
        otp_hash = hash_string(otp_code)
        expires_at = datetime.now() + timedelta(minutes=10)

        # Dispatch via Multi-Channel Mailer
        email_sent, email_msg = email_service.send_otp_email(email_clean, otp_code, purpose="register")
        write_log(f"[Auth] Register OTP to {email_clean} - Sent: {email_sent} - Result: {email_msg}")

        # Store in Database
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS studio_email_otps (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR(150) NOT NULL,
                        otp_hash VARCHAR(255) NOT NULL,
                        full_name VARCHAR(100),
                        role VARCHAR(20) DEFAULT 'recruiter',
                        purpose VARCHAR(30) NOT NULL DEFAULT 'register',
                        attempts INT NOT NULL DEFAULT 0,
                        expires_at TIMESTAMPTZ NOT NULL,
                        used_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                cur.execute("UPDATE studio_email_otps SET used_at = NOW() WHERE email = %s AND purpose = 'register' AND used_at IS NULL", (email_clean,))
                cur.execute("""
                    INSERT INTO studio_email_otps (email, otp_hash, full_name, role, purpose, expires_at)
                    VALUES (%s, %s, %s, %s, 'register', %s)
                """, (email_clean, otp_hash, name_clean, role, expires_at))
                conn.close()
                return True, {"message": f"Verification code sent to {email_clean}.", "email_sent": email_sent}
            except Exception as e:
                write_log(f"[Auth] Supabase OTP save error: {e}. Using local store...")

        # Local Fallback
        resets = self._get_local_resets()
        resets[f"reg_{email_clean}"] = {
            "otp_hash": otp_hash,
            "full_name": name_clean,
            "role": role,
            "purpose": "register",
            "attempts": 0,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "used": False
        }
        self._save_local_resets(resets)
        return True, {"message": f"Verification code sent to {email_clean}.", "email_sent": email_sent}

    def verify_registration_otp(self, email: str, otp_code: str):
        email_clean = email.lower().strip()
        otp_clean = str(otp_code).strip()
        otp_hash = hash_string(otp_clean)

        # 1. Supabase Check
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, full_name, role, expires_at, used_at, attempts, otp_hash
                    FROM studio_email_otps
                    WHERE email = %s AND purpose = 'register'
                    ORDER BY created_at DESC LIMIT 1
                """, (email_clean,))
                row = cur.fetchone()
                if row:
                    otp_id, f_name, role, exp_dt, used_dt, attempts, stored_hash = row
                    if used_dt is not None:
                        conn.close()
                        return False, "This verification code has already been used. Please request a new one."
                    if attempts >= 5:
                        conn.close()
                        return False, "Maximum verification attempts exceeded. Please request a new code."
                    if datetime.now(exp_dt.tzinfo if exp_dt.tzinfo else None) > exp_dt:
                        conn.close()
                        return False, "Verification code expired (10-minute limit). Please request a new code."
                    if stored_hash != otp_hash:
                        cur.execute("UPDATE studio_email_otps SET attempts = attempts + 1 WHERE id = %s", (otp_id,))
                        conn.close()
                        return False, f"Invalid verification code. ({4 - attempts} attempts remaining)"

                    cur.execute("UPDATE studio_email_otps SET used_at = NOW() WHERE id = %s", (otp_id,))
                    cur.execute("""
                        INSERT INTO studio_users (email, password_hash, full_name, role)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                        RETURNING id, email, full_name, role
                    """, (email_clean, "OTP_VERIFIED", f_name, role or "recruiter"))
                    u_row = cur.fetchone()
                    conn.close()
                    user_id_str = str(u_row[0])
                    return True, {
                        "id": user_id_str,
                        "email": u_row[1],
                        "name": u_row[2],
                        "role": u_row[3],
                        "pairing_code": generate_pairing_code(user_id_str)
                    }
                conn.close()
            except Exception as e:
                write_log(f"[Auth] Supabase verify register error: {e}")

        # 2. Local Fallback
        resets = self._get_local_resets()
        k = f"reg_{email_clean}"
        if k in resets:
            rec = resets[k]
            if rec.get("used"):
                return False, "This verification code has already been used."
            if rec.get("attempts", 0) >= 5:
                return False, "Maximum verification attempts exceeded. Please request a new code."
            exp = datetime.strptime(rec.get("expires_at"), "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp:
                return False, "Verification code expired. Please request a new code."
            if rec.get("otp_hash") != otp_hash:
                rec["attempts"] = rec.get("attempts", 0) + 1
                self._save_local_resets(resets)
                return False, "Invalid verification code. Please check your email."

            rec["used"] = True
            self._save_local_resets(resets)

            users = self._get_local_users()
            uid = str(uuid.uuid4())
            name = rec.get("full_name") or email_clean.split('@')[0].capitalize()
            role = rec.get("role", "recruiter")
            users[email_clean] = {
                "id": uid, "email": email_clean, "name": name, "role": role,
                "password_hash": "OTP_VERIFIED", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_local_users(users)
            return True, {
                "id": uid,
                "email": email_clean,
                "name": name,
                "role": role,
                "pairing_code": generate_pairing_code(uid)
            }

        return False, "No active registration request found. Please enter your details and click Register."

    def request_login_otp(self, email: str):
        email_clean = email.lower().strip()

        # 1. Verify user exists first
        user_record = None
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                cur = conn.cursor()
                cur.execute("SELECT id, email, full_name, role FROM studio_users WHERE email = %s", (email_clean,))
                user_record = cur.fetchone()
                conn.close()
            except Exception as e:
                write_log(f"[Auth] Supabase user query error: {e}")
        else:
            users = self._get_local_users()
            user_record = users.get(email_clean)

        if not user_record:
            return False, "No account found with this email. Please Register first."

        # 2. Generate and Hash OTP
        otp_code = generate_numeric_otp(6)
        otp_hash = hash_string(otp_code)
        expires_at = datetime.now() + timedelta(minutes=10)

        # Dispatch via Multi-Channel Mailer
        email_sent, email_msg = email_service.send_otp_email(email_clean, otp_code, purpose="login")
        write_log(f"[Auth] Login OTP to {email_clean} - Sent: {email_sent} - Result: {email_msg}")

        # Store in Database
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("UPDATE studio_email_otps SET used_at = NOW() WHERE email = %s AND purpose = 'login' AND used_at IS NULL", (email_clean,))
                cur.execute("""
                    INSERT INTO studio_email_otps (email, otp_hash, purpose, expires_at)
                    VALUES (%s, %s, 'login', %s)
                """, (email_clean, otp_hash, expires_at))
                conn.close()
                return True, {"message": f"Sign-in code sent to {email_clean}.", "email_sent": email_sent}
            except Exception as e:
                write_log(f"[Auth] Supabase Login OTP error: {e}")

        # Local Fallback
        resets = self._get_local_resets()
        resets[f"login_{email_clean}"] = {
            "otp_hash": otp_hash,
            "purpose": "login",
            "attempts": 0,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "used": False
        }
        self._save_local_resets(resets)
        return True, {"message": f"Sign-in code sent to {email_clean}.", "email_sent": email_sent}

    def verify_login_otp(self, email: str, otp_code: str):
        email_clean = email.lower().strip()
        otp_clean = str(otp_code).strip()
        otp_hash = hash_string(otp_clean)

        # 1. Supabase Check
        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, expires_at, used_at, attempts, otp_hash
                    FROM studio_email_otps
                    WHERE email = %s AND purpose IN ('login', 'register')
                    ORDER BY created_at DESC LIMIT 1
                """, (email_clean,))
                row = cur.fetchone()
                if row:
                    otp_id, exp_dt, used_dt, attempts, stored_hash = row
                    if used_dt is not None:
                        conn.close()
                        return False, "This OTP has already been used. Please request a new code."
                    if attempts >= 5:
                        conn.close()
                        return False, "Maximum verification attempts exceeded. Please request a new code."
                    if datetime.now(exp_dt.tzinfo if exp_dt.tzinfo else None) > exp_dt:
                        conn.close()
                        return False, "OTP expired (10-minute limit). Please request a new code."
                    if stored_hash != otp_hash:
                        cur.execute("UPDATE studio_email_otps SET attempts = attempts + 1 WHERE id = %s", (otp_id,))
                        conn.close()
                        return False, f"Invalid verification code. ({4 - attempts} attempts remaining)"

                    cur.execute("UPDATE studio_email_otps SET used_at = NOW() WHERE id = %s", (otp_id,))
                    cur.execute("SELECT id, email, full_name, role FROM studio_users WHERE email = %s", (email_clean,))
                    u_row = cur.fetchone()
                    conn.close()
                    if u_row:
                        user_id_str = str(u_row[0])
                        return True, {
                            "id": user_id_str,
                            "email": u_row[1],
                            "name": u_row[2],
                            "role": u_row[3],
                            "pairing_code": generate_pairing_code(user_id_str)
                        }
                conn.close()
            except Exception as e:
                write_log(f"[Auth] Supabase verify login error: {e}")

        # 2. Local Fallback
        resets = self._get_local_resets()
        for prefix in ["login_", "reg_", "otp_"]:
            k = f"{prefix}{email_clean}"
            if k in resets:
                rec = resets[k]
                if rec.get("used"):
                    continue
                if rec.get("attempts", 0) >= 5:
                    return False, "Maximum verification attempts exceeded. Please request a new code."
                exp = datetime.strptime(rec.get("expires_at"), "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp:
                    return False, "OTP expired. Please request a new code."
                if rec.get("otp_hash") != otp_hash:
                    rec["attempts"] = rec.get("attempts", 0) + 1
                    self._save_local_resets(resets)
                    return False, "Invalid verification code."
                
                rec["used"] = True
                self._save_local_resets(resets)

                users = self._get_local_users()
                u = users.get(email_clean)
                if u:
                    return True, {
                        "id": u["id"],
                        "email": u["email"],
                        "name": u["name"],
                        "role": u.get("role", "recruiter"),
                        "pairing_code": generate_pairing_code(u["id"])
                    }

        return False, "Invalid verification code or session expired. Please request a new OTP."

    def create_login_otp(self, email: str, full_name: str = "", role: str = "recruiter"):
        return self.request_login_otp(email)

    def signup_user(self, email: str, password: str, full_name: str, role: str = "recruiter"):
        email_clean = email.lower().strip()
        name_clean = full_name.strip()
        pwd_hash = hash_string(password)

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
                user_id_str = str(user[0])
                return True, {
                    "id": user_id_str,
                    "email": user[1],
                    "name": user[2],
                    "role": user[3],
                    "pairing_code": generate_pairing_code(user_id_str)
                }
            except Exception as e:
                err = str(e)
                if "unique" in err.lower():
                    return False, "Email is already registered. Please sign in."
                write_log(f"[Auth] Supabase direct error: {err}. Switching to Local High-Availability Store...")

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
        return True, {
            "id": uid,
            "email": email_clean,
            "name": name_clean,
            "role": role,
            "pairing_code": generate_pairing_code(uid)
        }

    def login_user(self, email: str, password: str):
        email_clean = email.lower().strip()
        pwd_hash = hash_string(password)

        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                cur = conn.cursor()
                cur.execute("SELECT id, email, full_name, role, password_hash FROM studio_users WHERE email = %s", (email_clean,))
                user = cur.fetchone()
                conn.close()
                if user:
                    if user[4] != pwd_hash:
                        return False, "Invalid password. Please try again."
                    uid_str = str(user[0])
                    return True, {
                        "id": uid_str,
                        "email": user[1],
                        "name": user[2],
                        "role": user[3],
                        "pairing_code": generate_pairing_code(uid_str)
                    }
            except Exception as e:
                write_log(f"[Auth] Supabase query error: {e}. Checking Local Store...")

        users = self._get_local_users()
        if email_clean in users:
            u = users[email_clean]
            if u.get("password_hash") != pwd_hash:
                return False, "Invalid password. Please try again."
            return True, {
                "id": u["id"],
                "email": u["email"],
                "name": u["name"],
                "role": u.get("role", "recruiter"),
                "pairing_code": generate_pairing_code(u["id"])
            }

        return False, "No account found with this email. Please register first."

    def create_password_reset(self, email: str):
        email_clean = email.lower().strip()
        raw_token = generate_numeric_otp(6)
        token_hash = hash_string(raw_token)
        expires_at = datetime.now() + timedelta(minutes=15)

        email_sent, email_msg = email_service.send_password_reset_email(email_clean, raw_token)
        write_log(f"[Auth] Hostinger Password Reset to {email_clean} - Sent: {email_sent} - Result: {email_msg}")

        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS studio_resets (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR(150) NOT NULL,
                        token_hash VARCHAR(255) NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        used_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                cur.execute("INSERT INTO studio_resets (email, token_hash, expires_at) VALUES (%s, %s, %s)", (email_clean, token_hash, expires_at))
                conn.close()
                return True, {"message": f"Password reset instructions sent to {email_clean}.", "token": raw_token}
            except Exception as e:
                write_log(f"[Auth] Supabase Reset direct error: {e}")

        resets = self._get_local_resets()
        resets[email_clean] = {
            "token_hash": token_hash,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "used": False
        }
        self._save_local_resets(resets)
        return True, {"message": f"Password reset instructions sent to {email_clean}.", "token": raw_token}

    def reset_password_with_token(self, email: str, token: str, new_password: str):
        email_clean = email.lower().strip()
        tok_clean = token.strip()
        new_pwd_hash = hash_string(new_password)
        token_hash = hash_string(tok_clean)

        if self.enabled:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url, connect_timeout=6)
                conn.autocommit = True
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, expires_at, used_at FROM studio_resets
                    WHERE email = %s AND token_hash = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (email_clean, token_hash))
                row = cur.fetchone()
                if row:
                    r_id, exp_dt, used_dt = row
                    if used_dt is not None:
                        conn.close()
                        return False, "This reset token has already been used."
                    if datetime.now(exp_dt.tzinfo if exp_dt.tzinfo else None) > exp_dt:
                        conn.close()
                        return False, "Reset token has expired (15-min limit)."
                    cur.execute("UPDATE studio_resets SET used_at = NOW() WHERE id = %s", (r_id,))
                    cur.execute("UPDATE studio_users SET password_hash = %s WHERE email = %s", (new_pwd_hash, email_clean))
                    conn.close()
                    return True, "Password has been reset successfully! You can now sign in."
                conn.close()
            except Exception as e:
                write_log(f"[Auth] Supabase reset verify error: {e}")

        resets = self._get_local_resets()
        if email_clean in resets:
            rec = resets[email_clean]
            if rec.get("token_hash") == token_hash:
                if rec.get("used"):
                    return False, "This reset token has already been used."
                exp = datetime.strptime(rec.get("expires_at"), "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp:
                    return False, "Reset token has expired."
                rec["used"] = True
                self._save_local_resets(resets)
                users = self._get_local_users()
                if email_clean in users:
                    users[email_clean]["password_hash"] = new_pwd_hash
                    self._save_local_users(users)
                return True, "Password reset successfully! You can now sign in."
        return False, "Invalid or expired reset token."

# Global singleton
auth_service = AuthService()
