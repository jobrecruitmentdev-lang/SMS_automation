from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class DeviceRegisterRequest(BaseModel):
    pairing_code: Optional[str] = None
    code: Optional[str] = None
    login_code: Optional[str] = None
    device_id: Optional[str] = None
    id: Optional[str] = None
    device_name: Optional[str] = None
    name: Optional[str] = None
    carrier: Optional[str] = None
    battery: Optional[str] = None
    android_version: Optional[str] = None
    sim_slot: Optional[int] = 0

class DeviceHeartbeatRequest(BaseModel):
    pairing_code: Optional[str] = None
    device_id: Optional[str] = None
    battery: Optional[str] = "100%"
    carrier: Optional[str] = "Unknown"
    is_screen_on: Optional[bool] = True
    screen_state_text: Optional[str] = "Active"
    signal_level: Optional[int] = 4
    network_type: Optional[str] = "LTE"
    android_version: Optional[str] = "Android"

class DeliveryReportRequest(BaseModel):
    pairing_code: Optional[str] = None
    code: Optional[str] = None
    job_id: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = "SENT"
    sim_slot: Optional[int] = 0
    error: Optional[str] = None
    is_finished: Optional[bool] = False

class QueueJobRequest(BaseModel):
    pairing_code: str
    phone: str
    message: str
    name: Optional[str] = ""
    sim_slot: Optional[int] = 0
