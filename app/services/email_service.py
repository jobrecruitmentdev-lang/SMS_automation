"""
JobRecruitment.in — High-Speed Enterprise Multi-Channel Email Service
Optimized for <300ms low-latency dispatch and instant inbox delivery.
Supported Channels:
1. Resend HTTPS API (https://api.resend.com/emails) - Sub-200ms latency
2. Brevo HTTPS API (https://api.brevo.com/v3/smtp/email) - Sub-250ms latency
3. Hostinger HTTPS PHP Bridge (https://jobrecruitment.in/backend/api/send_email.php)
4. Hostinger SMTP Direct SSL (smtp.hostinger.com:465)
"""

import os
import smtplib
import ssl
import json
import requests
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.core.config import settings

class FastMultiChannelEmailService:
    def __init__(self):
        self.session = requests.Session()
        self.reload_config()

    def reload_config(self):
        self.resend_key = settings.RESEND_API_KEY
        self.brevo_key = settings.BREVO_API_KEY
        self.php_bridge_url = settings.PHP_EMAIL_BRIDGE_URL
        self.worker_api_key = settings.WORKER_API_KEY
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_pass = settings.SMTP_PASS
        self.from_name = settings.SMTP_FROM_NAME

    @property
    def is_configured(self):
        self.reload_config()
        return bool(self.resend_key or self.brevo_key or (self.php_bridge_url and self.worker_api_key) or (self.smtp_user and self.smtp_pass))

    def _send_via_resend(self, to_email: str, subject: str, html_content: str):
        """Ultra-fast transactional HTTPS dispatch (<200ms)."""
        if not self.resend_key:
            return False, "Resend API key not configured."
        try:
            from_sender = f"{self.from_name} <{self.smtp_user}>" if "@" in self.smtp_user else f"{self.from_name} <onboarding@resend.dev>"
            resp = self.session.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.resend_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": from_sender,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                },
                timeout=3.0
            )
            if resp.status_code in [200, 201]:
                return True, "Email dispatched via Resend HTTPS (Fast)."
            return False, f"Resend error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Resend connection error: {e}"

    def _send_via_brevo(self, to_email: str, subject: str, html_content: str):
        """High-speed Brevo HTTPS API (<250ms)."""
        if not self.brevo_key:
            return False, "Brevo API key not configured."
        try:
            resp = self.session.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": self.brevo_key,
                    "Content-Type": "application/json"
                },
                json={
                    "sender": {"name": self.from_name, "email": self.smtp_user},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html_content
                },
                timeout=3.0
            )
            if resp.status_code in [200, 201]:
                return True, "Email dispatched via Brevo HTTPS (Fast)."
            return False, f"Brevo error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Brevo connection error: {e}"

    def _send_via_hostinger_php_bridge(self, to_email: str, subject: str, html_content: str):
        """Dispatches via Hostinger PHP bridge on Port 443."""
        if not self.php_bridge_url or not self.worker_api_key:
            return False, "Hostinger PHP bridge URL or Worker API key missing."
        try:
            resp = self.session.post(
                self.php_bridge_url,
                json={
                    "to": to_email,
                    "subject": subject,
                    "html": html_content,
                    "from_name": self.from_name
                },
                headers={
                    "Authorization": f"Bearer {self.worker_api_key}",
                    "Content-Type": "application/json"
                },
                timeout=3.5
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return True, "Email sent via Hostinger PHP bridge."
            return False, f"Hostinger Bridge status {resp.status_code}"
        except Exception as e:
            return False, f"Hostinger PHP bridge error: {e}"

    def _send_via_smtp(self, to_email: str, subject: str, html_content: str, text_content: str = ""):
        """Direct Hostinger SMTP over TLS/SSL."""
        if not self.smtp_pass:
            return False, "SMTP_PASS not configured."
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.smtp_user}>"
            msg["To"] = to_email
            msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

            if text_content:
                msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with smtplib.SMTP_SSL(self.smtp_host, 465, context=ctx, timeout=3.0) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, [to_email], msg.as_string())
            return True, "Email sent successfully via Hostinger SMTP (465 SSL)."
        except Exception as e:
            return False, f"SMTP Error: {e}"

    def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = ""):
        self.reload_config()

        # 1. Primary Fastest: Resend HTTPS API (Fastest <200ms)
        if self.resend_key:
            ok, msg = self._send_via_resend(to_email, subject, html_content)
            if ok:
                return True, msg

        # 2. Secondary Fastest: Brevo HTTPS API (<250ms)
        if self.brevo_key:
            ok, msg = self._send_via_brevo(to_email, subject, html_content)
            if ok:
                return True, msg

        # 3. Tertiary: Direct SMTP (Hostinger 465 SSL)
        if self.smtp_pass:
            ok, msg = self._send_via_smtp(to_email, subject, html_content, text_content)
            if ok:
                return True, msg

        # 4. Quaternary: Hostinger PHP Bridge
        if self.worker_api_key and self.php_bridge_url:
            ok, msg = self._send_via_hostinger_php_bridge(to_email, subject, html_content)
            if ok:
                return True, msg

        return False, "All configured email delivery channels failed or credentials missing."

    def send_otp_email(self, to_email: str, otp_code: str, purpose: str = "Sign-In"):
        title_map = {
            "register": "New Recruiter Registration",
            "login": "Workspace Sign-In",
            "reset_password": "Password Reset"
        }
        title_text = title_map.get(purpose.lower(), f"Workspace {purpose}")
        subject = f"🔐 {otp_code} is your JobRecruitment Verification Code"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 20px; }}
                .card {{ max-width: 480px; margin: 0 auto; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 20px; padding: 32px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }}
                .badge {{ display: inline-block; padding: 6px 14px; background: rgba(20, 184, 166, 0.15); border: 1px solid #0d9488; color: #2dd4bf; border-radius: 12px; font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
                .code-box {{ margin: 24px 0; padding: 18px; background-color: #020617; border: 2px dashed #14b8a6; border-radius: 16px; text-align: center; }}
                .code {{ font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 900; letter-spacing: 8px; color: #5eead4; text-shadow: 0 0 10px rgba(94, 234, 212, 0.3); }}
                .footer {{ margin-top: 24px; font-size: 11px; color: #64748b; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 16px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="text-align: center; margin-bottom: 20px;">
                    <span class="badge">JobRecruitment SMS Studio</span>
                    <h2 style="color: #ffffff; margin-top: 12px; font-size: 22px; font-weight: 800;">{title_text}</h2>
                    <p style="color: #94a3b8; font-size: 13px; margin-top: 4px;">Use the one-time verification code below to verify your email.</p>
                </div>
                
                <div class="code-box">
                    <div class="code">{otp_code}</div>
                    <div style="color: #94a3b8; font-size: 11px; margin-top: 8px;">⏱️ Valid for 10 minutes • Single use only</div>
                </div>

                <p style="color: #cbd5e1; font-size: 12px; line-height: 1.6;">
                    If you did not request this verification code, please ignore this email or contact support at <a href="mailto:support@jobrecruitment.in" style="color: #2dd4bf; text-decoration: none;">support@jobrecruitment.in</a>.
                </p>

                <div class="footer">
                    🔒 Secured by JobRecruitment AI Cloud Authentication<br>
                    Sent automatically by <b>hire@jobrecruitment.in</b>
                </div>
            </div>
        </body>
        </html>
        """
        text = f"Your JobRecruitment verification code is: {otp_code}\nValid for 10 minutes."
        return self.send_email(to_email, subject, html, text)

    def send_otp_async(self, to_email: str, otp_code: str, purpose: str = "Sign-In"):
        """Fires email delivery in background thread for zero-latency instant API response (<50ms)."""
        t = threading.Thread(target=self.send_otp_email, args=(to_email, otp_code, purpose), daemon=True)
        t.start()
        return True, "Email dispatch initiated in background."

email_service = FastMultiChannelEmailService()
