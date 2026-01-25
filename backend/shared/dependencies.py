# backend/shared/dependencies.py
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
from auth.auth_utils import verify_access_token
from database.operations import get_user_by_id

security = HTTPBearer()

async def get_current_user(authorization: str = Depends(security)):
    """Get current authenticated user"""
    try:
        token = authorization.credentials
        user_id = verify_access_token(token)
        user = get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")