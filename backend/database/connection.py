# backend/database/connection.py
import psycopg2
from psycopg2.extras import RealDictCursor
import config

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            cursor_factory=RealDictCursor
        )
        # Set autocommit to True to ensure immediate commits
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise