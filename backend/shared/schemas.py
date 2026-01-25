# backend/shared/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

# Base schemas used across multiple modules

class UserBase(BaseModel):
    """Base user schema"""
    id: int
    email: EmailStr
    voice_enabled: bool = False
    
    class Config:
        from_attributes = True

class TimestampMixin(BaseModel):
    """Mixin for timestamps"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SimpleResponse(BaseModel):
    """Simple API response"""
    message: str
    success: bool = True
    
    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    """Error response schema"""
    detail: str
    status_code: int
    
    class Config:
        from_attributes = True

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    limit: int = 20
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    """Paginated response schema"""
    items: list
    total: int
    page: int
    pages: int
    
    class Config:
        from_attributes = True

# Minimal user data for client storage
class ClientUserData(BaseModel):
    """Minimal user data for client storage"""
    id: int
    email: EmailStr
    voice_enabled: bool
    
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # user_id
    email: str
    exp: Optional[int] = None
    
    class Config:
        from_attributes = True

class ChallengeRequest(BaseModel):
    """Base challenge request"""
    email: Optional[EmailStr] = None
    
    class Config:
        from_attributes = True

class ChallengeResponse(BaseModel):
    """Base challenge response"""
    challenge_text: str
    expires_in: int = 300
    
    class Config:
        from_attributes = True