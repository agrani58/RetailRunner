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

# ---------- Chatbot settings (as class for backward compatibility) ----------
class Config:
    INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH", "models/intent/intent_classifier.pth")
    INTENT_MODEL_DIR = os.getenv("INTENT_MODEL_DIR", "models/intent")
    NER_MODEL_PATH = os.getenv("NER_MODEL_PATH", "models/spacy_product_ner")
    PRICE_RATING_MODEL_PATH = os.getenv("PRICE_RATING_MODEL_PATH", "models/price_rating_model")
    PRODUCTS_FILE = os.getenv("PRODUCTS_FILE", "data/products.json")
    ECOMMERCE_API_URLS = [url.strip() for url in os.getenv("ECOMMERCE_API_URLS", "").split(",") if url.strip()]
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

# Global config instance expected by chatbot modules
config = Config()