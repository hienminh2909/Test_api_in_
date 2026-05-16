from pydantic import BaseModel
from typing import Optional

class ReportCreate(BaseModel):
    device_id: int
    status: str
    note: Optional[str] = None
    description: Optional[str] = None
    handheld_name: Optional[str] = None
