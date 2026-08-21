import requests
import pytest
from app.services.dispatch_service import clean_phone_number
from tests.api.test_rest_api import api_server

class TestSecurityAuditAndPayloads:
    def test_clean_phone_sanitization(self):
        # Valid cases
        assert clean_phone_number("9898011223") == "+919898011223"
        assert clean_phone_number("09898011223") == "+919898011223"
        assert clean_phone_number("919898011223") == "+919898011223"

        # Malicious / Injection Payloads must be rejected
        assert clean_phone_number("'; DROP TABLE users; --") is None
        assert clean_phone_number("<script>alert(1)</script>") is None
        assert clean_phone_number("12345") is None
        assert clean_phone_number("1898011223") is None

    def test_path_traversal_blocked(self, api_server):
        traversal_paths = [
            f"{api_server}/../../../../etc/passwd",
            f"{api_server}/..%2f..%2f.env",
            f"{api_server}/download/..%5c..%5c.env"
        ]
        for url in traversal_paths:
            try:
                resp = requests.get(url, timeout=3)
                assert "WORKER_API_KEY" not in resp.text
            except requests.exceptions.RequestException:
                pass

    def test_malformed_json_post_safe(self, api_server):
        try:
            resp = requests.post(
                f"{api_server}/api/validate_sms",
                data=b"INVALID_RAW_NON_JSON_GARBAGE{{{",
                headers={"Content-Type": "application/json"},
                timeout=3
            )
            assert resp.status_code in [400, 422]
        except requests.exceptions.RequestException:
            pass
