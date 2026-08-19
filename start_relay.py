#!/usr/bin/env python3
"""
================================================================================
  JobRecruitment — Cloud-to-Phone Local Relay Bridge Agent
  Role: Connects local phone ADB (192.168.1.x / USB) to Render Cloud Server
  Run: python start_relay.py (or double-click start_relay.bat)
================================================================================
"""

import os
import sys
import re
import time
import json
import random
import urllib.request
import subprocess

# Ensure UTF-8 output encoding on all Windows consoles and terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL", "https://sms-automation-q1zf.onrender.com")

def find_local_adb():
    base = os.path.dirname(os.path.abspath(__file__))
    local_pt = os.path.join(base, "platform-tools", "adb.exe" if sys.platform == "win32" else "adb")
    if os.path.exists(local_pt):
        return local_pt
    import shutil
    sys_adb = shutil.which("adb")
    if sys_adb:
        return sys_adb
    
    # Auto-bootstrap official Google platform-tools if downloaded in any random folder
    print("[*] ADB not found. Downloading official Google platform-tools...")
    try:
        import zipfile
        url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" if sys.platform == "win32" else "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
        zip_dest = os.path.join(base, "platform-tools.zip")
        urllib.request.urlretrieve(url, zip_dest)
        with zipfile.ZipFile(zip_dest, 'r') as zip_ref:
            zip_ref.extractall(base)
        if os.path.exists(zip_dest):
            os.remove(zip_dest)
        if os.path.exists(local_pt):
            print("[+] Platform-tools configured successfully!")
            return local_pt
    except Exception as e:
        print(f"[!] Auto-download warning: {e}")

    return "adb"

ADB_BIN = find_local_adb()

def get_phone_diagnostics():
    try:
        r = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, timeout=4)
        devs = []
        for line in r.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devs.append(parts[0])
                
        if not devs:
            return {
                "is_connected": False,
                "device_id": "None",
                "device_name": "No phone connected",
                "carrier": "None",
                "battery": "--%",
                "temperature": "--°C",
                "is_screen_locked": False,
                "screen_state_text": "Disconnected"
            }
        
        dev_id = devs[0]
        # Fast Single-Pass Multi-Property Batch Probe (< 200ms)
        probe_script = "getprop ro.product.manufacturer; echo '===P1==='; getprop ro.product.model; echo '===P2==='; getprop ro.build.version.release; echo '===P3==='; dumpsys battery; echo '===P4==='; wm size; echo '===P5==='; dumpsys window; echo '===P6==='; dumpsys telephony.registry"
        probe_res = subprocess.run([ADB_BIN, "-s", dev_id, "shell", probe_script], capture_output=True, text=True, timeout=4)
        parts = probe_res.stdout.split('===P')
        
        p_mfg = parts[0].strip().title() if len(parts) > 0 else "Android"
        p_model = parts[1].replace('1===', '').strip() if len(parts) > 1 else "Device"
        p_ver = parts[2].replace('2===', '').strip() if len(parts) > 2 else "14"
        p_bat = parts[3].replace('3===', '') if len(parts) > 3 else ""
        p_wm = parts[4].replace('4===', '') if len(parts) > 4 else ""
        p_win = parts[5].replace('5===', '') if len(parts) > 5 else ""
        p_tel = parts[6].replace('6===', '') if len(parts) > 6 else ""

        # Device Name
        device_name = f"{p_mfg} {p_model}".strip() or dev_id

        # Battery & Temp
        bat_lvl_m = re.search(r'level:\s*(\d+)', p_bat)
        bat_temp_m = re.search(r'temperature:\s*(\d+)', p_bat)
        bat_ac_m = re.search(r'AC powered:\s*(true|false)', p_bat, re.I)
        bat_usb_m = re.search(r'USB powered:\s*(true|false)', p_bat, re.I)

        bat_level = int(bat_lvl_m.group(1)) if bat_lvl_m else 100
        raw_temp = int(bat_temp_m.group(1)) if bat_temp_m else 300
        temp_c = round(raw_temp / 10.0, 1)
        is_charging = (bat_ac_m and bat_ac_m.group(1).lower() == 'true') or (bat_usb_m and bat_usb_m.group(1).lower() == 'true')

        battery_str = f"{bat_level}% ({'Charging ⚡' if is_charging else 'Discharging'})"
        temp_str = f"{temp_c}°C ({'Cool ❄️' if temp_c < 36 else 'Warm ♨️'})"

        # Screen Lock
        is_locked = "mDreamingLockscreen=true" in p_win or "mShowingDream=true" in p_win or "keyguard_upper_fingerprint_indication" in p_win or "isStatusBarKeyguard=true" in p_win
        screen_text = "⚠️ Screen Locked" if is_locked else "🟢 Screen Unlocked (Ready)"

        # Carrier
        carriers = list(set(re.findall(r'mOperatorAlphaLong=([^,\n]+)', p_tel)))
        carriers = [c.strip() for c in carriers if c.strip() and "null" not in c.lower()]
        carrier_str = carriers[0] if carriers else "Jio True5G"

        return {
            "is_connected": True,
            "device_id": dev_id,
            "device_name": device_name,
            "carrier": carrier_str,
            "battery": battery_str,
            "temperature": temp_str,
            "is_screen_locked": is_locked,
            "screen_state_text": screen_text
        }
    except Exception as e:
        return {
            "is_connected": False,
            "device_id": "None",
            "device_name": "ADB Offline",
            "carrier": "None",
            "battery": "--%",
            "temperature": "--°C",
            "is_screen_locked": False,
            "screen_state_text": f"Error: {e}"
        }

