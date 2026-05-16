from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    username: str # Đã đổi từ email sang username theo yêu cầu
