from fastapi import APIRouter, Depends
from core.config import supabase
from services.auth_service import get_current_user
from datetime import datetime
from core.cache import dashboard_cache

router = APIRouter()

@router.get("/activity")
def get_recent_activity(user: dict = Depends(get_current_user)):
    cache_key = "dashboard_activity"
    cached = dashboard_cache.get(cache_key)
    if cached is not None:
        return cached
    try:

        inventory_logs = supabase.table("inventory_logs").select("*, devices(device_name, status)").order("inventory_at", desc=True).limit(5).execute()
        

        report_logs = supabase.table("requests").select("*, devices(device_name), users!requests_created_by_fkey(full_name)").eq("request_type", "REPORT").order("created_at", desc=True).limit(5).execute()
        

        new_devices = supabase.table("devices").select("*, rooms(room_name)").order("created_at", desc=True).limit(5).execute()

        activities = []

        for log in (inventory_logs.data or []):
            device_info = log.get('devices') or {}
            d_name = device_info.get('device_name', 'Thiết bị')
            
            # Lấy trạng thái hiện tại của thiết bị thay vì trạng thái lúc quét
            status_scan = device_info.get('status', 'N/A')
            if status_scan == 'Bình thường':
                status_scan = 'Tốt'
                
            activities.append({
                "type": "inventory",
                "title": "Kiểm kê thiết bị",
                "content": f"Thiết bị: {d_name} - Trạng thái: {status_scan}",
                "description": f"Thiết bị: {d_name} - Trạng thái: {status_scan}",
                "time": log.get("inventory_at"),
                "user": log.get("handheld_name", "N/A")
            })

        for log in (report_logs.data or []):
            d_name = log.get('devices', {}).get('device_name', 'N/A') if log.get('devices') else 'N/A'
            u_name = log.get('users', {}).get('full_name', 'N/A') if log.get('users') else 'N/A'
            activities.append({
                "type": "report",
                "title": "Báo hỏng mới",
                "content": f"Thiết bị: {d_name} - Vấn đề: {log.get('description', 'Chưa có mô tả')}",
                "description": f"Thiết bị: {d_name} - Vấn đề: {log.get('description', 'Chưa có mô tả')}",
                "time": log.get("created_at"),
                "user": u_name
            })

        for dev in (new_devices.data or []):
            r_name = dev.get('rooms', {}).get('room_name', 'N/A') if dev.get('rooms') else 'N/A'
            activities.append({
                "type": "device",
                "title": "Tài sản mới",
                "content": f"Đã thêm {dev['device_name']} vào phòng {r_name}",
                "description": f"Đã thêm {dev['device_name']} vào phòng {r_name}",
                "time": dev.get("created_at"),
                "user": "Hệ thống"
            })

        activities.sort(key=lambda x: x.get("time") or "", reverse=True)
        result = activities[:10]
        dashboard_cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"ERROR in get_recent_activity: {e}")
        return []

@router.get("/inventory-history")
def get_inventory_history(months: int = 6, user: dict = Depends(get_current_user)):
    cache_key = f"dashboard_history_{months}"
    cached = dashboard_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        from dateutil.relativedelta import relativedelta
        
        end_date = datetime.utcnow()
        start_date = (end_date - relativedelta(months=months-1)).replace(day=1, hour=0, minute=0, second=0)
        

        # Bỏ lte filter để tránh lỗi múi giờ làm lọt log
        logs_res = supabase.table("inventory_logs").select("inventory_at, device_id") \
            .gte("inventory_at", start_date.isoformat()) \
            .execute()
        

        devices_res = supabase.table("devices").select("id, purchase_date").execute()
        all_devices = devices_res.data or []
        
        labels = []
        total_data = []
        checked_data = []
        
        curr = start_date
        while curr <= end_date:
            m_label = f"T{curr.month}/{curr.year}"
            labels.append(m_label)
            
            month_start = curr.replace(day=1, hour=0, minute=0, second=0)
            import calendar
            _, last_day = calendar.monthrange(curr.year, curr.month)
            month_end = curr.replace(day=last_day, hour=23, minute=59, second=59)
            
            checked_ids = set()
            for log in (logs_res.data or []):
                try:
                    import dateutil.parser
                    log_date = dateutil.parser.isoparse(log['inventory_at']).replace(tzinfo=None)
                    if month_start <= log_date <= month_end:
                        checked_ids.add(log['device_id'])
                except Exception as e:
                    print(f"Error parsing date {log.get('inventory_at')}: {e}")
                    continue
            
            checked_data.append(len(checked_ids))
            
            h_total = 0
            for d in all_devices:
                p_date_str = d.get('purchase_date')
                if not p_date_str:
                    h_total += 1
                    continue
                try:
                    p_ts = p_date_str.replace('Z', '').split('+')[0].split('T')[0]
                    p_date = datetime.strptime(p_ts, "%Y-%m-%d")
                    if p_date <= month_end:
                        h_total += 1
                except:
                    h_total += 1
            
            total_data.append(h_total)
            curr += relativedelta(months=1)
            
        result = {
            "labels": labels,
            "total": total_data,
            "checked": checked_data
        }
        dashboard_cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"ERROR in get_inventory_history: {e}")
        return {"labels": [], "total": [], "checked": []}
