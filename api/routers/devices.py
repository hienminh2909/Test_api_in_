import io
import time
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
import pandas as pd
from datetime import datetime
import concurrent.futures

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from typing import List, Optional

from core.config import supabase
from services.auth_service import get_current_user
from schemas.device import DeviceResponse, RegisterDevice, DeviceUpdate
from api.routers.notifications import create_notification

router = APIRouter()

def get_safe_url(bucket, path):
    try:
        res = supabase.storage.from_(bucket).get_public_url(path)
        if isinstance(res, str): return res
        return getattr(res, "public_url", str(res))
    except:
        from core.config import SUPABASE_URL
        return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"

@router.get("", response_model=List[DeviceResponse])
def get_devices(
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    ids: Optional[str] = None,
    room_id: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    role = user.get("role")
    user_room_id = user.get("room_id")

    query = supabase.table("devices").select("*, rooms(id, room_name), categories(category_name), users(full_name)")

    if role == "teacher":
        if user_room_id is None: 
            return []
        query = query.eq("room_id", user_room_id)
    elif room_id:
        query = query.eq("room_id", room_id)

    if status and status.strip():
        query = query.eq("status", status)

    if category_id:
        query = query.eq("category_id", category_id)

    if search and search.strip():
        val = f"%{search}%"
        room_ids_res = supabase.table("rooms").select("id").ilike("room_name", val).execute()
        room_ids = [str(r['id']) for r in room_ids_res.data]
        if room_ids:
            room_filter = f"room_id.in.({','.join(room_ids)})"
            query = query.or_(f"device_name.ilike.{val},{room_filter}")
        else:
            query = query.ilike("device_name", val)

    if ids and ids.strip():
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.in_("id", id_list)

    response = query.order("created_at", desc=True).execute()
    
    if not response.data:
        return []
    
    results = []
    for item in response.data:
        room_obj = item.get("rooms") or {"room_name": "N/A"}
        cat_obj = item.get("categories") or {"category_name": "N/A"}
        user_obj = item.get("users") or {"full_name": "N/A"}
        
        item["rooms"] = room_obj
        item["categories"] = cat_obj
        item["users"] = user_obj
        item["quantity"] = 1
        item["all_devices_detail"] = []
        results.append(item)
        
    return results

@router.get("/summary", response_model=List[DeviceResponse])
def get_devices_summary(
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    ids: Optional[str] = None,
    room_id: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    role = user.get("role")
    user_room_id = user.get("room_id")

    query = supabase.table("devices").select("*, rooms(id, room_name), categories(category_name), users(full_name)")

    if role == "teacher":
        if user_room_id is None: 
            return []
        query = query.eq("room_id", user_room_id)
    elif room_id:
        query = query.eq("room_id", room_id)

    if status and status.strip():
        query = query.eq("status", status)

    if category_id:
        query = query.eq("category_id", category_id)

    if search and search.strip():
        val = f"%{search}%"
        room_ids_res = supabase.table("rooms").select("id").ilike("room_name", val).execute()
        room_ids = [str(r['id']) for r in room_ids_res.data]
        if room_ids:
            room_filter = f"room_id.in.({','.join(room_ids)})"
            query = query.or_(f"device_name.ilike.{val},{room_filter}")
        else:
            query = query.ilike("device_name", val)

    if ids and ids.strip():
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.in_("id", id_list)

    response = query.order("created_at", desc=True).execute()
    
    if not response.data:
        return []

    raw_data = response.data
    grouped_data = {}

    for item in raw_data:
        room_obj = item.get("rooms") or {"room_name": "N/A"}
        cat_obj = item.get("categories") or {"category_name": "N/A"}
        user_obj = item.get("users") or {"full_name": "N/A"}
        
        room_n = room_obj.get("room_name", "N/A")
        cat_n = cat_obj.get("category_name", "N/A")
        
        # Group key bao gồm cả giá tiền để tách các thiết bị có giá khác nhau
        d_price = str(item.get('device_price', ''))
        group_key = f"{item['device_name']}-{room_n}-{cat_n}-{item['status']}-{d_price}"
        
        current_device_detail = {
            "id": item["id"],
            "device_code": item["device_code"],
            "qr_url": item.get("qr_url"),
        }

        if group_key not in grouped_data:
            new_item = item.copy()
            new_item["quantity"] = 1
            new_item["all_devices_detail"] = [current_device_detail]
            new_item["rooms"] = room_obj
            new_item["categories"] = cat_obj
            new_item["users"] = user_obj
            new_item["image_url"] = item.get("image_url")
            grouped_data[group_key] = new_item
        else:
            grouped_data[group_key]["quantity"] += 1
            grouped_data[group_key]["all_devices_detail"].append(current_device_detail)
            if not grouped_data[group_key].get("image_url") and item.get("image_url"):
                grouped_data[group_key]["image_url"] = item.get("image_url")

    return list(grouped_data.values())

@router.post("")
def register_device(form: RegisterDevice, user: dict = Depends(get_current_user)):
    role = user.get("role")
    user_room_id = user.get("room_id")
    
    # KIỂM TRA PHÂN QUYỀN CHO TEACHER
    if role == "teacher":
        if user_room_id is None:
            raise HTTPException(status_code=403, detail="Tài khoản giáo viên chưa được gán phòng quản lý")
        
        # Lấy thông tin phòng mà giáo viên quản lý
        teacher_room = supabase.table("rooms").select("room_name").eq("id", user_room_id).execute()
        if not teacher_room.data or teacher_room.data[0]["room_name"] != form.room_name:
            raise HTTPException(status_code=403, detail=f"Bạn chỉ có quyền đăng ký thiết bị cho phòng {teacher_room.data[0]['room_name'] if teacher_room.data else 'được giao'}")

    try:
        room_res = supabase.table("rooms").select("id").eq("room_name", form.room_name).execute()
        if not room_res.data:
            raise HTTPException(status_code=404, detail=f"Phòng {form.room_name} không tồn tại")
        
        cat_res = supabase.table("categories").select("id, category_code").eq("category_name", form.category_name).execute()
        if not cat_res.data:
            raise HTTPException(status_code=404, detail="Loại thiết bị không tồn tại")       
        
        category_id = cat_res.data[0]['id']
        category_code = cat_res.data[0]['category_code']
        r_id = room_res.data[0]['id']

        qty = form.quantity if form.quantity and form.quantity > 0 else 1
        base_ts = int(time.time())
        devices_to_insert = []

        def upload_codes(dev_code):
            qr_buf = io.BytesIO()
            qrcode.make(dev_code).save(qr_buf, format='PNG')
            qr_path = f"qr_{dev_code}.png"
            supabase.storage.from_("qrcodes").upload(qr_path, qr_buf.getvalue(), {"content-type": "image/png"})
            qr_url = get_safe_url("qrcodes", qr_path)
            
            bar_buf = io.BytesIO()
            Code128(dev_code, writer=ImageWriter()).write(bar_buf)
            bar_path = f"bar_{dev_code}.png"
            supabase.storage.from_("qrcodes").upload(bar_path, bar_buf.getvalue(), {"content-type": "image/png"})
            bar_url = get_safe_url("qrcodes", bar_path)
            return qr_url, bar_url

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for i in range(qty):
                suffix = i + 1
                dev_code = f"{form.room_name.replace(' ', '')}-{category_code}-{base_ts}-{suffix}"
                
                future = executor.submit(upload_codes, dev_code)
                
                devices_to_insert.append({
                    "device_name": form.device_name,
                    "device_code": dev_code,
                    "room_id": r_id,
                    "category_id": category_id,
                    "status": form.status,
                    "description": form.description,
                    "purchase_date": form.purchase_date,
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": user.get("user_id"),
                    "device_price": form.device_price,
                    "future": future
                })
        
        for d in devices_to_insert:
            qr_url, bar_url = d["future"].result()
            d["qr_url"] = qr_url
            d["barcode_url"] = bar_url
            del d["future"]
        
        res = supabase.table("devices").insert(devices_to_insert).execute()
        
        if not res.data:
            raise HTTPException(status_code=500, detail="Không thể lưu thiết bị vào cơ sở dữ liệu")

        # THÔNG BÁO HỆ THỐNG
        try:
            sender_id = user.get("user_id")
            sender_name = user.get("username") or "Người dùng"
            
            # Lấy danh sách Admin
            admins = supabase.table("users").select("id").in_("role", ["admin", "Admin"]).execute()
            admin_ids = [a["id"] for a in admins.data]
            
            notif_title = "✨ Thiết bị mới đã được đăng ký"
            notif_content = f"Người dùng {sender_name} đã đăng ký thành công {len(res.data)} thiết bị {form.device_name} vào {form.room_name}."
            # Link tự động lọc theo cả Tên thiết bị và Phòng học để kết quả chính xác tuyệt đối
            notif_link = f"/devices/list?search={form.device_name}&roomName={form.room_name}"
            
            # Thông báo cho Admins
            for admin_id in admin_ids:
                if admin_id != sender_id: 
                    create_notification(admin_id, notif_title, notif_content, notif_link)
            
            # Thông báo cho chính người đăng ký
            create_notification(sender_id, "✅ Đăng ký thành công", f"Bạn đã đăng ký thành công {len(res.data)} thiết bị mới vào {form.room_name}.", notif_link)
        except Exception as e:
            print(f">>> ERROR generating registration notification: {e}")

        return {
            "message": f"Đã đăng ký thành công {len(res.data)} thiết bị",
            "count": len(res.data),
            "ids": [d['id'] for d in res.data],
            "qr_urls": [d.get('qr_url') for d in res.data]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/validate")
def validate_import(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents))
        if df.empty:
            raise HTTPException(status_code=400, detail="File rỗng")

        rooms_data = supabase.table("rooms").select("id, room_name").execute().data
        cats_data = supabase.table("categories").select("id, category_name").execute().data
        
        room_names = {r['room_name'] for r in rooms_data}
        cat_names = {c['category_name'] for c in cats_data}

        preview_data = []
        for index, row in df.iterrows():
            d_name = str(row.get('device_name', '')).strip()
            r_name = str(row.get('room_name', '')).strip()
            c_name = str(row.get('category_name', '')).strip()
            qty = int(row.get('quantity', 1))
            d_price = str(row.get('device_price', '')).strip()
            p_date = str(row.get('purchase_date', '')).strip()

            error_msg = []
            room_err = r_name not in room_names
            cat_err = c_name not in cat_names
            
            if room_err: error_msg.append(f"Phòng '{r_name}' không tồn tại")
            if cat_err: error_msg.append(f"Danh mục '{c_name}' không tồn tại")
            if not d_name or d_name == 'nan': error_msg.append("Thiết bị không có tên")
            if not d_price or d_price == 'nan': error_msg.append("Thiếu giá tiền")
            if not p_date or p_date == 'nan': error_msg.append("Thiếu ngày mua")

            preview_data.append({
                "device_name": d_name,
                "room_name": r_name,
                "category_name": c_name,
                "quantity": qty,
                "device_price": d_price,
                "purchase_date": p_date,
                "description": str(row.get('description', '')).strip(),
                "room_error": room_err,
                "cat_error": cat_err,
                "error_msg": error_msg
            })

            # Check thêm mô tả
            if not str(row.get('description', '')).strip() or str(row.get('description', '')) == 'nan':
                error_msg.append("Thiếu mô tả thiết bị")
                preview_data[-1]["is_valid"] = False # Đánh dấu không hợp lệ
            
            preview_data[-1]["is_valid"] = len(error_msg) == 0

        return {"status": "success", "data": preview_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/template")
def download_template():
    try:
        # Tạo file mẫu với các cột yêu cầu (V2)
        columns = [
            "device_name", "room_name", "category_name", 
            "status", "device_price", "quantity", "purchase_date", "description"
        ]
        # Dữ liệu mẫu (ví dụ)
        example_data = [{
            "device_name": "Máy tính Dell Latitude 7490",
            "room_name": "Phòng 101",
            "category_name": "Máy tính",
            "status": "Tốt",
            "device_price": "12.500.000",
            "quantity": 1,
            "purchase_date": datetime.now().strftime("%Y-%m-%d"),
            "description": "Máy tính xách tay i5 8th Gen, 8GB RAM, 256GB SSD"
        }]
        
        df = pd.DataFrame(example_data, columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, index=False, sheet_name='Template_V2')
        
        output.seek(0)
        data = output.getvalue()
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=Mau_Nhap_Thiet_Bi_Moi_{int(time.time())}.xlsx",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
def import_and_register(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        role = user.get("role")
        user_room_id = user.get("room_id")

        if role == "teacher":
            if user_room_id is None:
                raise HTTPException(status_code=403, detail="Tài khoản chưa được gán phòng quản lý")
            
            # Lấy tên phòng của giáo viên
            teacher_room = supabase.table("rooms").select("room_name").eq("id", user_room_id).execute()
            if teacher_room.data:
                t_room_name = teacher_room.data[0]["room_name"]
                # Lọc bỏ các dòng không thuộc phòng của giáo viên
                df = df[df['room_name'].astype(str) == t_room_name]
                if df.empty:
                    raise HTTPException(status_code=403, detail=f"File import không chứa thiết bị nào thuộc phòng {t_room_name}")
        
        if df.empty:
            raise HTTPException(status_code=400, detail="File rỗng")

        devices_to_insert = []
        base_ts = int(time.time())

        rooms_data = supabase.table("rooms").select("id, room_name").execute().data
        cats_data = supabase.table("categories").select("id, category_name, category_code").execute().data
        
        room_map = {r['room_name']: r['id'] for r in rooms_data}
        cat_map = {c['category_name']: {'id': c['id'], 'code': c['category_code']} for c in cats_data}

        def upload_codes_import(dev_code):
            qr_buf = io.BytesIO()
            qrcode.make(dev_code).save(qr_buf, format='PNG')
            qr_path = f"qr_{dev_code}.png"
            supabase.storage.from_("qrcodes").upload(qr_path, qr_buf.getvalue(), {"content-type": "image/png"})
            qr_url = get_safe_url("qrcodes", qr_path)

            bar_buf = io.BytesIO()
            Code128(dev_code, writer=ImageWriter()).write(bar_buf)
            bar_path = f"bar_{dev_code}.png"
            supabase.storage.from_("qrcodes").upload(bar_path, bar_buf.getvalue(), {"content-type": "image/png"})
            bar_url = get_safe_url("qrcodes", bar_path)
            return qr_url, bar_url

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for index, row in df.iterrows():
                d_name = str(row.get('device_name', ''))
                r_name = str(row.get('room_name', ''))
                c_name = str(row.get('category_name', ''))
                qty = int(row.get('quantity', 1))
                d_price = str(row.get('device_price', ''))
                p_date = str(row.get('purchase_date', ''))
                description = str(row.get('description', ''))

                if r_name not in room_map or c_name not in cat_map:
                    continue
                
                if not description or description == 'nan' or not d_price or d_price == 'nan':
                    continue

                r_id = room_map[r_name]
                c_id = cat_map[c_name]['id']
                c_code = cat_map[c_name]['code']

                for i in range(qty):
                    dev_code = f"{r_name.replace(' ', '')}-{c_code}-{base_ts}-{index}-{i+1}"
                    
                    future = executor.submit(upload_codes_import, dev_code)

                    devices_to_insert.append({
                        "device_name": d_name, "device_code": dev_code,
                        "room_id": r_id, "category_id": c_id, "status": "Tốt",
                        "purchase_date": p_date if p_date else datetime.utcnow().isoformat(),
                        "device_price": d_price,
                        "description": description,
                        "created_at": datetime.utcnow().isoformat(),
                        "created_by": user.get("user_id"),
                        "future": future
                    })

        for d in devices_to_insert:
            qr_url, bar_url = d["future"].result()
            d["qr_url"] = qr_url
            d["barcode_url"] = bar_url
            del d["future"]

        res = supabase.table("devices").insert(devices_to_insert).execute()
        
        # THÔNG BÁO HỆ THỐNG (TÁCH RIÊNG THEO TỪNG HÀNG TRONG EXCEL)
        try:
            sender_id = user.get("user_id")
            sender_name = user.get("username") or "Người dùng"
            
            admins = supabase.table("users").select("id").in_("role", ["admin", "Admin"]).execute()
            admin_ids = [a["id"] for a in admins.data]

            # Đã lọc df trước đó cho teacher, nên giờ chỉ cần duyệt df để tạo thông báo
            # Vì ta chèn devices_to_insert theo đúng thứ tự hàng trong df, 
            # ta có thể tạo thông báo tương ứng cho mỗi hàng.
            for index, row in df.iterrows():
                d_name = str(row.get('device_name', ''))
                r_name = str(row.get('room_name', ''))
                qty = int(row.get('quantity', 1))

                notif_title = f"📥 Nhập mới: {d_name}"
                notif_content = f"Người dùng {sender_name} đã nhập {qty} thiết bị {d_name} vào {r_name}."
                notif_link = f"/devices/list?search={d_name}"

                # Thông báo cho Admins
                for admin_id in admin_ids:
                    if admin_id != sender_id:
                        create_notification(admin_id, notif_title, notif_content, notif_link)
                
                # Thông báo cho chính người thực hiện
                create_notification(sender_id, f"✅ Đã nhập: {d_name}", f"Đã nhập thành công {qty} thiết bị vào {r_name}.", notif_link)

        except Exception as e:
            print(f">>> ERROR generating split import notifications: {e}")

        return {
            "status": "success",
            "ids": [d['id'] for d in res.data],
            "count": len(res.data),
            "qr_urls": [d.get('qr_url') for d in res.data]
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))   

@router.put("/{device_id}")
def update_device(device_id: int, req: DeviceUpdate, user: dict = Depends(get_current_user)):
    try:
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        
        if req.status is not None: update_data["status"] = req.status
        if req.device_name is not None: update_data["device_name"] = req.device_name
        if req.description is not None: update_data["description"] = req.description
        if req.purchase_date is not None: update_data["purchase_date"] = req.purchase_date
        if req.device_price is not None: update_data["device_price"] = req.device_price
        
        if req.room_name is not None:
            room_res = supabase.table("rooms").select("id").eq("room_name", req.room_name).execute()
            if room_res.data:
                update_data["room_id"] = room_res.data[0]['id']
            else:
                raise HTTPException(status_code=404, detail=f"Phòng {req.room_name} không tồn tại")
        
        if req.category is not None:
            category_res = supabase.table("categories").select("id").eq("category_name", req.category).execute()
            if category_res.data:
                update_data["category_id"] = category_res.data[0]['id']
            else:
                raise HTTPException(status_code=404, detail=f"Danh mục {req.category} không tồn tại")
                
        res = supabase.table("devices").update(update_data).eq("id", device_id).execute()
        return {"message": "Cập nhật thành công!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{device_id}")
def delete_device(device_id: int, user: dict = Depends(get_current_user)):
    user_role = str(user.get("role", "")).lower()
    
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền Admin để thực hiện thao tác này!")
        
    try:
        res = supabase.table("devices").delete().eq("id", device_id).execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
            
        return {"message": "Đã xóa thiết bị thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-image")
def upload_device_image(
    file: UploadFile = File(...),
    device_ids: str = Form(None),
    device_name: str = Form(None),
    user: dict = Depends(get_current_user)
):
    """
    Upload ảnh thiết bị lên Supabase Storage bucket 'image_device'.
    - device_ids: danh sách ID thiết bị (phân cách bằng dấu phẩy) cần cập nhật image_url
    - device_name: tên thiết bị (dùng để đặt tên file)
    """
    try:
        # Đọc file ảnh
        contents = file.file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="File ảnh rỗng")

        # Xác định content-type
        content_type = file.content_type or "image/png"
        
        # Tạo tên file an toàn (loại bỏ dấu tiếng Việt và ký tự đặc biệt)
        import unicodedata
        import re

        def remove_accents(input_str):
            nfkd_form = unicodedata.normalize('NFKD', input_str)
            return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        raw_name = device_name or "device"
        # Loại bỏ dấu, chuyển sang lowercase, thay khoảng trắng/ký tự đặc biệt bằng gạch dưới
        safe_name = remove_accents(raw_name).lower()
        safe_name = re.sub(r'[^a-z0-9]', '_', safe_name)
        # Loại bỏ gạch dưới thừa
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        
        timestamp = int(time.time())
        file_path = f"{safe_name}_{timestamp}.{ext}"

        # Upload lên Supabase Storage bucket 'image_device'
        try:
            supabase.storage.from_("image_device").upload(
                path=file_path,
                file=contents,
                file_options={"content-type": content_type}
            )
        except Exception as storage_err:
            print(f"STORAGE ERROR: {str(storage_err)}")
            # Nếu bucket chưa có hoặc lỗi, trả về lỗi chi tiết hơn
            raise HTTPException(status_code=500, detail=f"Lỗi Storage Supabase: {str(storage_err)}. Vui lòng kiểm tra bucket 'image_device' đã được tạo chưa?")

        # Lấy public URL
        try:
            image_url_res = supabase.storage.from_("image_device").get_public_url(file_path)
            # Một số phiên bản trả về object, một số trả về string trực tiếp
            if isinstance(image_url_res, str):
                image_url = image_url_res
            else:
                image_url = getattr(image_url_res, "public_url", str(image_url_res))
        except:
            image_url = f"{supabase_url}/storage/v1/object/public/image_device/{file_path}"

        # Cập nhật image_url cho tất cả device_ids
        if device_ids and str(device_ids).strip() != "None":
            try:
                # Xử lý chuỗi ID (ví dụ: "1,2,3")
                dids = [int(x.strip()) for x in str(device_ids).split(",") if x.strip()]
                print(f"DEBUG: Bat dau cap nhat image_url cho {len(dids)} thiet bi: {dids}")
                
                for did in dids:
                    # Thử cập nhật, nếu không thấy ID thì đợi 300ms rồi thử lại 1 lần (đề phòng race condition)
                    success = False
                    for attempt in range(2):
                        res = supabase.table("devices").update({
                            "image_url": image_url,
                            "updated_at": datetime.utcnow().isoformat()
                        }).eq("id", did).execute()
                        
                        if res.data:
                            print(f"DEBUG: [THANH CONG] Da cap nhat device ID {did} (Lan thu {attempt + 1})")
                            success = True
                            break
                        else:
                            print(f"DEBUG: [CHO DOI] Khong tim thay ID {did}, dang thu lai...")
                            time.sleep(0.3)
                    
                    if not success:
                        print(f"DEBUG: [THAT BAI] Vinh vien khong tim thay device ID {did}")
                
            except Exception as db_err:
                print(f"DATABASE UPDATE ERROR: {str(db_err)}")
                raise HTTPException(status_code=500, detail=f"Lỗi cập nhật Database: {str(db_err)}")
        else:
            print("DEBUG: Khong co device_ids duoc gui len de cap nhat image_url")

        return {"message": "Upload ảnh thành công", "image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
