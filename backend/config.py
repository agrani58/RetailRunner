import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Config:
    """Application configuration – static + dynamic catalog settings."""

    # ---------- Model paths ----------
    INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH", "models/intent/intent_classifier.pth")
    INTENT_MODEL_DIR = os.getenv("INTENT_MODEL_DIR", "models/intent")
    NER_MODEL_PATH = os.getenv("NER_MODEL_PATH", "models/spacy_product_ner")
    PRICE_RATING_MODEL_PATH = os.getenv("PRICE_RATING_MODEL_PATH", "models/price_rating_model")
    PRODUCTS_FILE = os.getenv("PRODUCTS_FILE", "data/products.json")

    # ---------- Dynamic catalog settings ----------
    ECOMMERCE_API_URLS = os.getenv("ECOMMERCE_API_URLS", "").split(",")
    ECOMMERCE_API_URLS = [url.strip() for url in ECOMMERCE_API_URLS if url.strip()]
    REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "2500"))
    PRODUCTS_CACHE_FILE = os.getenv("PRODUCTS_CACHE_FILE", "data/products_cache.json")

    # ---------- Model settings ----------
    DEVICE = os.getenv("DEVICE", "cpu")
    MODEL_DEVICE = os.getenv("MODEL_DEVICE", "cpu")

    # ---------- Search settings ----------
    SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "10"))
    SEMANTIC_SEARCH_ENABLED = os.getenv("SEMANTIC_SEARCH_ENABLED", "true").lower() == "true"
    FUZZY_MATCHING_ENABLED = os.getenv("FUZZY_MATCHING_ENABLED", "true").lower() == "true"

    # ---------- API settings ----------
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate_paths(cls) -> Dict[str, bool]:
        """Validate that critical file paths exist."""
        results = {}
        for name, path in [
            ("Intent Model", cls.INTENT_MODEL_PATH),
            ("NER Model", cls.NER_MODEL_PATH),
            ("Price Rating Model", cls.PRICE_RATING_MODEL_PATH),
            ("Products File", cls.PRODUCTS_FILE),
            ("Products Cache", cls.PRODUCTS_CACHE_FILE),
        ]:
            exists = os.path.exists(path)
            results[name] = exists
            if exists:
                logger.info(f"✅ {name}: {path}")
            else:
                logger.warning(f"❌ {name} not found: {path}")
        return results

    @classmethod
    def validate(cls) -> bool:
        """Basic validation of dynamic catalog setup."""
        if not cls.ECOMMERCE_API_URLS:
            logger.warning("⚠️ No ECOMMERCE_API_URLS set – will only load from cache/static file.")
        return True

    @classmethod
    def get_model_info(cls) -> Dict[str, Any]:
        """Return configuration summary (for health checks)."""
        return {
            "intent_model": {
                "path": cls.INTENT_MODEL_PATH,
                "dir": cls.INTENT_MODEL_DIR,
                "exists": os.path.exists(cls.INTENT_MODEL_PATH),
                "device": cls.DEVICE,
            },
            "ner_model": {
                "path": cls.NER_MODEL_PATH,
                "exists": os.path.exists(cls.NER_MODEL_PATH),
            },
            "price_rating_model": {
                "path": cls.PRICE_RATING_MODEL_PATH,
                "exists": os.path.exists(cls.PRICE_RATING_MODEL_PATH),
            },
            "catalog": {
                "api_urls": cls.ECOMMERCE_API_URLS,
                "refresh_interval": cls.REFRESH_INTERVAL,
                "cache_file": cls.PRODUCTS_CACHE_FILE,
                "cache_exists": os.path.exists(cls.PRODUCTS_CACHE_FILE),
                "static_file": cls.PRODUCTS_FILE,
                "static_exists": os.path.exists(cls.PRODUCTS_FILE),
            },
            "search_settings": {
                "limit": cls.SEARCH_LIMIT,
                "semantic_search": cls.SEMANTIC_SEARCH_ENABLED,
                "fuzzy_matching": cls.FUZZY_MATCHING_ENABLED,
            },
        }

    @classmethod
    def print_config(cls):
        """Pretty‑print current configuration."""
        logger.info("=" * 60)
        logger.info("📋 CONFIGURATION")
        logger.info("=" * 60)
        info = cls.get_model_info()
        for category, settings in info.items():
            logger.info(f"\n📁 {category.replace('_', ' ').title()}:")
            for key, value in settings.items():
                if isinstance(value, bool):
                    status = "✅" if value else "❌"
                    logger.info(f"   {key}: {status}")
                else:
                    logger.info(f"   {key}: {value}")


# Global config instance – import this everywhere
config = Config()