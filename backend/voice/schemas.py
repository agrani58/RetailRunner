# backend/voice/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from shared.schemas import ClientUserData

class VoiceVerifyRequest(BaseModel):
    email: EmailStr
    audio_data: str  # base64
    challenge_text: str

class VoiceVerifyResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    similarity: Optional[float] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_data: Optional[ClientUserData] = None

class VoiceProfileResponse(BaseModel):
    has_voice_profile: bool
    model_version: Optional[str] = None
    embedding_size: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class VoiceStatsResponse(BaseModel):
    email: str
    voice_enabled: bool
    security_status: Dict[str, Any]

class VoiceDisableRequest(BaseModel):
    password: str