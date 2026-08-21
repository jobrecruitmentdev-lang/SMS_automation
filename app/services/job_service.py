import requests
from app.core.config import settings
from app.core.state import write_log

class CandidateService:
    def __init__(self, api_url=None, api_key=None):
        self.api_url = (api_url or settings.WORKER_API_URL).rstrip('?')
        api_k = api_key or settings.WORKER_API_KEY
        self.headers = {"Authorization": f"Bearer {api_k}"} if api_k else {}

    def fetch_admin_jobs(self, status=""):
        try:
            params = {"action": "get_admin_jobs"}
            if status:
                params["status"] = status
            r = requests.get(self.api_url, headers=self.headers, params=params, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("jobs", [])
        except Exception as e:
            write_log(f"CandidateService fetch_admin_jobs error: {e}")
        return []

    def fetch_job_applicants(self, job_id, status_filter=None):
        try:
            params = {"action": "get_job_applicants_data", "job_id": job_id}
            if status_filter:
                params["status"] = status_filter
            r = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("data", {}).get("applicants", [])
        except Exception as e:
            write_log(f"CandidateService fetch_job_applicants error: {e}")
        return []

    def fetch_filter_options(self):
        try:
            r = requests.get(self.api_url, headers=self.headers, params={"action": "get_filter_options"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("data", {})
        except Exception as e:
            write_log(f"CandidateService fetch_filter_options error: {e}")
        return {}

candidate_service = CandidateService()
