"""
JobRecruitment.in — Production Hostinger SMTP Mailer Service
Role: Sends enterprise OTPs, verification tokens, and pairing codes via hire@jobrecruitment.in
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class HostingerEmailService:
    def reload_config(self):
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
        return bool(self.smtp_user and self.smtp_pass)

    def test_connection(self, to_email="hire@jobrecruitment.in"):
        """Performs a 4-step network and authentication diagnostic."""
        self.reload_config()
        results = {
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "has_password": bool(self.smtp_pass),
            "steps": {}
        }

        # Step 1: DNS Resolution
        import socket
        try:
            ip = socket.gethostbyname(self.smtp_host)
            results["steps"]["1_dns_resolution"] = f"OK ({ip})"
        except Exception as e:
            results["steps"]["1_dns_resolution"] = f"FAILED: {e}"
            return False, results

        # Step 2: TCP Socket Test (Port 465 & 587)
        for p in [465, 587]:
            try:
                s = socket.create_connection((self.smtp_host, p), timeout=4)
                s.close()
                results["steps"][f"2_tcp_port_{p}"] = "CONNECTED"
            except Exception as e:
                results["steps"][f"2_tcp_port_{p}"] = f"BLOCKED/TIMEOUT: {e}"

        # Step 3: SMTP Handshake & Login
        if not self.smtp_pass:
            results["steps"]["3_smtp_auth"] = "SKIPPED: SMTP_PASS not set in environment."
            return False, results

        # Try Port 465 SSL
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(self.smtp_host, 465, context=ctx, timeout=6) as srv:
                srv.login(self.smtp_user, self.smtp_pass)
                results["steps"]["3_smtp_auth_465"] = "SUCCESS (SSL Login OK)"
                # Step 4: Send test email
                msg = MIMEText("JobRecruitment SMTP Diagnostic Verification OK", "plain", "utf-8")
                msg["Subject"] = "JobRecruitment SMTP Diagnostic Test"
                msg["From"] = f"{self.from_name} <{self.smtp_user}>"
                msg["To"] = to_email
                srv.sendmail(self.smtp_user, [to_email], msg.as_string())
                results["steps"]["4_test_send"] = f"SUCCESS: Delivered to {to_email}"
                return True, results
        except Exception as e:
            results["steps"]["3_smtp_auth_465"] = f"FAILED: {e}"

        # Try Port 587 STARTTLS
        try:
            with smtplib.SMTP(self.smtp_host, 587, timeout=6) as srv:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                srv.starttls(context=ctx)
                srv.login(self.smtp_user, self.smtp_pass)
                results["steps"]["3_smtp_auth_587"] = "SUCCESS (STARTTLS Login OK)"
                msg = MIMEText("JobRecruitment SMTP Diagnostic Verification OK", "plain", "utf-8")
                msg["Subject"] = "JobRecruitment SMTP Diagnostic Test"
                msg["From"] = f"{self.from_name} <{self.smtp_user}>"
                msg["To"] = to_email
                srv.sendmail(self.smtp_user, [to_email], msg.as_string())
                results["steps"]["4_test_send"] = f"SUCCESS: Delivered to {to_email}"
                return True, results
        except Exception as e:
            results["steps"]["3_smtp_auth_587"] = f"FAILED: {e}"

        return False, results

    def send_email(self, to_email, subject, html_content, text_content=""):
        self.reload_config()
        if not self.is_configured:
            err = "[EmailService] SMTP credentials not configured (SMTP_PASS missing in Render env variables)."
            print(err)
            return False, err

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
            with smtplib.SMTP_SSL(self.smtp_host, 465, context=ctx, timeout=6) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, [to_email], msg.as_string())
            print(f"[EmailService] Port 465 Success: Dispatched '{subject}' to {to_email}")
            return True, "Email sent successfully."
        except Exception as e:
            # Fallback to Port 587 STARTTLS
            try:
                with smtplib.SMTP(self.smtp_host, 587, timeout=6) as server:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    server.starttls(context=ctx)
                    server.login(self.smtp_user, self.smtp_pass)
                    server.sendmail(self.smtp_user, [to_email], msg.as_string())
                print(f"[EmailService] Port 587 Success: Dispatched via 587 to {to_email}")
                return True, "Email sent successfully (fallback port 587)."
            except Exception as fallback_err:
                err_msg = f"Hostinger SMTP (465): {e} | Fallback (587): {fallback_err}"
                print(f"[EmailService] {err_msg}")
                return False, err_msg

    def send_otp_email(self, to_email, otp_code, purpose="Authentication"):
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
                    <h2 style="color: #ffffff; margin-top: 12px; font-size: 22px; font-weight: 800;">Workspace {purpose}</h2>
                    <p style="color: #94a3b8; font-size: 13px; margin-top: 4px;">Use the one-time verification code below to verify your session.</p>
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

    def send_password_reset_email(self, to_email, reset_token):
        subject = f"🔑 Password Reset Code: {reset_token} — JobRecruitment SMS Studio"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 20px; }}
                .card {{ max-width: 480px; margin: 0 auto; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 20px; padding: 32px; }}
                .badge {{ display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid #dc2626; color: #f87171; border-radius: 12px; font-weight: bold; font-size: 11px; text-transform: uppercase; }}
                .code-box {{ margin: 24px 0; padding: 18px; background-color: #020617; border: 2px dashed #f87171; border-radius: 16px; text-align: center; }}
                .code {{ font-family: 'Courier New', Courier, monospace; font-size: 32px; font-weight: 900; letter-spacing: 6px; color: #fca5a5; }}
                .footer {{ margin-top: 24px; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; padding-top: 16px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="text-align: center; margin-bottom: 20px;">
                    <span class="badge">Security Alert</span>
                    <h2 style="color: #ffffff; margin-top: 12px; font-size: 20px; font-weight: 800;">Password Reset Request</h2>
                    <p style="color: #94a3b8; font-size: 13px;">We received a request to reset the password for <b>{to_email}</b>.</p>
                </div>
                
                <div class="code-box">
                    <div class="code">{reset_token}</div>
                    <div style="color: #94a3b8; font-size: 11px; margin-top: 8px;">⏱️ Code expires in 15 minutes</div>
                </div>

                <p style="color: #cbd5e1; font-size: 12px; line-height: 1.6;">
                    Paste this code on the reset password screen to create a new password. If you did not make this request, you can safely ignore this email.
                </p>

                <div class="footer">
                    Sent via Hostinger SMTP Mailer (hire@jobrecruitment.in) • JobRecruitment Security
                </div>
            </div>
        </body>
        </html>
        """
        text = f"Your JobRecruitment password reset code is: {reset_token}\nExpires in 15 minutes."
        return self.send_email(to_email, subject, html, text)

# Global singleton
email_service = HostingerEmailService()
