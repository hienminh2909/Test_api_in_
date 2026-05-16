from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user
from schemas.report import ReportCreate
from datetime import datetime

router = APIRouter()

@router.post("")
def create_report(req: ReportCreate, user: dict = Depends(get_current_user)):
    try:
        report_data = req.dict()
        report_data["reported_at"] = datetime.utcnow().isoformat()
        res = supabase.table("report_logs").insert(report_data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("")
def get_all_reports(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xem toàn bộ báo hỏng")
    res = supabase.table("report_logs").select("*, devices(device_name, device_code), users:created_by(full_name), resolver:resolved_by(full_name)").order("reported_at", desc=True).execute()
    return res.data

@router.get("/device/{device_id}")
def get_reports_by_device(device_id: int, user: dict = Depends(get_current_user)):
    res = supabase.table("report_logs").select("*").eq("device_id", device_id).order("reported_at", desc=True).execute()
    return res.data
