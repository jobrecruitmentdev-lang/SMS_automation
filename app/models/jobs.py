from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AdminJobModel(BaseModel):
    id: str
    title: str
    company_name: Optional[str] = ""
    location: Optional[str] = ""
    status: Optional[str] = "active"

class QuotaModel(BaseModel):
    sent_today: int
    daily_limit: int
    remaining: int
    quota_full: bool
    reset_time: str