def send_local_sms(phone, msg):
    clean_phone = "".join(filter(str.isdigit, str(phone)))[-10:]
    if not clean_phone:
        return False, "Invalid phone number"
        
    try:
        # 1. Wake Screen & Dismiss Keyguard (Screen Auto-Unlock)
        subprocess.run([ADB_BIN, "shell", "input", "keyevent", "224"], timeout=3)
        subprocess.run([ADB_BIN, "shell", "wm", "dismiss-keyguard"], timeout=3)
        subprocess.run([ADB_BIN, "shell", "input", "keyevent", "82"], timeout=2) # Unlock menu fallback

        # 2. Launch SMS conversation draft in default messaging app
        encoded_msg = urllib.parse.quote(msg)
        am_cmd = f'"{ADB_BIN}" shell am start -a android.intent.action.SENDTO -d "sms:{clean_phone}?body={encoded_msg}" --ez exit_on_sent true'
        subprocess.run(am_cmd, shell=True, capture_output=True, timeout=6)
        
        # Give Android UI 0.9s to render conversation
        time.sleep(0.9)

        # 3. Precision Multi-Point Send Triggers (Calibrated for Samsung Galaxy OneUI & Google Messages)
        # Button Location 1: Below input (e.g. 982, 2256 on 1080x2400)
        # Button Location 2: Above keyboard (e.g. 982, 1344)
        subprocess.run([ADB_BIN, "shell", "input", "tap", "982", "2256"], timeout=3)
        time.sleep(0.15)
        subprocess.run([ADB_BIN, "shell", "input", "tap", "982", "1344"], timeout=3)
        time.sleep(0.15)
        subprocess.run([ADB_BIN, "shell", "input", "keyevent", "66"], timeout=2) # Enter keyevent

        return True, "Dispatched via Physical SIM (Samsung OneUI Radio)"
    except Exception as e:
        return False, str(e)

def post_json(endpoint, data):
    url = f"{CLOUD_SERVER_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "JR-Relay-Agent/1.0", "Connection": "close"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"ok": False}

def get_json(endpoint):
    url = f"{CLOUD_SERVER_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "JR-Relay-Agent/1.0", "Connection": "close"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

def get_relay_config():
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relay_config.json")
    data = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    return config_file, data

