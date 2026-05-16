from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from jose import jwt

from core.config import supabase, SECRET_KEY, ALGORITHM
from services.auth_service import get_current_user
from schemas.auth import LoginRequest, ChangePasswordRequest, ForgotPasswordRequest

router = APIRouter()

@router.post("/login")
def login(req: LoginRequest):
    res = supabase.table("users").select("*").eq("username", req.username).execute()
    user = res.data[0] if res.data else None

    if not user or user['password_hash'] != req.password:
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không đúng")

    token_data = {
        "user_id": user['id'],
        "role": user['role'],
        "room_id": user.get('room_id'), 
        "exp": datetime.utcnow() + timedelta(days=1)
    }
    
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user['role'],
        "full_name": user['full_name']
    }

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    # 1. Tìm user
    res = supabase.table("users").select("id, full_name").eq("username", req.username).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Tên đăng nhập không tồn tại")
    
    user = res.data[0]

    # 2. Tạo thông báo cho Admin
    try:
        notif_content = f"Người dùng {user['full_name']} (@{req.username}) đã gửi yêu cầu đặt lại mật khẩu."
        supabase.table("notifications").insert({
            "user_id": "8d6e355c-091a-4c28-98e3-f09c6474831a", # ID của Admin (hoặc lấy ID có role admin đầu tiên)
            "content": notif_content,
            "created_at": datetime.utcnow().isoformat(),
            "status": "unread"
        }).execute()
        
        return {"message": "Yêu cầu khôi phục mật khẩu đã được gửi tới Quản trị viên hệ thống."}
    except Exception as e:
        # Nếu lỗi (ví dụ không tìm thấy bảng notifications), vẫn trả về thông báo để user biết hướng xử lý
        return {"message": "Vui lòng liên hệ trực tiếp với Quản trị viên để được cấp lại mật khẩu."}

@router.put("/password")
def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    try:
        res = supabase.table("users").select("password_hash").eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
            
        current_password_hash = res.data[0]['password_hash']
        
        if current_password_hash != req.old_password:
            raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")

        update_res = supabase.table("users").update({"password_hash": req.new_password}).eq("id", user_id).execute()
        
        if update_res.data:
            return {"message": "Đổi mật khẩu thành công"}
        else:
            raise HTTPException(status_code=500, detail="Cập nhật mật khẩu thất bại")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
