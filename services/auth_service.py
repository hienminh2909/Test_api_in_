from fastapi import HTTPException, Header
from jose import jwt, JWTError
from core.config import SECRET_KEY, ALGORITHM

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