def save_relay_config(config_file, data):
    try:
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def try_wifi_pair_interactive():
    print("\n" + "=" * 70)
    print(" 📶 1-CLICK WIRELESS WI-FI PAIRING (NO USB CABLE NEEDED)")
    print(" 1. Phone me Settings > Developer Options > Wireless Debugging ko ON karein.")
    print(" 2. 'Pair device with pairing code' par tap karein.")
    print("=" * 70)
    pair_ip = input(" Enter Pairing IP:Port (e.g. 192.168.1.13:37891): ").strip()
    pair_pin = input(" Enter 6-Digit Pairing PIN (e.g. 482910): ").strip()

    if pair_ip and pair_pin:
        print(f"[*] Pairing with {pair_ip}...")
        subprocess.run([ADB_BIN, "pair", pair_ip, pair_pin], timeout=10)
    
    print("-" * 70)
    main_ip = input(" Enter Main Wireless Debugging IP:Port (e.g. 192.168.1.13:44711): ").strip()
    if main_ip:
        print(f"[*] Connecting to {main_ip}...")
        r = subprocess.run([ADB_BIN, "connect", main_ip], capture_output=True, text=True, timeout=10)
        print(f"[+] Output: {r.stdout.strip()}")
        return main_ip
    return None

def get_saved_pairing_code():
    config_file, data = get_relay_config()
    if data.get("pairing_code"):
        return data["pairing_code"]
    
    print("\n" + "=" * 60)
    print(" 🔑 RECRUITER PAIRING CODE SETUP")
    print(" Open https://sms-automation-q1zf.onrender.com to get your 6-digit Code.")
    print("=" * 60)
    code = input(" Enter your Recruiter Pairing Code (e.g. JR-849201): ").strip().upper()
    if not code:
        code = "JR-DEFAULT"
    
    data["pairing_code"] = code
    save_relay_config(config_file, data)
    return code

def auto_connect_saved_wifi():
    config_file, data = get_relay_config()
    saved_ip = data.get("saved_wifi_ip")
    if saved_ip:
        try:
            subprocess.run([ADB_BIN, "connect", saved_ip], capture_output=True, text=True, timeout=4)
        except Exception:
            pass

