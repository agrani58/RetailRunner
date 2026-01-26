# \backend\voice\routes.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body, Header
import base64
import os
import tempfile
from typing import Optional
from pydantic import BaseModel

# Import dependencies
from shared.dependencies import get_current_user
from .models import VoiceEmbeddingModel, VoiceSecurityManager, AudioQualityValidator
from .processor import AudioProcessor
from .security import RateLimiter
from .speech_verifier import speech_verifier

# Import database operations
from database.operations import (
    get_user_by_email,
    enable_voice_auth,
    disable_voice_auth,
    save_voice_profile,
    get_voice_profile,
    create_challenge,
    validate_challenge,
    verify_user,
    get_user_by_id
)

# Import auth utilities
from auth.auth_utils import create_access_token, create_refresh_token
from database.operations import create_refresh_token as db_create_refresh_token

# Define router FIRST
router = APIRouter(prefix="/voice", tags=["Voice Authentication"])
processor = AudioProcessor()
embedding_model = VoiceEmbeddingModel()
security_manager = VoiceSecurityManager()
audio_validator = AudioQualityValidator()
rate_limiter = RateLimiter()

class VoiceLoginRequest(BaseModel):
    email: str
    audio_data: str
    challenge_text: str

@router.get("/enroll/challenge")
def enroll_challenge(current_user: dict = Depends(get_current_user)):
    """Get challenge for voice enrollment"""
    challenge_text = security_manager.generate_challenge()
    challenge = create_challenge(current_user['id'], challenge_text)
    
    if not challenge:
        raise HTTPException(status_code=500, detail="Failed to create challenge")
    
    return {
        "challenge_text": challenge_text,
        "expires_in": 300
    }

