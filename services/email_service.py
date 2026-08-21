"""
JobRecruitment.in — Multi-Channel Enterprise Email Service
Supported Channels:
1. Hostinger HTTPS PHP Bridge (https://jobrecruitment.in/backend/api/send_email.php) - Port 443
2. Resend HTTPS API (https://api.resend.com/emails) - Port 443
3. Brevo HTTPS API (https://api.brevo.com/v3/smtp/email) - Port 443
4. Direct Hostinger SMTP (smtp.hostinger.com) - Port 465 / 587 (Local fallback)
"""

import os
import smtplib
import ssl
import json
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class MultiChannelEmailService:
    def __init__(self):
        self.reload_config()

    def reload_config(self):
        self.php_bridge_url = os.getenv("PHP_EMAIL_BRIDGE_URL", "https://jobrecruitment.in/backend/api/send_email.php").strip()
        self.worker_api_key = os.getenv("WORKER_API_KEY", "jrk_a537e025205460bf1da0ec9765a0e192d2a33b6c773fbdaa").strip()
        self.resend_key = (os.getenv("RESEND_API_KEY") or os.getenv("RESEND_KEY") or "").strip()
        self.brevo_key = (os.getenv("BREVO_API_KEY") or os.getenv("BREVO_KEY") or "").strip()
        
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.hostinger.com").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user = os.getenv("SMTP_USER", "hire@jobrecruitment.in").strip()
        self.smtp_pass = (
            os.getenv("SMTP_PASS")
            or os.getenv("SMTP_PASSWORD")
            or os.getenv("HOSTINGER_EMAIL_PASS")
            or os.getenv("HOSTINGER_PASS")
            or os.getenv("EMAIL_PASS")
            or os.getenv("MAIL_PASSWORD")
            or ""
        ).strip()
        self.from_name = os.getenv("SMTP_FROM_NAME", "JobRecruitment AI SMS Studio").strip()

    @property
    def is_configured(self):
        self.reload_config()
        return bool(self.worker_api_key or self.resend_key or self.brevo_key or (self.smtp_user and self.smtp_pass))

    def _send_via_hostinger_php_bridge(self, to_email, subject, html_content):
        """Dispatches via Hostinger PHP bridge on Port 443 HTTPS (Never blocked by cloud firewalls)."""
        if not self.php_bridge_url or not self.worker_api_key:
            return False, "Hostinger PHP bridge URL or Worker API key missing."
        try:
            payload = json.dumps({
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "from_name": self.from_name
            }).encode("utf-8")
            
            req = urllib.request.Request(
                self.php_bridge_url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.worker_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "JobRecruitment-SMS-Studio/2.0"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        print(f"[EmailService] Hostinger PHP Bridge Success: Dispatched to {to_email}")
                        return True, "Email sent successfully via Hostinger PHP Bridge."
                return False, f"Hostinger PHP Bridge returned status {resp.status}"
        except Exception as e:
            return False, f"Hostinger PHP Bridge error: {str(e)}"

    def _send_via_resend(self, to_email, subject, html_content):
        import requests
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.resend_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": f"{self.from_name} <{self.smtp_user}>" if "@" in self.smtp_user else f"{self.from_name} <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                },
                timeout=8
            )
            if resp.status_code in [200, 201]:
                print(f"[EmailService] Resend HTTPS Success: Dispatched to {to_email}")
                return True, "Email sent successfully via Resend HTTPS API."
            return False, f"Resend API Error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Resend API Error: {e}"

    def _send_via_brevo(self, to_email, subject, html_content):
        import requests
        try:
            resp = requests.post(
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
                timeout=8
            )
            if resp.status_code in [200, 201]:
                print(f"[EmailService] Brevo HTTPS Success: Dispatched to {to_email}")
                return True, "Email sent successfully via Brevo HTTPS API."
            return False, f"Brevo API Error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Brevo API Error: {e}"

    def _send_via_smtp(self, to_email, subject, html_content, text_content=""):
        if not self.smtp_pass:
            return False, "SMTP_PASS not provided."
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.smtp_user}>"
        msg["To"] = to_email
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # Try Port 465 SSL first
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(self.smtp_host, 465, context=ctx, timeout=3.5) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, [to_email], msg.as_string())
            return True, "Email sent successfully via Hostinger SMTP (465)."
        except Exception as e:
            # Fallback to Port 587 STARTTLS
            try:
                with smtplib.SMTP(self.smtp_host, 587, timeout=3.5) as server:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    server.starttls(context=ctx)
                    server.login(self.smtp_user, self.smtp_pass)
                    server.sendmail(self.smtp_user, [to_email], msg.as_string())
                return True, "Email sent successfully via Hostinger SMTP (587)."
            except Exception as fallback_err:
                return False, f"SMTP Error: {e} | Fallback Error: {fallback_err}"

    def send_email(self, to_email, subject, html_content, text_content=""):
        self.reload_config()

        # 1. Primary: Hostinger HTTPS PHP Bridge (Port 443)
        if self.worker_api_key:
            ok, msg = self._send_via_hostinger_php_bridge(to_email, subject, html_content)
            if ok:
                return True, msg
            print(f"[EmailService] Hostinger PHP Bridge failed: {msg}. Trying next provider...")

        # 2. Secondary: Resend HTTPS API (Port 443)
        if self.resend_key:
            ok, msg = self._send_via_resend(to_email, subject, html_content)
            if ok:
                return True, msg
            print(f"[EmailService] Resend failed: {msg}. Trying next provider...")

        # 3. Tertiary: Brevo HTTPS API (Port 443)
        if self.brevo_key:
            ok, msg = self._send_via_brevo(to_email, subject, html_content)
            if ok:
                return True, msg
            print(f"[EmailService] Brevo failed: {msg}. Trying SMTP...")

        # 4. Quaternary: Direct SMTP (Port 465 / 587)
        if self.smtp_pass:
            ok, msg = self._send_via_smtp(to_email, subject, html_content, text_content)
            if ok:
                return True, msg

        return False, "All email delivery channels failed (Hostinger PHP bridge, Resend, Brevo, and SMTP)."

    def send_otp_email(self, to_email, otp_code, purpose="Sign-In"):
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

# Global singleton
email_service = MultiChannelEmailService()
