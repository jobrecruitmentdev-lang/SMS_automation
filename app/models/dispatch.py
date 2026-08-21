from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class StartDispatchRequest(BaseModel):
    job_id: str
    template_body: str
    candidates: List[Dict[str, Any]]
    sim_slot: Optional[int] = 0
    delay_seconds: Optional[int] = 5
    pairing_code: Optional[str] = "JR-DEFAULT"
    auto_spin: Optional[bool] = False

class StopDispatchRequest(BaseModel):
    pairing_code: Optional[str] = "JR-DEFAULT"

class DispatchStatusResponse(BaseModel):
    is_running: bool
    current_index: int
    total: int
    sent_count: int
    failed_count: int
    active_job_id: Optional[str] = None
    logs: List[str]
