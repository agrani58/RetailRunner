from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def password_length(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_data: Dict[str, Any]  # Single user object
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SimpleResponse(BaseModel):
    message: str
    email: Optional[str] = None
    user_id: Optional[int] = None

class UserResponse(BaseModel):
    user_id: int
    email: str
    created_at: Optional[datetime] = None  # ← changed from str to datetime