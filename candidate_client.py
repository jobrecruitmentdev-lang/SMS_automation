#!/usr/bin/env python3
"""
Master Candidate & Jobs Client — Connects to Live JobRecruitment API
"""

import requests
import os

class CandidateClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url.rstrip('?')
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def fetch_admin_jobs(self, status="Active"):
        """Fetches all jobs from the 'Manage Jobs' tab with applicant counts."""
        try:
            params = {"action": "get_admin_jobs"}
            if status:
                params["status"] = status
            
            res = requests.get(self.api_url, headers=self.headers, params=params, timeout=12)
            res.raise_for_status()
            data = res.json()
            if data.get("success"):
                return data.get("jobs", [])
            return []
        except Exception as e:
            print(f"[Error] Failed to fetch jobs: {e}")
            return []

    def fetch_job_applicants(self, job_id, status_filter=None):
        """Fetches all applicants for a specific job_id with clean phone numbers."""
        try:
            params = {
                "action": "get_job_applicants_data",
                "job_id": job_id
            }
            if status_filter:
                params["status"] = status_filter
            
            res = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            res.raise_for_status()
            data = res.json()
            if data.get("success"):
                return data.get("cands", []), data.get("job", {})
            return [], {}
        except Exception as e:
            print(f"[Error] Failed to fetch job applicants for {job_id}: {e}")
            return [], {}

    def fetch_global_candidates(self, role=None, city=None, status=None, limit=100):
        """Fetches candidates matching global search filters."""
        try:
            params = {
                "action": "get_all_campaign_cands",
                "limit": limit
            }
            if role:
                params["role"] = role
            if city:
                params["city"] = city
            if status:
                params["status"] = status

            res = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            res.raise_for_status()
            data = res.json()
            if data.get("success"):
                return data.get("cands", []), data.get("total_fetched", 0)
            return [], 0
        except Exception as e:
            print(f"[Error] Failed to fetch candidates: {e}")
            return [], 0
