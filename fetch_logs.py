import os
from core.config import supabase

logs = supabase.table("inventory_logs").select("*, devices(device_name, status)").order("inventory_at", desc=True).limit(5).execute()
for log in logs.data:
    print(log)
