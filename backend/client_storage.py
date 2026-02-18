from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ClientStorageSchema(BaseModel):
    """Schema for client-side storage"""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    cart: List[Dict[str, Any]] = []
    session_expiry: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJ...",
                "refresh_token": "abc...",
                "user": {
                    "id": 1,
                    "email": "user@example.com"
                },
                "cart": [],
                "session_expiry": "2024-01-01T00:00:00"
            }
        }

class StorageManager:
    """Manages what gets stored on client side"""
    
    @staticmethod
    def get_login_storage(access_token: str, refresh_token: str, user: dict) -> dict:
        """Get storage data for login"""
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.get("user_id"),
                "email": user.get("email")
            },
            "cart": [],  # Always start with empty cart on login
            "session_expiry": None  # Will be set by frontend
        }
    
    @staticmethod
    def get_logout_storage() -> dict:
        """Get storage data for logout"""
        return {
            "access_token": None,
            "refresh_token": None,
            "user": None,
            "cart": [],  # Clear cart on logout
            "session_expiry": None
        }
    
    @staticmethod
    def validate_storage(data: dict) -> bool:
        """Validate storage data structure"""
        try:
            # Check required structure
            if not isinstance(data, dict):
                return False
            
            # User should be either None or have required fields
            user = data.get("user")
            if user is not None:
                if not isinstance(user, dict):
                    return False
                if "id" not in user or "email" not in user:
                    return False
            
            # Cart should be a list
            cart = data.get("cart", [])
            if not isinstance(cart, list):
                return False
            
            return True
        except Exception:
            return False