import paho.mqtt.client as mqtt
import json
from datetime import datetime
import re

from core.config import supabase
from core.cache import dashboard_cache

MQTT_BROKER = "485c424b34b94547a880a5e0ee048610.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hienminh2909"
MQTT_PASSWORD = "Minhhien24@"

TOPIC_INV_REQ = "scanner/inventory/request"
TOPIC_INV_RES = "scanner/inventory/response"
TOPIC_REP_REQ = "scanner/report/request"
TOPIC_REP_RES = "scanner/report/response"

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

def on_connect(client, userdata, flags, rc):
    print(f"✅ Đã kết nối tới MQTT Broker {MQTT_BROKER} với mã: {rc}")
    client.subscribe(TOPIC_INV_REQ)
    client.subscribe(TOPIC_REP_REQ)

def on_message(client, userdata, msg):
    print(f"📥 Nhận được tin nhắn ở topic: {msg.topic}")
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
    except Exception as e:
        print("Lỗi parse JSON:", e)
        return

    if msg.topic == TOPIC_INV_REQ:
        handle_inventory_request(client, data)
    elif msg.topic == TOPIC_REP_REQ:
        handle_report_request(client, data)

def handle_inventory_request(client, data):
    try:
        device_code = data.get("device_code")
        handheld_name = data.get("handheld_name")
        
        if not device_code:
            return

        res = supabase.table("devices").select("id, device_name, status, rooms(room_name)").eq("device_code", device_code).execute()
        if not res.data:
            client.publish(TOPIC_INV_RES, json.dumps({"n": "NOT_FOUND", "r": "", "s": ""}))
            return
            
        device = res.data[0]
        device_name_safe = remove_vietnamese_accent(device["device_name"])
        status_safe = remove_vietnamese_accent(device["status"])
        room_name = device["rooms"]["room_name"] if device.get("rooms") else "N/A"
        room_name_safe = remove_vietnamese_accent(room_name)

        res_user = supabase.table("users").select("id").eq("handheld_name", handheld_name).execute()
        user_id = res_user.data[0]['id'] if res_user.data else None

        log_entry = {
            "device_id": device["id"],
            "resolved_by": user_id,
            "inventory_at": datetime.utcnow().isoformat(),
            "status_at_scan": device["status"]
        }
        supabase.table("inventory_logs").insert(log_entry).execute()
        dashboard_cache.clear()

        supabase.table("devices").update({"last_inventory_at": datetime.utcnow().isoformat()}).eq("id", device["id"]).execute()

        res_data = {
            "n": device_name_safe,
            "r": room_name_safe,
            "s": status_safe
        }
        client.publish(TOPIC_INV_RES, json.dumps(res_data))
        print(f"📤 Đã phản hồi Inventory: {res_data}")

    except Exception as e:
        print("Lỗi khi xử lý kiểm kê qua MQTT:", e)

def handle_report_request(client, data):
    try:
        device_code = data.get("device_code")
        status_device = data.get("status_device", "Hỏng hóc")
        request_type = data.get("request_type", "REPORT")
        description = data.get("description", "")
        handheld_name = data.get("handheld_name")
        
        if not device_code:
            return

        res_device = supabase.table("devices").select("id").eq("device_code", device_code).execute()
        if not res_device.data:
            client.publish(TOPIC_REP_RES, json.dumps({"success": False, "message": "Thiet bi khong ton tai"}))
            return
            
        device_id = res_device.data[0]['id']

        res_user = supabase.table("users").select("id").eq("handheld_name", handheld_name).execute()
        user_id = res_user.data[0]['id'] if res_user.data else None

        report_data = {
            "created_by": user_id,
            "device_id": device_id,
            "status_device": status_device,
            "description": description,
            "request_type": request_type,
            "status_resolve": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("requests").insert(report_data).execute()

        client.publish(TOPIC_REP_RES, json.dumps({"success": True, "message": "Gui bao cao thanh cong"}))
        print("📤 Đã phản hồi Report thành công.")

    except Exception as e:
        print("Lỗi khi xử lý báo cáo qua MQTT:", e)
        client.publish(TOPIC_REP_RES, json.dumps({"success": False, "message": "Loi may chu"}))

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def start_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print("🚀 MQTT Client đã được khởi động.")
    except Exception as e:
        print("⚠️ Không thể kết nối tới MQTT Broker:", e)

def stop_mqtt():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
