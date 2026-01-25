# backend/database/__init__.py
from .models import init_db
from .operations import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_user,
    create_refresh_token,
    get_refresh_token,
    revoke_refresh_token,
    enable_voice_auth,
    disable_voice_auth,
    save_voice_profile,
    get_voice_profile,
    create_challenge,
    validate_challenge
)

__all__ = [
    "init_db",
    "create_user",
    "get_user_by_email",
    "get_user_by_id",
    "verify_user",
    "create_refresh_token",
    "get_refresh_token",
    "revoke_refresh_token",
    "enable_voice_auth",
    "disable_voice_auth",
    "save_voice_profile",
    "get_voice_profile",
    "create_challenge",
    "validate_challenge"
]