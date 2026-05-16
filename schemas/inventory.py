from pydantic import BaseModel
from typing import Optional

class InventoryLogSchema(BaseModel):
    id: int
    device_id: int
    status_at_scan: Optional[str] = None
    inventory_at: Optional[str] = None
    handheld_name: Optional[str] = None
