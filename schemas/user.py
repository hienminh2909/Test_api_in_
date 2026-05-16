from pydantic import BaseModel
from typing import Optional

class UserSchema(BaseModel):
    id: int
    full_name: str
    username: str
    role: str
    room_id: Optional[int] = None