@router.post("/enroll/verify")
async def verify_enrollment(
    audio: UploadFile = File(...),
    challenge_text: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Verify enrollment and create/update voice profile"""
    if not validate_challenge(current_user['id'], challenge_text):
        raise HTTPException(status_code=400, detail="Invalid challenge")
    
    audio_bytes = await audio.read()
    valid, message, audio_path = processor.validate_recording(audio_bytes)
    
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    try:
        # Step 1: Verify speech matches challenge EXACTLY
        is_correct_speech, spoken_text, speech_message = speech_verifier.verify_challenge_speech(
            audio_path, challenge_text
        )
        
        if not is_correct_speech:
            raise HTTPException(status_code=400, detail=speech_message)
        
        # Step 2: Validate audio quality
        is_quality_ok, quality_message = audio_validator.validate(audio_path)
        if not is_quality_ok:
            raise HTTPException(status_code=400, detail=quality_message)
        
        # Step 3: Create embedding
        embedding = embedding_model.create_embedding(audio_path)
        
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to create voice embedding")
        
        # Save or update profile
        if not save_voice_profile(current_user['id'], embedding):
            raise HTTPException(status_code=500, detail="Failed to save profile")
        
        # Enable voice auth if not already enabled
        if not current_user.get('voice_enabled', False):
            if not enable_voice_auth(current_user['id']):
                raise HTTPException(status_code=500, detail="Failed to enable voice authentication")
        
        # Get the updated user data
        user = get_user_by_id(current_user['id'])
        if not user:
            raise HTTPException(status_code=500, detail="Failed to get user data")
        
        # Generate new tokens with updated voice_enabled status
        access_token = create_access_token(user['id'], user['email'])
        refresh_token, token_hash, expires_at = create_refresh_token(user['id'])
        
        if not db_create_refresh_token(user['id'], token_hash, expires_at):
            raise HTTPException(status_code=500, detail="Failed to update session")
        
        return {
            "success": True,
            "message": "Voice profile created successfully",
            "spoken_text": spoken_text,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_data": {
                "id": user['id'],
                "email": user['email'],
                "voice_enabled": True
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in enrollment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if audio_path and os.path.exists(audio_path):
            processor.cleanup(audio_path)

@router.get("/login/challenge")  # CHANGED from POST to GET
def login_challenge(email: str):
    """Get challenge for voice login"""
    # Clean email
    email = email.strip().lower()
    
    # Get user
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please sign up first.")
    
    # Check if voice is enabled
    if not user.get('voice_enabled', False):
        raise HTTPException(status_code=400, detail="Voice authentication is not enabled for this account. Please enable it first.")
    
    # Generate challenge
    challenge_text = security_manager.generate_challenge()
    challenge = create_challenge(user['id'], challenge_text)
    
    if not challenge:
        raise HTTPException(status_code=500, detail="Failed to create challenge")
    
    return {
        "challenge_text": challenge_text,
        "expires_in": 300
    }

@router.post("/login/verify")
async def verify_login(request: VoiceLoginRequest):
    """Verify voice login - accepts JSON body, uses 0.8 threshold"""
    email = request.email.strip().lower()
    
    # Get user
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please sign up first.")
    
    # Check voice enabled
    if not user.get('voice_enabled', False):
        raise HTTPException(status_code=400, detail="Voice authentication is not enabled for this account.")
    
    # Validate challenge
    if not validate_challenge(user['id'], request.challenge_text):
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(request.audio_data)
    except:
        raise HTTPException(status_code=400, detail="Invalid audio data")
    
    # Validate recording
    valid, message, audio_path = processor.validate_recording(audio_bytes)
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    try:
        # Step 1: Verify speech matches challenge EXACTLY
        is_correct_speech, spoken_text, speech_message = speech_verifier.verify_challenge_speech(
            audio_path, request.challenge_text
        )
        
        if not is_correct_speech:
            raise HTTPException(
                status_code=400, 
                detail=f"Speech verification failed: {speech_message}"
            )
        
        # Step 2: Validate audio quality
        is_quality_ok, quality_message = audio_validator.validate(audio_path)
        if not is_quality_ok:
            raise HTTPException(status_code=400, detail=quality_message)
        
        # Step 3: Get stored profile and verify speaker
        profile = get_voice_profile(user['id'])
        if not profile:
            raise HTTPException(status_code=400, detail="No voice profile found")
        
        # Create new embedding
        new_embedding = embedding_model.create_embedding(audio_path)
        
        if not new_embedding:
            raise HTTPException(status_code=500, detail="Failed to create voice embedding")
        
        # Verify speaker with 0.8 threshold
        is_match, similarity = embedding_model.verify_speaker(
            profile['embedding_vector'], 
            new_embedding,
            threshold=0.8
        )
        
        if not is_match:
            raise HTTPException(
                status_code=401, 
                detail=f"Voice verification failed (similarity: {similarity:.2f}, required: 0.80). Please try again."
            )
        
        # Create tokens
        access_token = create_access_token(user['id'], user['email'])
        refresh_token, token_hash, expires_at = create_refresh_token(user['id'])
        
        if not db_create_refresh_token(user['id'], token_hash, expires_at):
            raise HTTPException(status_code=500, detail="Failed to create session")
        
        return {
            "success": True,
            "message": "Voice login successful",
            "spoken_text": spoken_text,
            "similarity": similarity,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_data": {
                "id": user['id'],
                "email": user['email'],
                "voice_enabled": user['voice_enabled']
            }
        }
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    except Exception as e:
        print(f"Error in voice login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if audio_path and os.path.exists(audio_path):
            processor.cleanup(audio_path)

@router.get("/profile")
def get_profile(current_user: dict = Depends(get_current_user)):
    """Get voice profile information"""
    profile = get_voice_profile(current_user['id'])
    
    if not profile:
        return {
            "has_voice_profile": False,
            "message": "No voice profile found"
        }
    
    return {
        "has_voice_profile": True,
        "model_version": profile.get('model_version', 'v1'),
        "embedding_size": len(profile['embedding_vector']) if profile['embedding_vector'] else 0,
        "created_at": profile.get('created_at'),
        "updated_at": profile.get('updated_at')
    }

@router.get("/profile/update/challenge")
def update_profile_challenge(current_user: dict = Depends(get_current_user)):
    """Get challenge for updating voice profile"""
    if not current_user.get('voice_enabled', False):
        raise HTTPException(status_code=400, detail="Voice authentication not enabled. Enable it first.")
    
    # Generate new challenge
    challenge_text = security_manager.generate_challenge()
    challenge = create_challenge(current_user['id'], challenge_text)
    
    if not challenge:
        raise HTTPException(status_code=500, detail="Failed to create challenge")
    
    return {
        "challenge_text": challenge_text,
        "expires_in": 300,
        "is_update": True
    }

@router.post("/profile/update/verify")
async def update_profile_verify(
    audio: UploadFile = File(...),
    challenge_text: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Update voice profile for logged-in user"""
    if not validate_challenge(current_user['id'], challenge_text):
        raise HTTPException(status_code=400, detail="Invalid challenge")
    
    audio_bytes = await audio.read()
    valid, message, audio_path = processor.validate_recording(audio_bytes)
    
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    try:
        # Step 1: Verify speech matches challenge EXACTLY
        is_correct_speech, spoken_text, speech_message = speech_verifier.verify_challenge_speech(
            audio_path, challenge_text
        )
        
        if not is_correct_speech:
            raise HTTPException(status_code=400, detail=speech_message)
        
        # Step 2: Validate audio quality
        is_quality_ok, quality_message = audio_validator.validate(audio_path)
        if not is_quality_ok:
            raise HTTPException(status_code=400, detail=quality_message)
        
        # Step 3: Create embedding
        embedding = embedding_model.create_embedding(audio_path)
        
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to create voice embedding")
        
        # Update profile
        if not save_voice_profile(current_user['id'], embedding):
            raise HTTPException(status_code=500, detail="Failed to update profile")
        
        # Get updated user
        user = get_user_by_id(current_user['id'])
        
        return {
            "success": True,
            "message": "Voice profile updated successfully",
            "spoken_text": spoken_text,
            "user_data": {
                "id": user['id'],
                "email": user['email'],
                "voice_enabled": user['voice_enabled']
            }
        }
    finally:
        if audio_path:
            processor.cleanup(audio_path)

@router.post("/disable")
def disable_voice(
    password: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Disable voice authentication"""
    # Verify password
    if not verify_user(current_user['email'], password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    if disable_voice_auth(current_user['id']):
        return {
            "success": True,
            "message": "Voice authentication disabled"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to disable")

@router.get("/stats")
def get_stats(current_user: dict = Depends(get_current_user)):
    """Get voice authentication statistics"""
    security_status = rate_limiter.get_security_status(current_user['email'])
    
    return {
        "email": current_user['email'],
        "voice_enabled": current_user.get('voice_enabled', False),
        "security_status": security_status
    }

@router.post("/verify/challenge-speech")
async def verify_challenge_speech(
    audio: UploadFile = File(...),
    challenge_text: str = Form(...),
    email: Optional[str] = Form(None)  # Optional for signup
):
    """
    Verify that audio contains the exact challenge text.
    Used for real-time validation during signup.
    """
    audio_bytes = await audio.read()
    valid, message, audio_path = processor.validate_recording(audio_bytes)
    
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    
    try:
        # Step 1: Verify speech matches challenge EXACTLY
        is_correct_speech, spoken_text, speech_message = speech_verifier.verify_challenge_speech(
            audio_path, challenge_text
        )
        
        if not is_correct_speech:
            raise HTTPException(status_code=400, detail=speech_message)
        
        # Step 2: Validate audio quality
        is_quality_ok, quality_message = audio_validator.validate(audio_path)
        if not is_quality_ok:
            raise HTTPException(status_code=400, detail=quality_message)
        
        # Step 3: Create embedding for quality check (but don't save it yet)
        embedding = embedding_model.create_embedding(audio_path)
        
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to create voice embedding")
        
        # Return success with embedding for potential later use
        return {
            "success": True,
            "message": "Speech verification successful",
            "spoken_text": spoken_text,
            "embedding_created": True
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in challenge speech verification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if audio_path and os.path.exists(audio_path):
            processor.cleanup(audio_path)