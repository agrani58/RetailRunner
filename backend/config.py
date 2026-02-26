import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Database ----------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "retailrunner"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "admin"),
    "port": os.getenv("DB_PORT", "5432")
}

# ---------- JWT ----------
JWT_CONFIG = {
    "secret_key": os.getenv("JWT_SECRET_KEY", "7bb63a2a0d7c68407ebfb499c14cc26a582dd44ca9b624358aac4e7f8e7e6643"),
    "algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
    "access_token_expire_minutes": int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)),
    "refresh_token_expire_days": int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)),
}

# ---------- Chatbot settings ----------
class Config:
    INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH", "models/intent/intent_classifier.pth")
    INTENT_MODEL_DIR = os.getenv("INTENT_MODEL_DIR", "models/intent")
    NER_MODEL_PATH = os.getenv("NER_MODEL_PATH", "models/spacy_product_ner")
    PRICE_RATING_MODEL_PATH = os.getenv("PRICE_RATING_MODEL_PATH", "models/recommendation_model")
    PRODUCTS_FILE = os.getenv("PRODUCTS_FILE", "data/products.json")
    
    # Comma‑separated list of secure product API endpoints
    ECOMMERCE_API_URLS = [
        url.strip() for url in os.getenv("ECOMMERCE_API_URLS", "").split(",") 
        if url.strip() and url.strip().startswith("http")
    ]
    
    # API key for secure endpoints
    ECOMMERCE_API_KEY = os.getenv("ECOMMERCE_API_KEY", "MY_CHATBOT_SECRET_789")
    
    REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "2500"))
    PRODUCTS_CACHE_FILE = os.getenv("PRODUCTS_CACHE_FILE", "data/products_cache.json")
    DEVICE = os.getenv("DEVICE", "cpu")
    MODEL_DEVICE = os.getenv("MODEL_DEVICE", "cpu")
    SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "10"))
    SEMANTIC_SEARCH_ENABLED = os.getenv("SEMANTIC_SEARCH_ENABLED", "true").lower() == "true"
    FUZZY_MATCHING_ENABLED = os.getenv("FUZZY_MATCHING_ENABLED", "true").lower() == "true"
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()

# ---------- Frontend mapping for order bot ----------
# Maps API base URL (scheme://host:port) to store frontend base URL.
STORE_FRONTEND_MAP = {
    "http://100.30.70.54:5002/api/secure/products": "http://100.30.70.54",
    "http://44.219.130.221:5001/api/secure/products": "http://44.219.130.221",
    "http://98.87.208.115:5000/api/secure/products": "http://98.87.208.115",
}

# ---------- Store names for display ----------
# Maps full API endpoint URL to friendly store name.
STORE_NAMES = {
    "http://100.30.70.54:5002/api/secure/products": "SkinGlow",
    "http://44.219.130.221:5001/api/secure/products": "Urban Threads",
    "http://98.87.208.115:5000/api/secure/products": "Tech Haven",
}