from fastapi import APIRouter, Query
from app.services.job_service import candidate_service
from app.services.quota_service import quota_service

router = APIRouter(tags=["Hostinger Jobs & Quota"])

@router.get("/api/jobs")
def get_jobs(status: str = Query("")):
    jobs = candidate_service.fetch_admin_jobs(status)
    return {"ok": True, "jobs": jobs}

@router.get("/api/applicants")
def get_applicants(job_id: str = Query(...), status: str = Query(None)):
    applicants = candidate_service.fetch_job_applicants(job_id, status)
    return {"ok": True, "applicants": applicants}

@router.get("/api/filter_options")
def get_filter_options():
    filters = candidate_service.fetch_filter_options()
    return {"ok": True, "filters": filters}

@router.get("/api/quota")
def get_quota():
    return quota_service.get_status()

@router.post("/api/reset_quota")
def reset_quota():
    quota_service.reset_today()
    return {"ok": True, "message": "Daily quota reset successfully.", "status": quota_service.get_status()}
