from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user
from schemas.request import RequestCreate
from datetime import datetime
from api.routers.notifications import create_notification

router = APIRouter()

@router.post("")
def create_request(req: RequestCreate, user: dict = Depends(get_current_user)):
    try:
        request_data = {
            "device_id": req.device_id,
            "created_by": user.get("user_id"),
            "description": req.description,
            "status_device": req.status_device,
            "status_resolve": "pending",
            "request_type": req.request_type,
            "update_payload": req.update_payload,
            "created_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("requests").insert(request_data).execute()
        
        if res.data:
            # Lấy thông tin người gửi để hiện tên trong thông báo
            sender_info = supabase.table("users").select("full_name, username").eq("id", user.get("user_id")).execute()
            sender_name = sender_info.data[0].get("full_name") or user.get("username") or "Người dùng"
            
            # THÔNG BÁO CHO ADMIN
            admins = supabase.table("users").select("id").in_("role", ["admin", "Admin"]).execute()
            notif_link = "/requests?tab=advanced" if req.request_type != "REPORT" else "/requests"
            for admin in admins.data:
                create_notification(
                    user_id=admin["id"],
                    title="Yêu cầu mới cần phê duyệt",
                    content=f"Người dùng {sender_name} vừa gửi yêu cầu {req.request_type} cho thiết bị ID: {req.device_id}",
                    link=notif_link
                )
        
        return res.data[0] if res.data else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("")
def get_all_requests(status: str = None, user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xem toàn bộ yêu cầu")
    
    query = supabase.table("requests").select("*, devices(device_name, device_code, room_id, rooms(room_name)), users!requests_created_by_fkey(full_name), resolver:users!requests_resolved_by_fkey(full_name)")
    
    if status == "pending":
        query = query.or_("status_resolve.is.null,status_resolve.eq.pending")
    elif status == "resolved" or status == "approved":
        query = query.eq("status_resolve", "approved")
    elif status == "rejected":
        query = query.eq("status_resolve", "rejected")
        
    res = query.order("created_at", desc=True).execute()
    return res.data

@router.get("/me")
def get_my_requests(user: dict = Depends(get_current_user)):
    res = supabase.table("requests").select("*, devices(device_name, device_code)").eq("created_by", user.get("user_id")).order("created_at", desc=True).execute()
    return res.data

@router.put("/{request_id}/resolve")
def resolve_request(request_id: int, status: str, user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xử lý yêu cầu")
    
    update_resolve_data = {
        "status_resolve": status,
        "resolved_by": user.get("user_id"),
        "resolved_at": datetime.utcnow().isoformat()
    }
    
    # Lấy thông tin yêu cầu hiện tại để lấy ID người gửi
    request_info = supabase.table("requests").select("*, devices(device_name)").eq("id", request_id).execute()
    
    if not request_info.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
        
    req = request_info.data[0]
    sender_id = req["created_by"]
    device_name = req.get("devices", {}).get("device_name", "Thiết bị")
    req_type_label = "Báo hỏng" if req.get("request_type") == "REPORT" else "Sửa đổi/Xóa"

    if status == "approved":
        dev_id = req["device_id"]
        req_type = req.get("request_type", "REPORT")
        
        if req_type == "DELETE":
            # 1. Ngắt kết nối với thiết bị để tránh bị xóa lan truyền (Cascade Delete)
            update_resolve_data["device_id"] = None
            supabase.table("requests").update(update_resolve_data).eq("id", request_id).execute()
            
            # Tiến hành xóa thiết bị
            supabase.table("devices").delete().eq("id", dev_id).execute()
        elif req_type == "UPDATE":
            payload = req.get("update_payload")
            if payload:
                valid_fields = ["device_name", "device_code", "room_id", "status", "category_id", "description", "device_price"]
                filtered_payload = {k: v for k, v in payload.items() if k in valid_fields}
                supabase.table("devices").update(filtered_payload).eq("id", dev_id).execute()
        else: # REPORT
            new_status = req.get("status_device")
            if new_status and new_status != "pending":
                supabase.table("devices").update({"status": new_status}).eq("id", dev_id).execute()
    # THÔNG BÁO CHO NGƯỜI GỬI
    status_label = "PHÊ DUYỆT" if status == "approved" else "TỪ CHỐI"
    create_notification(
        user_id=sender_id,
        title=f"Yêu cầu của bạn đã được {status_label}",
        content=f"Admin đã {status_label.lower()} yêu cầu {req_type_label} của bạn cho thiết bị: {device_name}",
        link="/requests"
    )

    res = supabase.table("requests").update(update_resolve_data).eq("id", request_id).execute()
    return res.data[0] if res.data else None

@router.delete("/{request_id}")
def delete_request(request_id: int, user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa yêu cầu")
    try:
        res = supabase.table("requests").delete().eq("id", request_id).execute()
        return {"message": "Xóa yêu cầu thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("")
def clear_all_requests(user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa yêu cầu")
    try:
        res = supabase.table("requests").delete().neq("id", 0).execute()
        return {"message": "Đã xóa toàn bộ yêu cầu thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
