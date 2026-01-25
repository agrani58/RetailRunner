# backend/auth/routes.py (updated signup endpoint to handle real users)
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer
import hashlib
import base64
import os
import tempfile
import json
from typing import Optional
from pydantic import BaseModel

from shared.dependencies import get_current_user
from . import schemas as auth_schemas
from .auth_utils import create_access_token, create_refresh_token
from database.operations import (
    create_user,
    verify_user,
    get_user_by_id,
    create_refresh_token as db_create_refresh_token,
    get_refresh_token,
    revoke_refresh_token,
    save_voice_profile,
    enable_voice_auth,
)

# Import voice components correctly
from voice.models import VoiceEmbeddingModel
from voice.processor import AudioProcessor
from voice.speech_verifier import speech_verifier

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()
embedding_model = VoiceEmbeddingModel()
processor = AudioProcessor()

class SignupWithVoiceRequest(BaseModel):
    """Extend UserCreate with optional voice data"""
    email: str
    password: str
    voice_sample: Optional[str] = None  # base64 encoded audio
    challenge_text: Optional[str] = None

@router.post("/signup")
def signup(user_data: SignupWithVoiceRequest = Body(...)):
    """Create new user with optional voice sample and strict speech verification"""
    print(f"SIGNUP: Attempting to create user with email: {user_data.email}")
    
    # Create user first
    user = create_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    print(f"SIGNUP: User created successfully: {user}")
    
    result = {
        "message": "Account created successfully",
        "email": user['email'],
        "user_id": user['id'],
        "voice_enabled": False,
        "speech_verified": False
    }
    
    # If voice sample provided, process it with strict verification
    if user_data.voice_sample and user_data.challenge_text:
        print(f"SIGNUP: Processing voice sample for user_id: {user['id']}")
        print(f"SIGNUP: Challenge text: {user_data.challenge_text}")
        
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(user_data.voice_sample)
            print(f"SIGNUP: Audio bytes decoded, length: {len(audio_bytes)}")
            
            # Validate recording and get audio path
            valid, message, audio_path = processor.validate_recording(audio_bytes)
            if not valid:
                result["voice_message"] = f"Audio validation failed: {message}"
                result["speech_verified"] = False
                return result
            
            try:
                # STEP 1: Strict speech verification using shared speech_verifier
                print(f"SIGNUP: Starting speech verification...")
                is_correct_speech, spoken_text, speech_message = speech_verifier.verify_challenge_speech(
                    audio_path, user_data.challenge_text
                )
                
                print(f"SIGNUP DEBUG: Is correct: {is_correct_speech}")
                print(f"SIGNUP DEBUG: Spoken text: '{spoken_text}'")
                print(f"SIGNUP DEBUG: Message: {speech_message}")
                
                if not is_correct_speech:
                    result["voice_message"] = f"Speech verification failed: {speech_message}"
                    result["speech_verified"] = False
                    return result
                
                print(f"SIGNUP: Speech verification PASSED!")
                
                # STEP 2: Create embedding
                print(f"SIGNUP: Creating voice embedding...")
                embedding = embedding_model.create_embedding(audio_path)
                
                if embedding:
                    print(f"SIGNUP: Embedding created, length: {len(embedding)}")
                    
                    # Save voice profile
                    print(f"SIGNUP: Saving voice profile...")
                    if save_voice_profile(user['id'], embedding):
                        print(f"SIGNUP: Voice profile saved successfully")
                        
                        # Enable voice auth
                        print(f"SIGNUP: Enabling voice auth...")
                        enabled_user = enable_voice_auth(user['id'])
                        if enabled_user:
                            print(f"SIGNUP: Voice auth enabled successfully")
                            result["voice_enabled"] = True
                            result["voice_message"] = "Voice authentication enabled successfully"
                            result["speech_verified"] = True
                            result["spoken_text"] = spoken_text
                        else:
                            print(f"SIGNUP: Failed to enable voice auth")
                            result["voice_message"] = "Voice profile saved but failed to enable voice authentication"
                            result["speech_verified"] = True
                    else:
                        print(f"SIGNUP: Failed to save voice profile")
                        result["voice_message"] = "Failed to save voice profile"
                        result["speech_verified"] = True  # Speech was correct
                else:
                    print(f"SIGNUP: Failed to create voice embedding")
                    result["voice_message"] = "Failed to create voice embedding"
                    result["speech_verified"] = True  # Speech was correct
                    
            finally:
                # Clean up temp file
                if audio_path and os.path.exists(audio_path):
                    processor.cleanup(audio_path)
                
        except Exception as e:
            print(f"SIGNUP ERROR: {e}")
            import traceback
            traceback.print_exc()
            result["voice_message"] = f"Failed to process voice sample: {str(e)}"
            result["speech_verified"] = False
    else:
        result["voice_message"] = "No voice sample provided"
    
    print(f"SIGNUP: Final result: {result}")
    return result

@router.post("/login", response_model=auth_schemas.TokenResponse)
def login(login_data: auth_schemas.LoginRequest):
    """Login user"""
    print(f"LOGIN: Attempting login for email: {login_data.email}")
    
    user = verify_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    print(f"LOGIN: User verified: {user['email']}, voice_enabled: {user.get('voice_enabled', False)}")
    
    access_token = create_access_token(user['id'], user['email'])
    refresh_token, token_hash, expires_at = create_refresh_token(user['id'])
    
    # Create refresh token
    if not db_create_refresh_token(user['id'], token_hash, expires_at):
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    # Get updated user with voice_enabled status
    updated_user = get_user_by_id(user['id'])
    
    return auth_schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_data={
            "id": updated_user['id'],
            "email": updated_user['email'],
            "voice_enabled": updated_user.get('voice_enabled', False)
        }
    )

@router.post("/refresh", response_model=auth_schemas.TokenResponse)
def refresh(refresh_data: auth_schemas.RefreshRequest):
    """Refresh access token"""
    token_hash = hashlib.sha256(refresh_data.refresh_token.encode()).hexdigest()
    token_data = get_refresh_token(token_hash)
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user = get_user_by_id(token_data['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new refresh token
    new_refresh_token, new_token_hash, new_expires_at = create_refresh_token(user['id'])
    
    # Delete old token first
    revoke_refresh_token(user['id'])
    
    # Create new token
    if not db_create_refresh_token(user['id'], new_token_hash, new_expires_at):
        raise HTTPException(status_code=500, detail="Failed to refresh session")
    
    # Create new access token
    access_token = create_access_token(user['id'], user['email'])
    
    return auth_schemas.TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_data={
            "id": user['id'],
            "email": user['email'],
            "voice_enabled": user.get('voice_enabled', False)
        }
    )

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Logout user"""
    revoke_refresh_token(current_user['id'])
    return {
        "message": "Logged out successfully",
        "cleanup": True,
        "clear_items": [
            "access_token", "refresh_token", "user_data", "cart",
            "pending_email", "pending_voice_enrollment",
            "last_used_email"
        ]
    }

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    # Get fresh user data from database
    user = get_user_by_id(current_user['id'])
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")