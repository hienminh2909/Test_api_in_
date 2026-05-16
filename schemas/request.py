from pydantic import BaseModel
from typing import Optional, Any

class RequestCreate(BaseModel):
    device_id: int
    description: str
    status_device: Optional[str] = None
    request_type: Optional[str] = "REPORT" # REPORT, UPDATE, DELETE
    update_payload: Optional[Any] = None # Dữ liệu mới nếu là UPDATE
