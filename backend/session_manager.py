from typing import Dict, Any, Optional
from datetime import datetime
import database
import json

class SessionManager:
    """Manages user session state"""
    
    @staticmethod
    def create_login_session(user: dict) -> Dict[str, Any]:
        """Create minimal session data for login"""
        return {
            "user": {
                "id": user.get("user_id"),
                "email": user.get("email")
            },
            "cart": [],  # Start with empty cart
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def create_logout_state() -> Dict[str, Any]:
        """Create clean logout state"""
        return {
            "user": None,
            "cart": [],
            "last_logout": datetime.now().isoformat()
        }
    
    @staticmethod
    def cleanup_pending_data(user_id: int):
        """Clean up any pending data (email changes, etc.)"""
        # No voice data to clean up anymore
        return True
    
    @staticmethod
    def validate_session_data(session_data: dict) -> bool:
        """Validate session data structure"""
        required_keys = ["user", "cart", "timestamp"]
        if not all(key in session_data for key in required_keys):
            return False
        
        user = session_data.get("user")
        if user and not all(key in user for key in ["id", "email"]):
            return False
        
        return True