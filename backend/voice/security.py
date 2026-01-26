import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import hashlib

logger = logging.getLogger("security_manager")

class RateLimiter:
    """Rate limiting for voice authentication attempts - STRICT VERSION"""
    
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
                email TEXT NOT NULL,
                success INTEGER DEFAULT 0,
                similarity REAL DEFAULT 0.0,
                challenge_text TEXT,
                spoken_text TEXT,
                verification_result TEXT,
                ip_address TEXT,
                user_agent TEXT,
                audio_duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create rate limit table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                email TEXT PRIMARY KEY,
                attempts_5min INTEGER DEFAULT 0,
                attempts_1hour INTEGER DEFAULT 0,
                failures_5min INTEGER DEFAULT 0,
                failures_1hour INTEGER DEFAULT 0,
                last_attempt TIMESTAMP,
                blocked_until TIMESTAMP,
                block_reason TEXT
            )
        """)
        
        # Create indices for better performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_voice_attempts_email ON voice_attempts(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_voice_attempts_created_at ON voice_attempts(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_voice_attempts_success ON voice_attempts(success)")
        
        conn.commit()
        conn.close()
    
    def get_client_fingerprint(self, request_headers: Dict) -> str:
        """Generate a client fingerprint from headers"""
        fingerprint_parts = []
        
        # Use various headers to create fingerprint
        headers_to_use = ['user-agent', 'accept-language', 'accept-encoding']
        for header in headers_to_use:
            if header in request_headers:
                fingerprint_parts.append(str(request_headers[header]))
        
        if fingerprint_parts:
            fingerprint = hashlib.sha256('|'.join(fingerprint_parts).encode()).hexdigest()
            return fingerprint
        
        return "unknown"
    
    def check_rate_limit(self, email: str, ip_address: str, request_headers: Dict = None) -> Tuple[bool, str]:
        """Check if request is rate limited - STRICT version"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        email = email.strip().lower()
        
        # Check if email is blocked
        cur.execute("""
            SELECT blocked_until, block_reason FROM rate_limits 
            WHERE email = ? AND blocked_until > datetime('now')
        """, (email,))
        
        blocked = cur.fetchone()
        if blocked:
            conn.close()
            block_time = datetime.fromisoformat(blocked[0])
            remaining = (block_time - datetime.now()).seconds // 60
            return False, f"Account temporarily locked. Try again in {remaining} minutes. Reason: {blocked[1]}"
        
        # Count attempts in last 5 minutes
        five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        cur.execute("""
            SELECT COUNT(*) FROM voice_attempts 
            WHERE email = ? AND created_at > ?
        """, (email, five_min_ago))
        
        attempts_5min = cur.fetchone()[0]
        
        # Count failures in last 5 minutes
        cur.execute("""
            SELECT COUNT(*) FROM voice_attempts 
            WHERE email = ? AND created_at > ? AND success = 0
        """, (email, five_min_ago))
        
        failures_5min = cur.fetchone()[0]
        
        # STRICT RATE LIMITING RULES
        if attempts_5min >= 10:  # 10 attempts in 5 minutes
            # Block for 30 minutes
            block_until = (datetime.now() + timedelta(minutes=30)).isoformat()
            cur.execute("""
                INSERT OR REPLACE INTO rate_limits 
                (email, attempts_5min, failures_5min, last_attempt, blocked_until, block_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, attempts_5min, failures_5min, datetime.now().isoformat(), 
                  block_until, "Too many attempts in 5 minutes"))
            conn.commit()
            conn.close()
            return False, "Too many attempts. Account locked for 30 minutes."
        
        if failures_5min >= 5:  # 5 failures in 5 minutes
            # Block for 15 minutes
            block_until = (datetime.now() + timedelta(minutes=15)).isoformat()
            cur.execute("""
                INSERT OR REPLACE INTO rate_limits 
                (email, attempts_5min, failures_5min, last_attempt, blocked_until, block_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, attempts_5min, failures_5min, datetime.now().isoformat(), 
                  block_until, "Too many failed attempts"))
            conn.commit()
            conn.close()
            return False, "Too many failed attempts. Account locked for 15 minutes."
        
        # Check for suspicious patterns (rapid consecutive failures)
        if failures_5min >= 3:
            # Get last 3 attempts
            cur.execute("""
                SELECT created_at FROM voice_attempts 
                WHERE email = ? AND success = 0 
                ORDER BY created_at DESC LIMIT 3
            """, (email,))
            
            attempts = cur.fetchall()
            if len(attempts) == 3:
                # Check if all within 1 minute
                first_time = datetime.fromisoformat(attempts[-1][0])
                last_time = datetime.fromisoformat(attempts[0][0])
                if (last_time - first_time).seconds < 60:
                    block_until = (datetime.now() + timedelta(minutes=10)).isoformat()
                    cur.execute("""
                        INSERT OR REPLACE INTO rate_limits 
                        (email, attempts_5min, failures_5min, last_attempt, blocked_until, block_reason)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (email, attempts_5min, failures_5min, datetime.now().isoformat(), 
                          block_until, "Suspicious rapid failures"))
                    conn.commit()
                    conn.close()
                    return False, "Suspicious activity detected. Account locked for 10 minutes."
        
        conn.close()
        return True, ""
    
    def log_attempt(self, user_id: Optional[int], email: str, success: bool, 
                   similarity: float, challenge_text: str, spoken_text: str,
                   verification_result: str, ip_address: str, audio_duration: float,
                   request_headers: Dict = None):
        """Log voice authentication attempt with detailed information"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        email = email.strip().lower()
        user_agent = request_headers.get('user-agent', '') if request_headers else ''
        
        cur.execute("""
            INSERT INTO voice_attempts 
            (user_id, email, success, similarity, challenge_text, spoken_text, 
             verification_result, ip_address, user_agent, audio_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, 1 if success else 0, similarity, challenge_text, 
              spoken_text, verification_result, ip_address, user_agent, audio_duration))
        
        # Update rate limits statistics
        now = datetime.now().isoformat()
        five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        hour_ago = (datetime.now() - timedelta(minutes=60)).isoformat()
        
        # Count recent attempts
        cur.execute("""
            SELECT 
                COUNT(*) as attempts_5min,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures_5min
            FROM voice_attempts 
            WHERE email = ? AND created_at > ?
        """, (email, five_min_ago))
        
        stats_5min = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as attempts_1hour,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures_1hour
            FROM voice_attempts 
            WHERE email = ? AND created_at > ?
        """, (email, hour_ago))
        
        stats_1hour = cur.fetchone()
        
        cur.execute("""
            INSERT OR REPLACE INTO rate_limits 
            (email, attempts_5min, attempts_1hour, failures_5min, failures_1hour, last_attempt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, 
              stats_5min[0] if stats_5min else 0,
              stats_1hour[0] if stats_1hour else 0,
              stats_5min[1] if stats_5min else 0,
              stats_1hour[1] if stats_1hour else 0,
              now))
        
        # If successful, clear any blocks
        if success:
            cur.execute("""
                UPDATE rate_limits 
                SET blocked_until = NULL, block_reason = NULL
                WHERE email = ?
            """, (email,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Logged voice attempt - Email: {email}, Success: {success}, "
                   f"Similarity: {similarity:.3f}, Challenge: {challenge_text}")
    
    def get_security_status(self, email: str) -> Dict:
        """Get security status for an email"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        email = email.strip().lower()
        
        # Get recent attempts (last hour)
        hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        cur.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                SUM(success) as successful_attempts,
                AVG(similarity) as avg_similarity,
                MIN(created_at) as first_attempt,
                MAX(created_at) as last_attempt
            FROM voice_attempts 
            WHERE email = ? AND created_at > ?
        """, (email, hour_ago))
        
        stats = cur.fetchone()
        
        # Get rate limit info
        cur.execute("""
            SELECT blocked_until, block_reason, attempts_5min, failures_5min 
            FROM rate_limits WHERE email = ?
        """, (email,))
        
        rate_limit = cur.fetchone()
        
        # Get last 5 attempts
        cur.execute("""
            SELECT success, similarity, challenge_text, spoken_text, 
                   verification_result, created_at
            FROM voice_attempts 
            WHERE email = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        """, (email,))
        
        recent_attempts = cur.fetchall()
        
        conn.close()
        
        # Calculate success rate
        total = stats[0] if stats and stats[0] else 0
        successful = stats[1] if stats and stats[1] else 0
        success_rate = (successful / total * 100) if total > 0 else 0
        
        return {
            "total_attempts_last_hour": total,
            "successful_attempts": successful,
            "success_rate": round(success_rate, 1),
            "avg_similarity": round(float(stats[2]), 3) if stats and stats[2] else 0,
            "first_attempt": stats[3] if stats else None,
            "last_attempt": stats[4] if stats else None,
            "blocked_until": rate_limit[0] if rate_limit else None,
            "block_reason": rate_limit[1] if rate_limit else None,
            "recent_attempts_5min": rate_limit[2] if rate_limit else 0,
            "recent_failures_5min": rate_limit[3] if rate_limit else 0,
            "recent_attempts": [
                {
                    "success": bool(attempt[0]),
                    "similarity": attempt[1],
                    "challenge": attempt[2],
                    "spoken": attempt[3],
                    "result": attempt[4],
                    "time": attempt[5]
                }
                for attempt in recent_attempts
            ]
        }
    
    def clear_old_records(self, days: int = 7):
        """Clear old records to keep database size manageable"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cur.execute("DELETE FROM voice_attempts WHERE created_at < ?", (cutoff_date,))
        
        # Also clear rate limits for emails with no recent attempts
        cur.execute("""
            DELETE FROM rate_limits 
            WHERE email NOT IN (
                SELECT DISTINCT email FROM voice_attempts 
                WHERE created_at > ?
            )
        """, (cutoff_date,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleaned up records older than {days} days")