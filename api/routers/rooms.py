from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class RoomCreate(BaseModel):
    room_name: str
    description: Optional[str] = None

@router.get("")
def get_rooms(user: dict = Depends(get_current_user)):
    role = user.get("role")
    user_room_id = user.get("room_id")
    print(f">>> API ROOMS: [GET] Fetching rooms for User: {user.get('user_id')} (Role: {role})")
    
    query = supabase.table("rooms").select("*").order("room_name")
    
    # Nếu là teacher, chỉ lấy phòng được giao quản lý
    if role == "teacher":
        if user_room_id:
            query = query.eq("id", user_room_id)
        else:
            return [] # Teacher không có phòng quản lý thì không thấy phòng nào
            
    rooms_res = query.execute()
    rooms = rooms_res.data
    
    # Lấy số lượng thiết bị cho mỗi phòng
    devices_res = supabase.table("devices").select("room_id").execute()
    device_data = devices_res.data
    
    # Đếm thủ công
    count_map = {}
    for d in device_data:
        r_id = d.get("room_id")
        if r_id:
            count_map[r_id] = count_map.get(r_id, 0) + 1
            
    for room in rooms:
        room["device_count"] = count_map.get(room["id"], 0)
        
    return rooms

@router.post("")
def create_room(req: RoomCreate, user: dict = Depends(get_current_user)):
    print(f">>> API ROOMS: [POST] Creating room: {req.room_name}")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền tạo phòng")
    
    try:
        res = supabase.table("rooms").insert({"room_name": req.room_name, "description": req.description}).execute()
        if res.data:
            print(f">>> API ROOMS: Room created ID: {res.data[0].get('id')}")
            return res.data[0]
        raise HTTPException(status_code=400, detail="Không thể tạo phòng")
    except Exception as e:
        print(f">>> API ROOMS: Error - {str(e)}")
        if "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="Tên phòng này đã tồn tại")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{room_id}")
def update_room(room_id: int, req: RoomCreate, user: dict = Depends(get_current_user)):
    print(f">>> API ROOMS: [PUT] Updating room ID: {room_id}")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền sửa phòng")
    
    try:
        res = supabase.table("rooms").update({"room_name": req.room_name, "description": req.description}).eq("id", room_id).execute()
        if res.data:
            return res.data[0]
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng")
    except Exception as e:
        if "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="Tên phòng này đã tồn tại")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{room_id}")
def delete_room(room_id: int, user: dict = Depends(get_current_user)):
    print(f">>> API ROOMS: [DELETE] Deleting room ID: {room_id}")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa phòng")
    
    try:
        # Kiểm tra xem có thiết bị nào trong phòng không
        check_devices = supabase.table("devices").select("id").eq("room_id", room_id).limit(1).execute()
        if check_devices.data:
            raise HTTPException(status_code=400, detail="Không thể xóa phòng đang có thiết bị. Vui lòng di chuyển thiết bị trước.")
            
        res = supabase.table("rooms").delete().eq("id", room_id).execute()
        return {"message": "Đã xóa phòng thành công"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
