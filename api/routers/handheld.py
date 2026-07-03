from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import re
from typing import Optional

from core.config import supabase
from core.cache import dashboard_cache

router = APIRouter()

# --- UTILS: Loại bỏ dấu tiếng Việt cho ESP32 ---
def remove_vietnamese_accent(text: str) -> str:
    if not text:
        return ""
    patterns = {
        '[àáảãạăằắẳẵặâầấẩẫậ]': 'a',
        '[èéẻẽẹêềếểễệ]': 'e',
        '[ìíỉĩị]': 'i',
        '[òóỏõọôồốổỗộơờớởỡợ]': 'o',
        '[ùúủũụưừứửữự]': 'u',
        '[ỳýỷỹỵ]': 'y',
        '[đ]': 'd',
        '[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ]': 'A',
        '[ÈÉỞẼẸÊỀẾỂỄỆ]': 'E',
        '[ÌÍỈĨỊ]': 'I',
        '[ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ]': 'O',
        '[ÙÚỦŨỤƯỪỨỬỮỰ]': 'U',
        '[ỲÝỶỸỴ]': 'Y',
        '[Đ]': 'D'
    }
    for pattern, replacement in patterns.items():
        text = re.sub(pattern, replacement, text)
    return text

# --- MODELS ---
class HandheldScanRequest(BaseModel):
    device_code: str
    handheld_name: str

class HandheldReportRequest(BaseModel):
    device_code: str
    status_device: str  # Ví dụ: "Đã hỏng" hoặc "Cần bảo trì"
    request_type: str
    description: str
    handheld_name: str

# --- API: Kiểm kê thiết bị (Scan) ---
@router.post("/scan")
async def scan_and_log(req: HandheldScanRequest):
    """
    Dành cho ESP32: Quét mã QR/Barcode và ghi nhận kiểm kê.
    Trả về dữ liệu tối giản: n (name), r (room), s (status).
    """
    try:
        res = supabase.table("devices").select("id, device_name, status, rooms(room_name)")\
            .eq("device_code", req.device_code).execute()
        
        if not res.data:
            return {"success": False, "message": "Unknow Device"}    
        device = res.data[0]
        

        device_name_safe = remove_vietnamese_accent(device["device_name"])
        status_safe = remove_vietnamese_accent(device["status"])
        room_name = device["rooms"]["room_name"] if device.get("rooms") else "N/A"
        room_name_safe = remove_vietnamese_accent(room_name)


        res_user = supabase.table("users").select("id").eq("handheld_name", req.handheld_name).execute()
        user_id = res_user.data[0]['id'] if res_user.data else None


        log_entry = {
            "device_id": device["id"],
            "resolved_by": user_id,
            "inventory_at": datetime.utcnow().isoformat(),
            "status_at_scan": device["status"]
        }
        supabase.table("inventory_logs").insert(log_entry).execute()
        dashboard_cache.clear()


        supabase.table("devices").update({"last_inventory_at": datetime.utcnow().isoformat()})\
            .eq("id", device["id"]).execute()


        return {
        "success": True,
        "message": "Kiem ke thanh cong",
        "n": device_name_safe,
        "r": room_name_safe,
        "s": status_safe
        }

    except Exception as e:
        print(f"Loi: {e}")
        return {"success": False, "message": "Loi may chu"}

# --- API: Báo cáo sự cố (Report) ---
@router.post("/report")
async def report_device_issue(req: HandheldReportRequest):
    """
    Dành cho ESP32: Báo cáo hỏng hóc hoặc yêu cầu bảo trì.
    """
    try:
        res_device = supabase.table("devices").select("id, device_name").eq("device_code", req.device_code).execute()
        if not res_device.data:
            return {"success": False, "message": "Unknow Device"}
        
        device_id = res_device.data[0]['id']
        

        res_user = supabase.table("users").select("id").eq("handheld_name", req.handheld_name).execute()
        
        # if not res_user.data:

        #     raise HTTPException(status_code=404, detail="Handheld User Not Found")
        
        user_id = res_user.data[0]['id']


        report_data = {
            "created_by": user_id,
            "device_id": device_id,
            "status_device": req.status_device,
            "description": req.description,
            "request_type": req.request_type,
            "status_resolve": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("requests").insert(report_data).execute()

        return {"success": True, "message": "REPORT SUCCESS!"}
    except Exception as e:
        print(f"Loi: {e}")
        return {"success": False, "message": "Loi may chu"}
