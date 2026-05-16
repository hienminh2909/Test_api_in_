from pydantic import BaseModel
from typing import Optional

class RoomSchema(BaseModel):
    id: Optional[int] = None
    room_name: str
