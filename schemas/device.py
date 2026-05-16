from pydantic import BaseModel
from typing import Optional, List
from schemas.room import RoomSchema
from schemas.category import CategorySchema

class UserSchema(BaseModel):
    full_name: str

class DeviceUpdate(BaseModel):
    status: Optional[str] = None
    device_name: Optional[str] = None
    room_name: Optional[str] = None
    description: Optional[str] = None
    purchase_date: Optional[str] = None
    category: Optional[str] = None
    device_price: Optional[str] = None

class DeviceResponse(BaseModel):
    id: int
    room_id: Optional[int] = None
    device_name: str
    device_code: str
    status: str
    description: Optional[str] = None
    qr_url: Optional[str] = None
    barcode_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_inventory_at: Optional[str] = None
    purchase_date: Optional[str] = None
    image_url: Optional[str] = None
    rooms: RoomSchema
    categories: CategorySchema
    users: Optional[UserSchema] = None
    quantity: int = 1
    device_price: Optional[str] = None
    created_by: Optional[int] = None
    all_devices_detail: List[dict] = []

class RegisterDevice(BaseModel):
    device_name: str
    room_name: str
    category_name: str
    status: str
    description: Optional[str] = None
    purchase_date: Optional[str] = None
    device_price: Optional[str] = None
    quantity: Optional[int] = 1
