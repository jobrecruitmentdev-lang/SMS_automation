from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class ValidateSmsRequest(BaseModel):
    text: str
    seed: Optional[int] = 0

class SmsEncodingMetrics(BaseModel):
    encoding: str
    length: int
    segments: int
    char_limit_single: int
    char_limit_multi: int
    chars_remaining_in_segment: int
    is_unicode: bool
    spun_preview: str

class CloudTemplateModel(BaseModel):
    id: Optional[str] = None
    title: str
    template_body: str
    category: Optional[str] = "recruitment"
    visibility: Optional[str] = "public"
    user_id: Optional[str] = None
