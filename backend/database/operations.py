# backend/database/operations.py
import bcrypt
import json
from datetime import datetime, timedelta
from .connection import get_db_connection

# Helper functions
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# User operations
def create_user(email: str, password: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print(f"DEBUG: Checking if user exists: {email}")
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            print(f"DEBUG: User already exists: {email}")
            return None
        
        print(f"DEBUG: Creating user: {email}")
        cur.execute("""
            INSERT INTO users (email, password_hash, voice_enabled)
            VALUES (%s, %s, FALSE)
            RETURNING id, email, voice_enabled, created_at
        """, (email, hash_password(password)))
        
        user = cur.fetchone()
        conn.commit()
        print(f"DEBUG: User created successfully: {user}")
        return dict(user) if user else None
    except Exception as e:
        print(f"ERROR creating user: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_email(email: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, email, password_hash, voice_enabled, created_at
            FROM users WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"ERROR getting user by email: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_id(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, email, voice_enabled, created_at
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cur.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"ERROR getting user by id: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def verify_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        print(f"DEBUG: User not found for verification: {email}")
        return None
    
    if verify_password(password, user['password_hash']):
        print(f"DEBUG: Password verified for user: {email}")
        user.pop('password_hash', None)
        return user
    
    print(f"DEBUG: Password verification failed for user: {email}")
    return None

# Token operations
def create_refresh_token(user_id: int, token_hash: str, expires_at):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Delete any existing tokens for this user first
        cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        
        # Insert new token
        cur.execute("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (user_id, token_hash, expires_at))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR creating refresh token: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def get_refresh_token(token_hash: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT user_id, expires_at
            FROM refresh_tokens 
            WHERE token_hash = %s AND expires_at > NOW()
        """, (token_hash,))
        
        token = cur.fetchone()
        return dict(token) if token else None
    except Exception as e:
        print(f"ERROR getting refresh token: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def revoke_refresh_token(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR revoking refresh token: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

# Voice operations
def enable_voice_auth(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print(f"DEBUG: Enabling voice auth for user_id: {user_id}")
        cur.execute("""
            UPDATE users SET voice_enabled = TRUE
            WHERE id = %s
            RETURNING id, email, voice_enabled
        """, (user_id,))
        
        user = cur.fetchone()
        conn.commit()
        print(f"DEBUG: Voice auth enabled successfully: {user}")
        return dict(user) if user else None
    except Exception as e:
        print(f"ERROR enabling voice auth: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def disable_voice_auth(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("UPDATE users SET voice_enabled = FALSE WHERE id = %s", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR disabling voice auth: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def save_voice_profile(user_id: int, embedding: list):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Delete existing profile first
        cur.execute("DELETE FROM voice_profiles WHERE user_id = %s", (user_id,))
        
        # Insert new profile
        cur.execute("""
            INSERT INTO voice_profiles (user_id, embedding_vector)
            VALUES (%s, %s)
        """, (user_id, json.dumps(embedding)))
        conn.commit()
        print(f"DEBUG: Voice profile saved for user_id: {user_id}")
        return True
    except Exception as e:
        print(f"ERROR saving voice profile: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def get_voice_profile(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT embedding_vector, model_version
            FROM voice_profiles WHERE user_id = %s
        """, (user_id,))
        
        profile = cur.fetchone()
        return dict(profile) if profile else None
    except Exception as e:
        print(f"ERROR getting voice profile: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def create_challenge(user_id: int, challenge_text: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Clean expired challenges
        cur.execute("DELETE FROM voice_challenges WHERE expires_at < NOW()")
        
        expires_at = datetime.now() + timedelta(minutes=5)
        cur.execute("""
            INSERT INTO voice_challenges (user_id, challenge_text, expires_at)
            VALUES (%s, %s, %s)
            RETURNING id, challenge_text, expires_at
        """, (user_id, challenge_text, expires_at))
        
        challenge = cur.fetchone()
        conn.commit()
        return dict(challenge) if challenge else None
    except Exception as e:
        print(f"ERROR creating challenge: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def validate_challenge(user_id: int, challenge_text: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE voice_challenges 
            SET used = TRUE
            WHERE user_id = %s 
            AND challenge_text = %s 
            AND used = FALSE 
            AND expires_at > NOW()
            RETURNING id
        """, (user_id, challenge_text))
        
        challenge = cur.fetchone()
        conn.commit()
        return bool(challenge)
    except Exception as e:
        print(f"ERROR validating challenge: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()