from fastapi import APIRouter, Query
from app.models.dispatch import StartDispatchRequest, StopDispatchRequest, DispatchStatusResponse
from app.services.dispatch_service import dispatch_service

router = APIRouter(tags=["SMS Dispatch & Campaigns"])

@router.post("/api/start_dispatch")
def start_dispatch(req: StartDispatchRequest):
    return dispatch_service.start_campaign(req.dict())

@router.post("/api/stop_dispatch")
def stop_dispatch(req: StopDispatchRequest):
    return dispatch_service.stop_campaign(req.pairing_code or "JR-DEFAULT")

@router.get("/api/dispatch_status", response_model=DispatchStatusResponse)
def dispatch_status(pairing_code: str = Query("JR-DEFAULT")):
    return dispatch_service.get_status(pairing_code)
