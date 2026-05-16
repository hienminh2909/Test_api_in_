from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, devices, inventory, rooms, categories, users, reports, requests, dashboard, notifications

app = FastAPI(title="Quản lý Thiết bị API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["Rooms"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(requests.router, prefix="/api/requests", tags=["Requests"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

@app.get("/")
async def root():
    return {"message": "Hệ thống Quản lý Thiết bị API đang hoạt động"}
