import os
import json
import tempfile
import pytest
from quota_tracker import QuotaTracker

class TestQuotaTracker:
    @pytest.fixture
    def temp_tracker(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        tracker = QuotaTracker(limit=10, storage_file=path)
        yield tracker
        if os.path.exists(path):
            os.remove(path)

    def test_initial_quota_state(self, temp_tracker):
        can_send, remaining, msg = temp_tracker.check_quota(5)
        assert can_send is True
        assert remaining == 10
        assert temp_tracker.state.get("sent_today") == 0

    def test_record_sent_and_decrement(self, temp_tracker):
        temp_tracker.record_sent(4)
        can_send, remaining, _ = temp_tracker.check_quota(5)
        assert can_send is True
        assert remaining == 6

    def test_quota_exceeded_blocking(self, temp_tracker):
        temp_tracker.record_sent(10)
        can_send, remaining, msg = temp_tracker.check_quota(1)
        assert can_send is False
        assert remaining == 0
        assert "limit" in msg.lower()

    def test_manual_reset(self, temp_tracker):
        temp_tracker.record_sent(10)
        assert temp_tracker.state.get("sent_today") == 10
        temp_tracker.manual_reset()
        assert temp_tracker.state.get("sent_today") == 0
        can_send, remaining, _ = temp_tracker.check_quota(5)
        assert can_send is True
        assert remaining == 10
