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
import time
import json
import random
import urllib.request
import subprocess

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
        r = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, timeout=3)
        devs = [l.split()[0] for l in r.stdout.splitlines()[1:] if "\tdevice" in l]
        if not devs:
            return False, "No device connected", "None", "--%"
        
        dev_id = devs[0]
        # Model
        m_res = subprocess.run([ADB_BIN, "-s", dev_id, "shell", "getprop", "ro.product.model"], capture_output=True, text=True, timeout=3)
        model = m_res.stdout.strip() or dev_id
        
        # Battery
        b_res = subprocess.run([ADB_BIN, "-s", dev_id, "shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=3)
        bat = "100%"
        for l in b_res.stdout.splitlines():
            if "level:" in l:
                bat = l.split(":")[1].strip() + "%"
                break
        return True, model, "Jio True5G", bat
    except Exception as e:
        return False, "ADB Offline", "None", "--%"

def send_local_sms(phone, msg):
    clean_phone = "".join(filter(str.isdigit, str(phone)))[-10:]
    try:
        cmd = [
            ADB_BIN, "shell", "service", "call", "isms", "5",
            "i32", "0",
            "s16", "com.android.mms",
            "s16", "null",
            "s16", clean_phone,
            "s16", "null",
            "s16", msg,
            "s16", "null",
            "s16", "null",
            "i32", "0",
            "i32", "0"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return r.returncode == 0, r.stdout
    except Exception as e:
        return False, str(e)

def post_json(endpoint, data):
    url = f"{CLOUD_SERVER_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "JR-Relay-Agent/1.0"}
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(endpoint):
    url = f"{CLOUD_SERVER_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "JR-Relay-Agent/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))

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
    is_connected, dev_name, carrier, battery = get_phone_diagnostics()
    if not is_connected:
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

    while True:
        try:
            # 1. Heartbeat to Cloud Server for this specific Recruiter
            is_connected, dev_name, carrier, battery = get_phone_diagnostics()
            post_json("/api/relay/heartbeat", {
                "pairing_code": pairing_code,
                "device_name": dev_name if is_connected else "Waiting for Phone...",
                "carrier": carrier,
                "battery": battery
            })

            if not is_connected:
                print(f"[*] Waiting for phone... (Plug USB or enable Wireless Debugging)", end="\r")
                time.sleep(3)
                continue

            if not device_printed:
                print(f"\n[🟢 PHONE DETECTED & LINKED TO CLOUD!] Device: {dev_name} | Carrier: {carrier} | Battery: {battery}")
                print(f"[*] Cloud Relay is LIVE! You can now trigger SMS dispatches from the website.\n")
                device_printed = True

            # 2. Poll for pending jobs specifically for this Recruiter
            res = get_json(f"/api/relay/poll_jobs?pairing_code={pairing_code}")
            if res.get("has_job") and res.get("job"):
                job = res["job"]
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
