import json
import os
import asyncio
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
from config import config

logger = logging.getLogger(__name__)


async def fetch_products_from_api(api_url: str) -> List[Dict[str, Any]]:
    """Fetch products from a single e‑commerce API endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json()
            # Assume the API returns a list of products directly, or under a 'products' key
            if isinstance(data, list):
                products = data
            elif isinstance(data, dict) and "products" in data:
                products = data["products"]
            else:
                logger.warning(f"Unexpected JSON format from {api_url}: {type(data)}")
                products = []
            logger.info(f"✅ Fetched {len(products)} products from {api_url}")
            return products
    except Exception as e:
        logger.error(f"❌ Failed to fetch from {api_url}: {e}")
        return []


def assign_product_id(product: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Ensure each product has a consistent unique ID based on name + source."""
    p = product.copy()
    name = p.get("name", "")
    source = p.get("source", "unknown")
    unique_str = f"{name}_{source}_{index}"
    hash_val = hashlib.md5(unique_str.encode()).hexdigest()[:12]
    p["id"] = int(hash_val, 16) if hash_val else index + 1
    p["original_id"] = product.get("id", index + 1)
    return p


async def fetch_all_products(api_urls: List[str]) -> List[Dict[str, Any]]:
    """Fetch products from all configured APIs concurrently."""
    tasks = [fetch_products_from_api(url) for url in api_urls if url.strip()]
    results = await asyncio.gather(*tasks)

    all_products = []
    for idx, product_list in enumerate(results):
        source = api_urls[idx] if idx < len(api_urls) else f"source_{idx}"
        for prod in product_list:
            prod["source"] = source  # tag with source URL for traceability
            all_products.append(prod)

    # Assign stable IDs
    validated = []
    for i, prod in enumerate(all_products):
        validated.append(assign_product_id(prod, i))

    logger.info(f"📦 Total products fetched: {len(validated)}")
    return validated


def save_products_cache(products: List[Dict[str, Any]], cache_path: str):
    """Save products to local JSON cache."""
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Products cached to {cache_path}")


def load_products_cache(cache_path: str) -> Optional[List[Dict[str, Any]]]:
    """Load products from local JSON cache if it exists."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                products = json.load(f)
            logger.info(f"📂 Loaded {len(products)} products from cache: {cache_path}")
            return products
        except Exception as e:
            logger.error(f"❌ Failed to load cache: {e}")
    return None


# ------------------------------------------------------------
# Public API – called from main.py
# ------------------------------------------------------------
async def load_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Main entry point:
    - If force_refresh or no cache, fetch from APIs.
    - Otherwise load from cache.
    """
    cache_path = config.PRODUCTS_CACHE_FILE
    api_urls = config.ECOMMERCE_API_URLS

    # 1. Try cache first (unless force_refresh)
    if not force_refresh:
        cached = load_products_cache(cache_path)
        if cached:
            return cached

    # 2. Fetch from APIs (or fallback to products.json)
    if api_urls and api_urls != [""]:
        products = await fetch_all_products(api_urls)
        if products:
            save_products_cache(products, cache_path)
            return products
        else:
            logger.warning("⚠️ No products fetched from APIs, falling back to static file.")

    # 3. Final fallback: load from static products.json
    static_path = config.PRODUCTS_FILE
    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            products = json.load(f)
        logger.info(f"📁 Loaded {len(products)} products from static file: {static_path}")
        # Assign IDs if missing
        validated = []
        for i, prod in enumerate(products):
            if "id" not in prod:
                prod = assign_product_id(prod, i)
            validated.append(prod)
        return validated

    # 4. Nothing – fatal
    raise RuntimeError("❌ No products could be loaded – check API URLs or products.json")


# ------------------------------------------------------------
# Background refresh task (called from main.py lifespan)
# ------------------------------------------------------------
async def refresh_catalog_periodically(app_state: dict, interval: int):
    """
    Runs in background, updates the global product list and reinitializes
    the search engine when changes are detected.
    """
    while True:
        await asyncio.sleep(interval)
        logger.info("🔄 Starting periodic catalog refresh...")
        try:
            new_products = await fetch_all_products(config.ECOMMERCE_API_URLS)
            if not new_products:
                logger.warning("⚠️ Refresh fetched 0 products, keeping old catalog.")
                continue

            # Compare with current products (by ID set)
            current_products = app_state.get("products_data", [])
            current_ids = {p.get("id") for p in current_products}
            new_ids = {p.get("id") for p in new_products}

            if current_ids != new_ids:
                logger.info(f"✨ Catalog changed! Old: {len(current_ids)} products, New: {len(new_ids)}")
                # Update state
                app_state["products_data"] = new_products
                save_products_cache(new_products, config.PRODUCTS_CACHE_FILE)

                # Re‑initialize search engine with new products
                from search_engine import SearchEngine
                app_state["search_engine"] = SearchEngine(new_products)
                logger.info("✅ Search engine reinitialised with updated catalog.")
            else:
                logger.info("📦 No changes detected in product catalog.")
        except Exception as e:
            logger.error(f"❌ Refresh failed: {e}", exc_info=True)