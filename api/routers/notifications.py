from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user

router = APIRouter()

class Notification(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    link: Optional[str] = None
    is_read: bool
    created_at: str
    created_by: Optional[int] = None

class NotificationCreate(BaseModel):
    user_id: Optional[int] = None
    title: str
    content: str
    link: Optional[str] = None

@router.get("")
def get_my_notifications(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    res = supabase.table("notifications").select("*, creator:users!notifications_created_by_fkey(full_name)").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    return res.data

@router.post("/{notif_id}/read")
def mark_as_read(notif_id: int, user: dict = Depends(get_current_user)):
    curr_user_id = user.get("user_id")
    print(f">>> DEBUG: Marking notif {notif_id} as read for user {curr_user_id}")
    res = supabase.table("notifications").update({"is_read": True}).eq("id", notif_id).eq("user_id", curr_user_id).execute()
    print(f">>> DEBUG: Result: {res.data}")
    return {"success": True}

@router.post("/read-all")
def mark_all_as_read(user: dict = Depends(get_current_user)):
    curr_user_id = user.get("user_id")
    print(f">>> DEBUG: Marking all read for user {curr_user_id}")
    res = supabase.table("notifications").update({"is_read": True}).eq("user_id", curr_user_id).execute()
    return {"success": True}

@router.delete("/{notif_id}")
def delete_notification(notif_id: int, user: dict = Depends(get_current_user)):
    curr_user_id = user.get("user_id")
    print(f">>> DEBUG: Deleting notif {notif_id} for user {curr_user_id}")
    res = supabase.table("notifications").delete().eq("id", notif_id).eq("user_id", curr_user_id).execute()
    return {"success": True}

@router.delete("")
def delete_all_notifications(user: dict = Depends(get_current_user)):
    curr_user_id = user.get("user_id")
    print(f">>> DEBUG: Deleting all notifications for user {curr_user_id}")
    res = supabase.table("notifications").delete().eq("user_id", curr_user_id).execute()
    return {"success": True}

@router.post("/test")
def send_test_notification(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    try:
        data = {
            "user_id": user_id,
            "title": "🔔 Thông báo thử nghiệm",
            "content": "Đây là thông báo được gửi từ hệ thống để kiểm tra tính năng. Nếu bạn thấy dòng này, hệ thống thông báo đã hoạt động!",
            "link": "/notifications",
            "is_read": False,
            "created_by": user_id
        }
        res = supabase.table("notifications").insert(data).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo thông báo: {str(e)}")

@router.post("")
def create_custom_notification(data: NotificationCreate, user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    curr_user_id = user.get("user_id")
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền tạo thông báo")
    
    try:
        if data.user_id:
            create_notification(data.user_id, data.title, data.content, data.link, created_by=curr_user_id)
        else:
            # Gửi cho tất cả người dùng
            users_res = supabase.table("users").select("id").execute()
            for u in users_res.data:
                create_notification(u["id"], data.title, data.content, data.link, created_by=curr_user_id)
        return {"success": True, "message": "Tạo thông báo thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

# Hàm helper để tạo thông báo từ phía server
def create_notification(user_id, title: str, content: str, link: str = None, created_by: int = None):
    try:
        # Ép kiểu user_id về string nếu là UUID
        data = {
            "user_id": str(user_id),
            "title": title,
            "content": content,
            "link": link,
            "is_read": False
        }
        if created_by is not None:
            data["created_by"] = created_by
            
        supabase.table("notifications").insert(data).execute()
        print(f">>> NOTIF: Created notification for user {user_id}")
    except Exception as e:
        print(f">>> ERROR creating notification for user {user_id}: {e}")
