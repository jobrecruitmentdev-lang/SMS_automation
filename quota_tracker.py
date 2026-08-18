#!/usr/bin/env python3
"""
TRAI Compliance & Daily Quota Tracker
- Hard limit of 180 SMS/day
- Automatic midnight reset (00:00:00) with timestamp audit log
- Persistent local JSON ledger
"""

import json
import os
from datetime import datetime

class QuotaTracker:
    def __init__(self, limit=180, storage_file="quota_state.json"):
        self.limit = int(limit)
        self.storage_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), storage_file)
        self.state = self._load_state()

    def _get_today_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def _load_state(self):
        today = self._get_today_str()
        default_state = {
            "current_date": today,
            "sent_today": 0,
            "last_reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reset_history": []
        }

        if not os.path.exists(self.storage_file):
            self._save_state(default_state)
            return default_state

        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if midnight has passed
            if data.get("current_date") != today:
                reset_entry = {
                    "from_date": data.get("current_date"),
                    "to_date": today,
                    "final_count": data.get("sent_today", 0),
                    "reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "MIDNIGHT_RESET_SUCCESS"
                }
                data["current_date"] = today
                data["sent_today"] = 0
                data["last_reset_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history = data.get("reset_history", [])
                history.append(reset_entry)
                data["reset_history"] = history[-30:] # Keep last 30 days
                self._save_state(data)
            
            return data
        except Exception:
            self._save_state(default_state)
            return default_state

    def _save_state(self, data):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Warning] Failed to save quota state: {e}")

    def check_quota(self, requested_count=1):
        """
        Returns (can_send: bool, remaining: int, message: str)
        """
        # Ensure date check is fresh
        self.state = self._load_state()
        sent = self.state.get("sent_today", 0)
        remaining = max(0, self.limit - sent)

        if remaining <= 0:
            return False, 0, f"Daily TRAI limit ({self.limit} SMS/day) reached! Reset scheduled at midnight."
        
        if requested_count > remaining:
            return False, remaining, f"Requested {requested_count} exceeds remaining quota ({remaining}/{self.limit})."

        return True, remaining, f"Quota OK: {sent}/{self.limit} sent today ({remaining} remaining)."

    def record_sent(self, count=1):
        """Records a successful dispatch and increments the daily counter."""
        self.state = self._load_state()
        self.state["sent_today"] = self.state.get("sent_today", 0) + count
        self._save_state(self.state)
        return self.state["sent_today"], max(0, self.limit - self.state["sent_today"])

    def manual_reset(self):
        """Manual reset (e.g. if switching physical SIM card)."""
        today = self._get_today_str()
        reset_entry = {
            "from_date": today,
            "to_date": today,
            "final_count": self.state.get("sent_today", 0),
            "reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "MANUAL_SIM_RESET_OVERRIDE"
        }
        self.state["sent_today"] = 0
        self.state["last_reset_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = self.state.get("reset_history", [])
        history.append(reset_entry)
        self.state["reset_history"] = history[-30:]
        self._save_state(self.state)
        return True, "Quota manually reset to 0/180."
