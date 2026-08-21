import time
import socket
import threading
import requests
import pytest
import uvicorn
from main import app

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def api_server():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.6)
    yield base_url
    server.should_exit = True

class TestStudioRESTApi:
    def test_get_quota_endpoint(self, api_server):
        resp = requests.get(f"{api_server}/api/quota", timeout=4)
        assert resp.status_code == 200
        data = resp.json()
        assert "sent_today" in data
        assert "daily_limit" in data

    def test_post_validate_sms_endpoint(self, api_server):
        resp = requests.post(
            f"{api_server}/api/validate_sms",
            json={"text": "Hello {name}, visit https://jobrecruitment.in", "seed": 0},
            timeout=4
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["encoding"] == "GSM-7 (Standard)"
        assert data["is_unicode"] is False
        assert "spun_preview" in data

    def test_gateway_register_and_heartbeat(self, api_server):
        # 1. Register Mobile Device
        reg_payload = {
            "pairing_code": "JR-TEST99",
            "device_name": "Test Galaxy S23",
            "carrier": "Jio True5G",
            "battery": "95%",
            "sim_slot": 0
        }
        resp = requests.post(f"{api_server}/api/gateway/register", json=reg_payload, timeout=4)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "token" in data

        # 2. Drain Jobs
        poll_resp = requests.get(f"{api_server}/api/relay/drain_jobs?pairing_code=JR-TEST99", timeout=4)
        assert poll_resp.status_code == 200
        data = poll_resp.json()
        assert "jobs" in data

    def test_download_apk_route(self, api_server):
        resp = requests.get(f"{api_server}/download/JobRecruitment-Gateway.apk", timeout=4)
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/vnd.android.package-archive"
        assert len(resp.content) > 1000

        resp2 = requests.get(f"{api_server}/download/jobrecruitment-companion.apk", timeout=4)
        assert resp2.status_code == 200
        assert resp2.headers.get("content-type") == "application/vnd.android.package-archive"

    def test_relay_status_pairing_code_detection(self, api_server):
        # Heartbeat from phone with pairing code JR-275900
        hb_payload = {
            "pairing_code": "JR-275900",
            "device_name": "Samsung Galaxy S24",
            "carrier": "Jio True5G",
            "battery": "88%",
            "is_online": True
        }
        hb_resp = requests.post(f"{api_server}/api/gateway/heartbeat", json=hb_payload, timeout=4)
        assert hb_resp.status_code == 200
        assert hb_resp.json()["ok"] is True

        # Status check from frontend HUD
        status_resp = requests.get(f"{api_server}/api/relay/status?pairing_code=JR-275900", timeout=4)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["is_online"] is True
        assert status_data["connected"] is True
        assert status_data["device_name"] == "Samsung Galaxy S24"
        assert status_data["battery"] == "88%"
