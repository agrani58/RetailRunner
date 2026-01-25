# backend/voice/security.py
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class RateLimiter:
    """Rate limiting for voice authentication attempts"""
    
    def __init__(self, db_path: str = "voice_security.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """Initialize security database"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Create attempts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS voice_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                success INTEGER,
                similarity REAL,
                ip_address TEXT,
                audio_duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create rate limit table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                email TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                last_attempt TIMESTAMP,
                blocked_until TIMESTAMP
            )
        """)
        
        # Create indices for better performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_voice_attempts_email ON voice_attempts(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_voice_attempts_created_at ON voice_attempts(created_at)")
        
        conn.commit()
        conn.close()
    
    def check_rate_limit(self, email: str, ip_address: str) -> Tuple[bool, str]:
        """Check if request is rate limited"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Check if email is blocked
        cur.execute("""
            SELECT blocked_until FROM rate_limits 
            WHERE email = ? AND blocked_until > datetime('now')
        """, (email,))
        
        blocked = cur.fetchone()
        if blocked:
            conn.close()
            return False, "Too many attempts. Please try again later."
        
        # Count recent attempts
        five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        cur.execute("""
            SELECT COUNT(*) FROM voice_attempts 
            WHERE email = ? AND created_at > ? AND success = 0
        """, (email, five_min_ago))
        
        recent_failures = cur.fetchone()[0]
        
        if recent_failures >= 5:
            # Block for 5 minutes
            block_until = (datetime.now() + timedelta(minutes=5)).isoformat()
            cur.execute("""
                INSERT OR REPLACE INTO rate_limits (email, attempts, last_attempt, blocked_until)
                VALUES (?, ?, ?, ?)
            """, (email, recent_failures, datetime.now().isoformat(), block_until))
            conn.commit()
            conn.close()
            return False, "Too many failed attempts. Account temporarily locked."
        
        conn.close()
        return True, ""
    
    def log_attempt(self, user_id: Optional[int], email: str, success: bool, 
                   similarity: float, ip_address: str, audio_duration: float):
        """Log voice authentication attempt"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO voice_attempts 
            (user_id, email, success, similarity, ip_address, audio_duration)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email, 1 if success else 0, similarity, ip_address, audio_duration))
        
        # Update rate limits
        cur.execute("""
            INSERT OR REPLACE INTO rate_limits (email, attempts, last_attempt)
            VALUES (?, COALESCE((SELECT attempts + 1 FROM rate_limits WHERE email = ?), 1), ?)
        """, (email, email, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_security_status(self, email: str) -> Dict:
        """Get security status for an email"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Get recent attempts
        hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        cur.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                SUM(success) as successful_attempts,
                AVG(similarity) as avg_similarity
            FROM voice_attempts 
            WHERE email = ? AND created_at > ?
        """, (email, hour_ago))
        
        stats = cur.fetchone()
        
        # Get rate limit info
        cur.execute("SELECT blocked_until FROM rate_limits WHERE email = ?", (email,))
        blocked = cur.fetchone()
        
        conn.close()
        
        return {
            "total_attempts_last_hour": stats[0] if stats[0] else 0,
            "successful_attempts": stats[1] if stats[1] else 0,
            "avg_similarity": float(stats[2]) if stats[2] else 0,
            "blocked_until": blocked[0] if blocked else None,
            "success_rate": (stats[1] / stats[0] * 100) if stats[0] and stats[0] > 0 else 0
        }
    
    def clear_old_records(self, days: int = 30):
        """Clear old records to keep database size manageable"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cur.execute("DELETE FROM voice_attempts WHERE created_at < ?", (cutoff_date,))
        
        conn.commit()
        conn.close()