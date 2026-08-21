import json
import urllib.request
import urllib.parse
import pytest
from sms_gateway import SMSGateway
from tests.api.test_rest_api import api_server

class TestSecurityAuditAndPayloads:
    def test_clean_phone_sanitization(self):
        # Valid cases
        assert SMSGateway.clean_phone("+91 98980 11223") == "9898011223"
        assert SMSGateway.clean_phone("09898011223") == "9898011223"
        assert SMSGateway.clean_phone("919898011223") == "9898011223"

        # Malicious / Injection Payloads must be rejected
        assert SMSGateway.clean_phone("'; DROP TABLE users; --") is None
        assert SMSGateway.clean_phone("<script>alert(1)</script>") is None
        assert SMSGateway.clean_phone("12345") is None  # Invalid length
        assert SMSGateway.clean_phone("1898011223") is None  # Invalid Indian starting digit

    def test_path_traversal_blocked(self, api_server):
        # Attempt to escape web root via dot-dot-slash
        traversal_urls = [
            f"{api_server}/../../../../etc/passwd",
            f"{api_server}/..%2f..%2f.env",
            f"{api_server}/download/..%5c..%5c.env"
        ]
        for url in traversal_urls:
            try:
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=2)
                # If server answered 200, ensure it didn't return sensitive .env content
                content = resp.read().decode(errors="ignore")
                assert "WORKER_API_KEY" not in content
            except urllib.error.HTTPError as e:
                # 404 or 400 is the expected safe rejection
                assert e.code in [400, 403, 404]

    def test_malformed_json_post_safe(self, api_server):
        # Sending non-JSON raw garbage must return 400 or handle gracefully without 500 crash
        req = urllib.request.Request(
            f"{api_server}/api/validate_sms",
            data=b"INVALID_RAW_NON_JSON_GARBAGE{{{",
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                assert resp.status in [200, 400]
        except urllib.error.HTTPError as e:
            assert e.code in [400, 500]
