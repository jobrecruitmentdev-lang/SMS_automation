import os
import tempfile
import pytest
from app.services.quota_service import QuotaTracker

class TestQuotaTracker:
    @pytest.fixture
    def temp_tracker(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        tracker = QuotaTracker(limit=10, tracker_file=path)
        yield tracker
        if os.path.exists(path):
            os.remove(path)

    def test_initial_quota_state(self, temp_tracker):
        assert temp_tracker.can_send() is True
        status = temp_tracker.get_status()
        assert status["remaining"] == 10
        assert status["sent_today"] == 0

    def test_record_sent_and_decrement(self, temp_tracker):
        for _ in range(4):
            temp_tracker.record_sent()
        assert temp_tracker.can_send() is True
        status = temp_tracker.get_status()
        assert status["remaining"] == 6

    def test_quota_exceeded_blocking(self, temp_tracker):
        for _ in range(10):
            temp_tracker.record_sent()
        assert temp_tracker.can_send() is False
        status = temp_tracker.get_status()
        assert status["remaining"] == 0
        assert status["quota_full"] is True

    def test_manual_reset(self, temp_tracker):
        for _ in range(10):
            temp_tracker.record_sent()
        assert temp_tracker.can_send() is False
        temp_tracker.reset_today()
        assert temp_tracker.can_send() is True
        assert temp_tracker.get_status()["remaining"] == 10
