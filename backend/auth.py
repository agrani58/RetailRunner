from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Header
from config import JWT_CONFIG
import database
import secrets
import hashlib

def create_access_token(data: dict):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_CONFIG["access_token_expire_minutes"])
    to_encode.update({"exp": expire, "type": "access"})
    
    return jwt.encode(
        to_encode,
        JWT_CONFIG["secret_key"],
        algorithm=JWT_CONFIG["algorithm"]
    )

def create_refresh_token(user_id: int):
    """Create refresh token"""
    try:
        token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=JWT_CONFIG["refresh_token_expire_days"])
        
        database.store_or_update_refresh_token(user_id, token_hash, expires_at)
        return token, expires_at
    except Exception:
        return None, None

def verify_access_token(token: str):
    """Verify JWT access token"""
    try:
        payload = jwt.decode(
            token,
            JWT_CONFIG["secret_key"],
            algorithms=[JWT_CONFIG["algorithm"]]
        )
        
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
            
        return int(payload.get("sub"))
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def verify_refresh_token(token: str):
    """Verify refresh token (plain token, not hash)"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    token_data = database.get_valid_refresh_token(token_hash)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    return token_data["user_id"]

async def get_current_user(authorization: str = Header(None)):
    """Extract and verify access token"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required"
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required"
            )
        
        user_id = verify_access_token(token)
        user = database.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )