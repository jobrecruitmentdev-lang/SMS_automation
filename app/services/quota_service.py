import os
import json
from datetime import datetime, date
from app.core.config import BASE_DIR, settings

class QuotaTracker:
    def __init__(self, limit=None, tracker_file=None):
        self.limit = limit if limit is not None else settings.DAILY_SMS_LIMIT
        self.tracker_file = tracker_file or os.path.join(BASE_DIR, "daily_quota.json")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.tracker_file):
            self._save_state({"date": str(date.today()), "sent_count": 0})

    def _load_state(self):
        self._ensure_file()
        try:
            with open(self.tracker_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") != str(date.today()):
                data = {"date": str(date.today()), "sent_count": 0}
                self._save_state(data)
            return data
        except Exception:
            return {"date": str(date.today()), "sent_count": 0}

    def _save_state(self, state):
        try:
            with open(self.tracker_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def get_status(self):
        state = self._load_state()
        sent = state.get("sent_count", 0)
        rem = max(0, self.limit - sent)
        return {
            "sent_today": sent,
            "daily_limit": self.limit,
            "remaining": rem,
            "quota_full": sent >= self.limit,
            "reset_time": "Midnight (00:00:00)"
        }

    def can_send(self):
        state = self._load_state()
        return state.get("sent_count", 0) < self.limit

    def record_sent(self):
        state = self._load_state()
        state["sent_count"] = state.get("sent_count", 0) + 1
        self._save_state(state)
        return self.limit - state["sent_count"]

    def reset_today(self):
        self._save_state({"date": str(date.today()), "sent_count": 0})

quota_service = QuotaTracker()
