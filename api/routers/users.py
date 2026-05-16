from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class UserCreate(BaseModel):
    full_name: str
    username: str
    password_hash: str
    role: str
    room_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    room_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

@router.get("/me")
def get_my_profile(user: dict = Depends(get_current_user)):
    res = supabase.table("users").select("id, full_name, username, role, room_id, phone, email, created_at").eq("id", user.get("user_id")).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin")
    return res.data[0]

@router.put("/me/update")
def update_my_profile(req: UserUpdate, user: dict = Depends(get_current_user)):
    try:
        # Chỉ cho phép cập nhật một số trường
        update_data = {k: v for k, v in req.dict().items() if v is not None and k in ["full_name", "phone", "email"]}
        res = supabase.table("users").update(update_data).eq("id", user.get("user_id")).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/me/change-password")
def change_password(req: PasswordChange, user: dict = Depends(get_current_user)):
    # 1. Kiểm tra mật khẩu cũ
    user_res = supabase.table("users").select("password_hash").eq("id", user.get("user_id")).execute()
    if not user_res.data or user_res.data[0]["password_hash"] != req.old_password:
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
    
    # 2. Cập nhật mật khẩu mới
    try:
        supabase.table("users").update({"password_hash": req.new_password}).eq("id", user.get("user_id")).execute()
        return {"message": "Đổi mật khẩu thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("")
def get_users(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    res = supabase.table("users").select("id, full_name, username, role, room_id, phone, email, created_at, rooms(room_name)").execute()
    
    # Flatten rooms(room_name)
    for u in res.data:
        if u.get("rooms"):
            u["room_name"] = u["rooms"].get("room_name")
        else:
            u["room_name"] = "Tất cả"
            
    return res.data

@router.post("")
def create_user(req: UserCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        res = supabase.table("users").insert(req.dict()).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Không thể tạo người dùng. Có thể username đã tồn tại.")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{user_id}")
def update_user(user_id: int, req: UserUpdate, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        update_data = {k: v for k, v in req.dict().items() if v is not None}
        res = supabase.table("users").update(update_data).eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng để cập nhật")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{user_id}/reset-password")
def reset_user_password(user_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        # Đặt lại mật khẩu mặc định là 123456
        res = supabase.table("users").update({"password_hash": "123456"}).eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        return {"message": "Đã đặt lại mật khẩu về 123456"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}")
def delete_user(user_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        res = supabase.table("users").delete().eq("id", user_id).execute()
        return {"message": "Đã xóa thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
