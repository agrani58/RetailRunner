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
        
        # Refresh tokens table
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
        
        # Order confirmations table (for offline delivery)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_confirmations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                product_name VARCHAR(255) NOT NULL,
                delivery_date VARCHAR(100),
                order_id VARCHAR(100),
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered BOOLEAN DEFAULT FALSE
            )
        """)
        
        # NEW: User orders table (permanent order history)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                product_source VARCHAR(255) NOT NULL,
                store_frontend_url VARCHAR(255),
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_date VARCHAR(100),
                order_reference VARCHAR(100),
                reviewed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # NEW: Wishlist table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                product_source VARCHAR(255) NOT NULL,
                store_name VARCHAR(255),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, product_id)
            )
        """)
        
        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_confirmations_user ON order_confirmations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_order_confirmations_delivered ON order_confirmations(delivered)")
        
        # NEW: Indexes for user_orders and wishlist
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_orders_user ON user_orders(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id)")
        
        conn.commit()
        print("Database tables initialized successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def store_order_confirmation(user_id: int, product_name: str, delivery_date: str, order_id: str = None) -> bool:
    """Store an undelivered order confirmation message."""
    conn = get_db_connection()
    cur = conn.cursor()
    message = f"✅ Order confirmed for '{product_name}'. Expected delivery: {delivery_date}." + (f" Order ID: {order_id}" if order_id else "")
    try:
        cur.execute("""
            INSERT INTO order_confirmations (user_id, product_name, delivery_date, order_id, message)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, product_name, delivery_date, order_id, message))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error storing order confirmation: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_undelivered_confirmations(user_id: int) -> list:
    """Retrieve all undelivered confirmations for a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, product_name, delivery_date, order_id, message
            FROM order_confirmations
            WHERE user_id = %s AND delivered = FALSE
            ORDER BY created_at ASC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows] if rows else []
    except Exception as e:
        print(f"Error fetching undelivered confirmations: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def mark_confirmations_delivered(user_id: int, confirmation_ids: list):
    """Mark specific confirmations as delivered."""
    if not confirmation_ids:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE order_confirmations
            SET delivered = TRUE
            WHERE user_id = %s AND id = ANY(%s)
        """, (user_id, confirmation_ids))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error marking confirmations delivered: {e}")
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
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise ValueError("Email already exists")
        
        password_hash = hash_password(password)
        
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

# ---------- NEW FUNCTIONS FOR USER ORDERS ----------
def add_user_order(user_id: int, product_id: int, product_name: str, product_source: str,
                   store_frontend_url: str = None, delivery_date: str = None,
                   order_reference: str = None) -> bool:
    """Add a product to the user's permanent order history."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_orders (user_id, product_id, product_name, product_source,
                                     store_frontend_url, delivery_date, order_reference)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, product_id, product_name, product_source, store_frontend_url,
              delivery_date, order_reference))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error adding user order: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_user_orders(user_id: int) -> list:
    """Retrieve all orders for a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, product_id, product_name, product_source, store_frontend_url,
                   order_date, delivery_date, order_reference, reviewed
            FROM user_orders
            WHERE user_id = %s
            ORDER BY order_date DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows] if rows else []
    except Exception as e:
        print(f"Error fetching user orders: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def mark_order_reviewed(order_id: int) -> bool:
    """Mark a specific order as reviewed."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_orders SET reviewed = TRUE WHERE id = %s", (order_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error marking order reviewed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# ---------- NEW FUNCTIONS FOR WISHLIST ----------
def add_to_wishlist(user_id: int, product_id: int, product_name: str,
                    product_source: str, store_name: str = None) -> bool:
    """Add a product to the user's wishlist."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO wishlist (user_id, product_id, product_name, product_source, store_name)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, product_id) DO NOTHING
        """, (user_id, product_id, product_name, product_source, store_name))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error adding to wishlist: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def remove_from_wishlist(user_id: int, product_id: int) -> bool:
    """Remove a product from the user's wishlist."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM wishlist WHERE user_id = %s AND product_id = %s",
                    (user_id, product_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error removing from wishlist: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_wishlist(user_id: int) -> list:
    """Retrieve all items in the user's wishlist."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, product_id, product_name, product_source, store_name, added_at
            FROM wishlist
            WHERE user_id = %s
            ORDER BY added_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows] if rows else []
    except Exception as e:
        print(f"Error fetching wishlist: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def is_in_wishlist(user_id: int, product_id: int) -> bool:
    """Check if a product is already in the user's wishlist."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM wishlist WHERE user_id = %s AND product_id = %s",
                    (user_id, product_id))
        return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking wishlist: {e}")
        return False
    finally:
        cur.close()
        conn.close()