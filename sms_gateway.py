#!/usr/bin/env python3
"""
Hardware SMS Radio Bridge — Android Phone Dispatch
Supports:
  1. ADB Mode (Native GSM send via USB / Wi-Fi Debugging)
  2. HTTP Gateway Mode (Local Android SMS Gateway App)
"""

import os
import re
import shutil
import subprocess
import requests

class SMSGateway:
    def __init__(self, mode="adb", gateway_url="http://192.168.1.100:8080/send"):
        self.mode = mode.lower()
        self.gateway_url = gateway_url
        self.adb_bin = self._find_adb()

    def _find_adb(self):
        """Locates adb executable in PATH, local platform-tools, or Android SDK."""
        # 1. Check PATH
        adb_in_path = shutil.which("adb")
        if adb_in_path:
            return adb_in_path
        
        # 2. Check local platform-tools directory
        local_adb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform-tools", "adb.exe")
        if os.path.exists(local_adb):
            return local_adb
        
        # 3. Check standard Android SDK location
        sdk_adb = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
        if os.path.exists(sdk_adb):
            return sdk_adb
            
        return "adb" # fallback to default

    @staticmethod
    def clean_phone(phone_str):
        """Cleans and validates a 10-digit Indian phone number."""
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
        """Tests whether Android phone is connected and responsive."""
        if self.mode == "adb":
            adb_cmd = self._find_adb()
            try:
                res = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=5)
                lines = [l for l in res.stdout.strip().split('\n')[1:] if l.strip()]
                
                devices = []
                unauthorized = []
                for l in lines:
                    parts = l.split()
                    if len(parts) >= 2:
                        dev_id, status = parts[0], parts[1]
                        if status == "device":
                            devices.append(dev_id)
                        elif status == "unauthorized":
                            unauthorized.append(dev_id)
                
                if devices:
                    return True, f"Android Phone Connected (Device: {devices[0]})"
                elif unauthorized:
                    return False, "Device unauthorized. Please unlock phone and tap 'Allow USB Debugging'."
                return False, "No Android device detected. Connect phone via USB with USB Debugging ON."
            except FileNotFoundError:
                return False, "'adb' command not found. Run setup.bat to install portable ADB automatically."
            except Exception as e:
                return False, f"ADB Error: {str(e)}"
        else:
            try:
                # Ping HTTP Gateway
                res = requests.get(self.gateway_url.replace('/send', '/status'), timeout=3)
                if res.status_code in [200, 404]:
                    return True, f"HTTP SMS Gateway Connected ({self.gateway_url})"
                return False, f"HTTP Gateway returned status {res.status_code}"
            except Exception as e:
                return False, f"Cannot reach Android Gateway ({self.gateway_url}): {str(e)}"

    def send_sms(self, phone, message):
        """
        Sends an SMS to a 10-digit Indian phone number.
        Returns: (success: bool, response_msg: str)
        """
        clean_num = self.clean_phone(phone)
        if not clean_num:
            return False, f"Invalid Indian phone number: {phone}"

        if not message or not message.strip():
            return False, "Message body cannot be empty"

        if self.mode == "adb":
            return self._send_via_adb(clean_num, message.strip())
        else:
            return self._send_via_http(clean_num, message.strip())

    def _send_via_adb(self, phone, message):
        adb_cmd = self._find_adb()
        try:
            # First check if phone is physically connected
            res_dev = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=5)
            lines = [l for l in res_dev.stdout.strip().split('\n')[1:] if l.strip()]
            connected = [l.split()[0] for l in lines if '\tdevice' in l]
            if not connected:
                if any('unauthorized' in l for l in lines):
                    return False, "Phone unauthorized. Unlock phone & tap 'Allow USB Debugging'."
                return False, "No Android device connected. Please plug in USB and turn ON USB Debugging."

            # Primary send: Android isms send-text
            intent_cmd = [
                adb_cmd, "shell", "cmd", "isms", "send-text",
                "--sub-id", "0",
                phone,
                message
            ]
            
            res = subprocess.run(intent_cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return True, "Dispatched via Android isms"
            
            # Alternative Android fallback: am start SMS intent
            escaped_msg = message.replace('"', '\\"').replace("'", "\\'")
            alt_cmd = f'"{adb_cmd}" shell am start -a android.intent.action.SENDTO -d sms:{phone} --es sms_body "{escaped_msg}" --ez exit_on_sent true'
            subprocess.run(alt_cmd, shell=True, capture_output=True, timeout=10)
            # Press send button via keyevent 22 (right) + 66 (enter)
            subprocess.run([adb_cmd, "shell", "input", "keyevent", "22"], timeout=2)
            subprocess.run([adb_cmd, "shell", "input", "keyevent", "66"], timeout=2)
            return True, "Dispatched via Android UI automation"
        except FileNotFoundError:
            return False, "ADB not found. Please run setup.bat to download ADB automatically."
        except Exception as e:
            return False, f"ADB Dispatch Error: {str(e)}"

    def _send_via_http(self, phone, message):
        try:
            payload = {
                "to": f"+91{phone}",
                "message": message
            }
            res = requests.post(self.gateway_url, json=payload, timeout=8)
            if res.status_code in [200, 201, 202]:
                return True, "Dispatched via HTTP Gateway APK"
            return False, f"Gateway Error {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Gateway Network Error: {str(e)}"
