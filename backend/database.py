import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
import bcrypt
from datetime import datetime, timedelta

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Refresh tokens table with UNIQUE constraint on user_id
        cur.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        """)
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)")
        
        conn.commit()
        print("Database tables initialized successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    return password_hash.decode('utf-8')

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False

def create_user(email: str, password: str):
    """Create a new user"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user already exists
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise ValueError("Email already exists")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        cur.execute("""
            INSERT INTO users (email, password_hash)
            VALUES (%s, %s)
            RETURNING user_id, email, created_at
        """, (email, password_hash))
        
        user = cur.fetchone()
        conn.commit()
        
        if user:
            return dict(user)
        return None
        
    except psycopg2.IntegrityError:
        conn.rollback()
        raise ValueError("Email already exists")
    except Exception as e:
        conn.rollback()
        print(f"Create user error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_user_by_email(email: str):
    """Get user by email"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT user_id, email, password_hash, created_at
            FROM users WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"Get user by email error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_id(user_id: int):
    """Get user by ID"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT user_id, email, created_at
            FROM users WHERE user_id = %s
        """, (user_id,))
        
        user = cur.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"Get user by ID error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def verify_user_credentials(email: str, password: str):
    """Verify email and password"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT user_id, email, password_hash
            FROM users WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        if not user:
            return None
        
        user_dict = dict(user)
        
        if verify_password(password, user_dict['password_hash']):
            # Remove password hash from response
            del user_dict['password_hash']
            return user_dict
        
        return None
    except Exception as e:
        print(f"Verify credentials error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def store_or_update_refresh_token(user_id: int, token_hash: str, expires_at):
    """Store or update refresh token"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                token_hash = EXCLUDED.token_hash,
                expires_at = EXCLUDED.expires_at,
                created_at = CURRENT_TIMESTAMP
        """, (user_id, token_hash, expires_at))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Store refresh token error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_valid_refresh_token(token_hash: str):
    """Get valid refresh token"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT user_id, token_hash, expires_at
            FROM refresh_tokens 
            WHERE token_hash = %s AND expires_at > NOW()
        """, (token_hash,))
        
        token = cur.fetchone()
        return dict(token) if token else None
    except Exception as e:
        print(f"Get refresh token error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def revoke_refresh_token(user_id: int):
    """Revoke refresh token"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Revoke refresh token error: {e}")
        return False
    finally:
        cur.close()
        conn.close()