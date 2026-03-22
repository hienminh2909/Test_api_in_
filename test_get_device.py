from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from jose import jwt, JWTError
from datetime import datetime, timedelta

from pydantic import BaseModel
from typing import List, Optional

import os
import uvicorn

# --- 1. CẤU HÌNH HỆ THỐNG ---
SUPABASE_URL = "https://bcrztgtuoiexafijgtvw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJjcnp0Z3R1b2lleGFmaWpndHZ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNTg2NTgsImV4cCI6MjA4ODYzNDY1OH0.OWv0Ure8c1tth87oMtRN--Z_YFQKAQ7mphQjD9uDQis"
SECRET_KEY = "HIEN_PRO_SECRET_KEY"  # Chìa khóa để ký Token
ALGORITHM = "HS256"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()




# --- 2. MODEL DỮ LIỆU ---
class LoginRequest(BaseModel):
    username: str
    password: str

# --- 3. HÀM KIỂM TRA TOKEN (SECURITY) ---
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    try:
        # Tách chuỗi "Bearer <token>"
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # Trả về: {"user_id": 1, "role": "admin", "room_id": 101}
    except (JWTError, IndexError):
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc hết hạn")

# --- 4. API ĐĂNG NHẬP (LOGIN) ---
@app.post("/login")
async def login(req: LoginRequest):
    # Truy vấn User từ Supabase
    res = supabase.table("users").select("*").eq("username", req.username).execute()
    user = res.data[0] if res.data else None

    # Kiểm tra mật khẩu (So sánh trực tiếp để Hiển dễ test trước)
    if not user or user['password_hash'] != req.password:
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không đúng")

    # Tạo nội dung Token (Payload)
    token_data = {
        "user_id": user['id'],
        "role": user['role'],
        "room_id": user.get('room_id'), 
        "exp": datetime.utcnow() + timedelta(days=1) # Token dùng được trong 24h
    }
    
    # Mã hóa thành chuỗi Token
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user['role'],
        "full_name": user['full_name']
    }





# --------------------------------------------------------------------------------
class RoomSchema(BaseModel):
    room_name: str

class CategorySchema(BaseModel):
    category_name: str

class DeviceResponse(BaseModel):
    id: int
    device_name: str
    device_code: str
    status: str
    description: Optional[str] = None
    qr_url: Optional[str]
    barcode_url: Optional[str]
    created_at: Optional[str]
    last_inventory_at: Optional[str]
    rooms: RoomSchema        # Thông tin phòng lồng vào
    categories: CategorySchema # Thông tin loại lồng vào
    

@app.get("/api/devices", response_model=List[DeviceResponse])
async def get_devices(
    category_id: Optional[CategorySchema] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user) # Lấy user từ Token
):
    role = user.get("role")
    user_room_id = user.get("room_id")

    # 1. Bắt đầu Query với Join bảng rooms và categories
    # Dùng .select("*, rooms(room_name), categories(category_name)")
    query = supabase.table("devices").select("*, rooms(room_name), categories(category_name)")

    # 2. PHÂN QUYỀN (ROLE-BASED ACCESS CONTROL)
    if role == "teacher":
        if not user_room_id:
            return [] # Giáo viên không có phòng thì không thấy gì
        # Chỉ lấy thiết bị thuộc phòng của giáo viên này
        query = query.eq("room_id", user_room_id)
    
    # Nếu là 'admin' thì không thêm filter room_id (thấy tất cả)

    # 3. BỘ LỌC NÂNG CAO (FILTERS)
    if category_id:
        query = query.eq("category_id", category_id)
    
    if status:
        query = query.eq("status", status)
    
    if search:
        # Tìm kiếm theo tên hoặc mã code (Dùng or để tìm cả 2)
        query = query.or_(f"device_name.ilike.%{search}%,device_code.ilike.%{search}%")

    # 4. SẮP XẾP (Mới nhất lên đầu)
    response = query.order("created_at", desc=True).execute()

    return response.data



# ------------------------------------------

class ScanRequest(BaseModel):
    device_code: str
    handheld_name: str
# --- API KIỂM KÊ ---
@app.post("/api/inventory/scan")
async def scan_and_log(req: ScanRequest, user: dict = Depends(get_current_user)):
    # 1. Lấy thông tin thiết bị và phòng
    res = supabase.table("devices").select("id, device_name, status, rooms(room_name)")\
        .eq("device_code", req.device_code).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Device Not Found")
    
    device = res.data[0]
    
    # 2. Ghi nhật ký kiểm kê (Log)
    log_entry = {
        "device_id": device["id"],
        "handheld_name": req.handheld_name,
        "inventory_at": "now()",
        "status_at_scan": device["status"]
        
    }
    supabase.table("inventory_logs").insert(log_entry).execute()

    # 3. Cập nhật ngày kiểm kê mới nhất vào bảng devices
    supabase.table("devices").update({"last_inventory_at": datetime.now().isoformat()})\
        .eq("id", device["id"]).execute()

    # 4. Trả về cho ESP32 (Dùng key ngắn gọn n, r, s)
    return {
        "n": device["device_name"],
        "r": device["rooms"]["room_name"],
        "s": device["status"]
    }
    
    
# ---------------------------------------------------
class ReportRequest(BaseModel):
    device_code: str
    description: str | None = None
    status_reported: str  # Ví dụ: "Đã hỏng" hoặc "Cần bảo trì"
    handheld_name: str

@app.post("/api/report/device")
async def report_device_issue(req: ReportRequest, user: dict = Depends(get_current_user)):
    # 1. Tìm thiết bị
    res = supabase.table("devices").select("id, device_name").eq("device_code", req.device_code).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Device Not Found")
    
    device_id = res.data[0]['id']

    # 2. Ghi vào bảng log_reports
    report_data = {
        "device_id": device_id,
        "handheld_name": req.handheld_name,
        "description": req.description,
        "status": req.status_reported
    }
    supabase.table("report_logs").insert(report_data).execute()

    # 3. Cập nhật trạng thái mới nhất trực tiếp vào bảng devices
    supabase.table("devices").update({"status": req.status_reported}).eq("id", device_id).execute()

    return {"message": "Báo cáo thành công", "device": res.data[0]['device_name']}




if __name__ == "__main__":
    # Lấy cổng từ môi trường của Render, mặc định là 8000 nếu chạy local
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)