# backend/auth/schemas.py
from pydantic import BaseModel, EmailStr, validator
from typing import Dict, Any

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_data: Dict[str, Any]

class RefreshRequest(BaseModel):
    refresh_token: str