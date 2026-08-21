import os
import json
import time
import socket
import threading
import urllib.request
import urllib.parse
import pytest
from http.server import HTTPServer
from web_ui import StudioHTTPHandler

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def api_server():
    port = get_free_port()
    server = HTTPServer(("127.0.0.1", port), StudioHTTPHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.3)
    yield base_url
    server.shutdown()

class TestStudioRESTApi:
    def test_get_quota_endpoint(self, api_server):
        req = urllib.request.Request(f"{api_server}/api/quota")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert "sent_today" in data
            assert "limit" in data

    def test_post_validate_sms_endpoint(self, api_server):
        payload = json.dumps({"text": "Hello {name}, visit https://jobrecruitment.in", "seed": 0}).encode()
        req = urllib.request.Request(
            f"{api_server}/api/validate_sms",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["encoding"] == "GSM-7 (Standard)"
            assert data["is_unicode"] is False
            assert "spun_preview" in data

    def test_gateway_register_and_heartbeat(self, api_server):
        # 1. Register Mobile Device
        reg_payload = json.dumps({
            "pairing_code": "JR-TEST99",
            "device_name": "Test Galaxy S23",
            "carrier": "Jio True5G",
            "battery": "95%",
            "sim_slot": 0
        }).encode()
        req = urllib.request.Request(
            f"{api_server}/api/gateway/register",
            data=reg_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["ok"] is True
            assert "token" in data

        # 2. Poll for Jobs
        poll_req = urllib.request.Request(f"{api_server}/api/gateway/poll?pairing_code=JR-TEST99")
        with urllib.request.urlopen(poll_req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert "has_job" in data

    def test_download_apk_route(self, api_server):
        req = urllib.request.Request(f"{api_server}/download/JobRecruitment-Gateway.apk")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "application/vnd.android.package-archive"
            body = resp.read()
            assert len(body) > 1000  # Confirms non-empty binary
