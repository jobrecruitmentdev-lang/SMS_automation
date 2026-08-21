from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AiEnhanceRequest(BaseModel):
    template: str
    tone: Optional[str] = "professional"
    job_title: Optional[str] = ""
    company: Optional[str] = ""
    provider: Optional[str] = "groq"

class AiEnhanceResponse(BaseModel):
    ok: bool
    enhanced_text: Optional[str] = None
    character_count: Optional[int] = 0
    provider_used: Optional[str] = None
    error: Optional[str] = None
