from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from pydantic import BaseModel

from core.config import supabase
from services.auth_service import get_current_user
from core.cache import dashboard_cache

router = APIRouter()

@router.get("/logs")
def get_inventory_logs(user: dict = Depends(get_current_user)):
    role = user.get("role")
    user_room_id = user.get("room_id")
    
    res = supabase.table("inventory_logs").select("*, devices(device_name, device_code, room_id, rooms(room_name)), users(full_name)").order("inventory_at", desc=True).execute()
    
    logs = res.data
    if role == "teacher" and user_room_id:
        logs = [log for log in logs if log.get("devices") and log["devices"].get("room_id") == user_room_id]
        
    return logs

@router.get("/rooms-progress")
def get_rooms_progress(
    month: int = None,
    year: int = None,
    user: dict = Depends(get_current_user)
):
    try:
        role = user.get("role")
        user_room_id = user.get("room_id")
        
        now = datetime.utcnow()
        if not month: month = now.month
        if not year: year = now.year

        import calendar
        _, last_day = calendar.monthrange(year, month)
        first_day_of_month = f"{year}-{month:02d}-01T00:00:00"
        end_day_of_month = f"{year}-{month:02d}-{last_day}T23:59:59"

        query = supabase.table("rooms").select("id, room_name")
        if role == "teacher" and user_room_id:
            query = query.eq("id", user_room_id)
        
        rooms_res = query.execute()
        rooms = rooms_res.data

        results = []
        for room in rooms:
            total_res = supabase.table("devices").select("id", count="exact").eq("room_id", room['id']).execute()
            total_count = total_res.count if total_res.count is not None else 0

            checked_res = supabase.table("devices").select("id", count="exact") \
                .eq("room_id", room['id']) \
                .gte("last_inventory_at", first_day_of_month) \
                .lte("last_inventory_at", end_day_of_month).execute()
            checked_count = checked_res.count if checked_res.count is not None else 0

            progress = int((checked_count / total_count * 100)) if total_count > 0 else 0

            results.append({
                "room_id": room['id'],
                "room_name": room['room_name'],
                "total": total_count,
                "checked": checked_count,
                "progress": progress
            })

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rooms/{room_id}/details")
def get_inventory_details(
    room_id: int, 
    month: int, 
    year: int, 
    user: dict = Depends(get_current_user)
):
    try:
        import calendar
        _, last_day = calendar.monthrange(year, month)
        start_date = f"{year}-{month:02d}-01T00:00:00"
        end_date = f"{year}-{month:02d}-{last_day}T23:59:59"

        res = supabase.table("devices").select("*").eq("room_id", room_id).execute()
        devices = res.data

        results = []
        for d in devices:
            last_check = d.get("last_inventory_at")
            
            is_checked = False
            if last_check and start_date <= last_check <= end_date:
                is_checked = True
            
            results.append({
                "id": d["id"],
                "device_name": d["device_name"],
                "device_code": d.get("device_code", "N/A"),
                "status": d["status"],
                "is_checked": is_checked,
                "last_check": last_check
            })
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class InventoryScanRequest(BaseModel):
    device_id: int
    status_at_scan: str

@router.post("/scan")
def scan_inventory(req: InventoryScanRequest, user: dict = Depends(get_current_user)):
    try:
        now = datetime.utcnow().isoformat()
        

        supabase.table("devices").update({"last_inventory_at": now}).eq("id", req.device_id).execute()
        

        log_data = {
            "device_id": req.device_id,
            "status_at_scan": req.status_at_scan,
            "inventory_at": now,
            "resolved_by": user.get("user_id")
        }
        res = supabase.table("inventory_logs").insert(log_data).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Không thể ghi log kiểm kê")
            
        dashboard_cache.clear()
        return {"message": "Ghi nhận kiểm kê thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/logs/{log_id}")
def delete_inventory_log(log_id: int, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa lịch sử kiểm kê")
    try:
        res = supabase.table("inventory_logs").delete().eq("id", log_id).execute()
        dashboard_cache.clear()
        return {"message": "Xóa nhật ký thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/logs")
def clear_all_inventory_logs(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa lịch sử kiểm kê")
    try:
        res = supabase.table("inventory_logs").delete().neq("id", 0).execute()
        dashboard_cache.clear()
        return {"message": "Đã xóa toàn bộ nhật ký thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