def main():
    pairing_code = get_saved_pairing_code()
    auto_connect_saved_wifi()

    print("=" * 72)
    print(" 🚀 JobRecruitment Cloud-to-Phone Local Relay Bridge")
    print(f" 🌐 Connected to Cloud: {CLOUD_SERVER_URL}")
    print(f" 🔑 Recruiter Code:     {pairing_code}")
    print(f" 📱 Local ADB Engine:   {ADB_BIN}")
    print("=" * 72)

    # Pre-check if phone is already attached
    diag = get_phone_diagnostics()
    if not diag["is_connected"]:
        print("\n" + "=" * 70)
        print(" 📱 NO PHONE DETECTED YET! HOW WOULD YOU LIKE TO CONNECT?")
        print(" [1] 🔌 USB Cable (Plug in phone & tap 'Allow' on screen)")
        print(" [2] 📶 Wireless Wi-Fi (No cable - enter IP & 6-digit PIN)")
        print("=" * 70)
        choice = input(" Select option [1 or 2, default=1]: ").strip()
        if choice == "2":
            connected_ip = try_wifi_pair_interactive()
            if connected_ip:
                config_file, data = get_relay_config()
                data["saved_wifi_ip"] = connected_ip
                save_relay_config(config_file, data)

    greetings_pool = ["Hi", "Hello", "Dear", "Greetings"]
    device_printed = False

    # Check connection right away
    diag = get_phone_diagnostics()
    if diag["is_connected"]:
        print(f"\n[🟢 PHONE DETECTED & LINKED TO CLOUD!] Device: {diag['device_name']} | Carrier: {diag['carrier']} | Battery: {diag['battery']} | Temp: {diag['temperature']}")
        print(f"[*] Cloud Relay is LIVE! You can now trigger SMS dispatches from the website.\n")
        device_printed = True

    while True:
        try:
            # 1. Heartbeat with 5-point telemetry to Cloud Server for this specific Recruiter
            diag = get_phone_diagnostics()
            post_json("/api/relay/heartbeat", {
                "pairing_code": pairing_code,
                "device_id": diag["device_id"],
                "device_name": diag["device_name"] if diag["is_connected"] else "Waiting for Phone...",
                "carrier": diag["carrier"],
                "battery": diag["battery"],
                "temperature": diag["temperature"],
                "is_screen_locked": diag["is_screen_locked"],
                "screen_state_text": diag["screen_state_text"],
                "is_online": diag["is_connected"]
            })

            if not diag["is_connected"]:
                device_printed = False
                print(f"[*] Waiting for phone... (Plug USB or enable Wireless Debugging)   ", end="\r")
                time.sleep(3)
                continue

            if not device_printed:
                print(f"\n[🟢 PHONE DETECTED & LINKED TO CLOUD!] Device: {diag['device_name']} | Carrier: {diag['carrier']} | Battery: {diag['battery']} | Temp: {diag['temperature']}")
                print(f"[*] Cloud Relay is LIVE! You can now trigger SMS dispatches from the website.\n")
                device_printed = True

            # 2. Poll for pending jobs specifically for this Recruiter
            res = get_json(f"/api/relay/poll_jobs?pairing_code={pairing_code}")
            if res.get("has_job") and res.get("job"):
                job = res["job"]

                # Handle Remote Action Commands
                action = job.get("action")
                if action == "UNLOCK_SCREEN":
                    print(f"[*] [Remote Command] Waking and unlocking phone screen...")
                    subprocess.run([ADB_BIN, "shell", "input", "keyevent", "224"], timeout=3)
                    subprocess.run([ADB_BIN, "shell", "wm", "dismiss-keyguard"], timeout=3)
                    subprocess.run([ADB_BIN, "shell", "input", "keyevent", "82"], timeout=2)
                    continue
                elif action == "RECONNECT_SOCKETS":
                    print(f"[*] [Remote Command] Refreshing Wi-Fi sockets...")
                    auto_connect_saved_wifi()
                    continue

                cands = job.get("candidates", [])
                template = job.get("template", "")
                role = job.get("role", "Candidate")
                location = job.get("location", "India")
                company = job.get("company", "Job Recruitment")
                base_delay = float(job.get("delay", 5.0))

                print(f"\n[⚡ NEW CAMPAIGN RECEIVED FOR {pairing_code}] '{job.get('campaign_title')}' - {len(cands)} SMS")

                for i, c in enumerate(cands, 1):
                    c_name = c.get("name") or "Candidate"
                    c_phone = c.get("phone")

                    # Dynamic Spintax
                    chosen_greeting = greetings_pool[(i - 1) % len(greetings_pool)]
                    cand_msg = template.replace("{name}", c_name).replace("{role}", role).replace("{location}", location).replace("{company}", company)
                    for g in ["Hi", "Hello", "Dear", "Greetings"]:
                        if cand_msg.startswith(f"{g} "):
                            cand_msg = f"{chosen_greeting} " + cand_msg[len(g) + 1:]
                            break
                    if "JobRecruitment" not in cand_msg and "HR" not in cand_msg:
                        cand_msg = f"{cand_msg} - HR Team, JobRecruitment.in"

                    # Send through physical SIM
                    ok, resp = send_local_sms(c_phone, cand_msg)
                    status_log = f"[{i}/{len(cands)}] {'Sent to' if ok else 'Failed for'} {c_name} (+91-{c_phone})"
                    print(f" {'✅' if ok else '❌'} {status_log}")

                    # Report status back to cloud
                    post_json("/api/relay/report_status", {
                        "pairing_code": pairing_code,
                        "current_index": i,
                        "is_sent": ok,
                        "log_line": status_log,
                        "is_finished": (i == len(cands))
                    })

                    if i < len(cands):
                        jitter = random.uniform(base_delay, base_delay + 3.5)
                        time.sleep(jitter)

                print("[*] Campaign complete! Listening for next job...\n")

        except Exception as e:
            # Silent retry
            time.sleep(3)

        time.sleep(2)

if __name__ == "__main__":
    main()
