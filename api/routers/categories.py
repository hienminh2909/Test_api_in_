from fastapi import APIRouter, Depends, HTTPException
from core.config import supabase
from services.auth_service import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class CategoryCreate(BaseModel):
    category_name: str
    category_code: str
    description: Optional[str] = None

@router.get("")
def get_categories(user: dict = Depends(get_current_user)):
    # Lấy danh sách categories
    categories_res = supabase.table("categories").select("*").execute()
    categories = categories_res.data
    
    # Lấy số lượng thiết bị cho mỗi category
    # Dùng query để lấy tất cả devices và count theo category_id
    devices_res = supabase.table("devices").select("category_id").execute()
    device_data = devices_res.data
    
    # Đếm thủ công (vì supabase-py hạn chế aggregate phức tạp trong join)
    count_map = {}
    for d in device_data:
        cat_id = d.get("category_id")
        if cat_id:
            count_map[cat_id] = count_map.get(cat_id, 0) + 1
            
    for cat in categories:
        cat["device_count"] = count_map.get(cat["id"], 0)
        
    return categories

@router.post("")
def create_category(req: CategoryCreate, user: dict = Depends(get_current_user)):
    print(f">>> API CATEGORIES: [POST] User: {user.get('role')} (ID: {user.get('user_id')})")
    if user.get("role") != "admin":
        print(f">>> API CATEGORIES: Permission Denied for user {user.get('user_id')}")
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    
    try:
        data_to_insert = req.dict()
        print(f">>> API CATEGORIES: Data to Supabase: {data_to_insert}")
        
        # Thử kiểm tra bảng trước khi insert
        test_res = supabase.table("categories").select("id").limit(1).execute()
        print(f">>> API CATEGORIES: Table check (Select 1): {test_res.data}")

        res = supabase.table("categories").insert(data_to_insert).execute()
        
        print(f">>> API CATEGORIES: Supabase Result: {res.data}")
        
        if res.data and len(res.data) > 0:
            print(f">>> API CATEGORIES: INSERT SUCCESSFUL - ID: {res.data[0].get('id')}")
            return res.data[0]
        else:
            print(">>> API CATEGORIES: INSERT FAILED - No data returned")
            raise HTTPException(status_code=400, detail="Database không trả về dữ liệu sau khi chèn")
            
    except Exception as e:
        err_str = str(e)
        print(f">>> API CATEGORIES: !!! ERROR !!! - {err_str}")
        if "duplicate key" in err_str.lower():
            raise HTTPException(status_code=400, detail="Mã hoặc Tên danh mục đã tồn tại")
        raise HTTPException(status_code=400, detail=f"Lỗi Supabase: {err_str}")

@router.put("/{category_id}")
def update_category(category_id: int, req: CategoryCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        print(f">>> API CATEGORIES: Updating ID {category_id} with {req}")
        res = supabase.table("categories").update(req.dict()).eq("id", category_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Không tìm thấy danh mục để cập nhật hoặc dữ liệu không thay đổi")
        return res.data[0]
    except Exception as e:
        error_msg = str(e)
        print(f">>> API CATEGORIES: Update Error - {error_msg}")
        if "duplicate key" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Mã danh mục mới đã tồn tại trong hệ thống.")
        raise HTTPException(status_code=400, detail=f"Lỗi Database: {error_msg}")

@router.delete("/{category_id}")
def delete_category(category_id: int, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền thao tác")
    try:
        res = supabase.table("categories").delete().eq("id", category_id).execute()
        return {"message": "Đã xóa thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
