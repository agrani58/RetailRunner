import json
import os
import asyncio
import logging
import hashlib
from typing import List, Dict, Any
import httpx
from config import config

logger = logging.getLogger(__name__)

# PostgreSQL INTEGER max value
_PG_INT_MAX = 2_147_483_647


# ------------------------------------------------------------
# Fetch from a single API with API key header
# ------------------------------------------------------------
async def fetch_products_from_api(
    client: httpx.AsyncClient,
    api_url: str,
) -> List[Dict[str, Any]]:
    """Fetch products from a single e-commerce API endpoint with API key."""
    try:
        logger.info(f"🌐 Fetching {api_url}")
        headers = {"x-api-key": config.ECOMMERCE_API_KEY}
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

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


# ------------------------------------------------------------
# Stable ID assignment
# ------------------------------------------------------------
def assign_product_id(product: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Ensure each product has a consistent unique ID based on name + source.
    Result is always within PostgreSQL INTEGER range (1 to 2,147,483,647).
    """
    p = product.copy()
    name = p.get("name", "")
    source = p.get("source", "unknown")
    unique_str = f"{name}_{source}_{index}"
    hash_bytes = hashlib.md5(unique_str.encode()).digest()
    # Take first 4 bytes as unsigned int, then mod to stay within pg INTEGER range
    raw = int.from_bytes(hash_bytes[:4], "big")
    safe_id = (raw % _PG_INT_MAX) + 1  # keep in [1, PG_INT_MAX]

    p["id"] = safe_id
    p["original_id"] = product.get("id", index + 1)
    return p


# ------------------------------------------------------------
# Fetch ALL APIs concurrently
# ------------------------------------------------------------
async def fetch_all_products(api_urls: List[str]) -> List[Dict[str, Any]]:
    """Fetch products from all configured APIs concurrently."""
    if not api_urls:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = [
            fetch_products_from_api(client, url)
            for url in api_urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_products = []

    for idx, result in enumerate(results):
        url = api_urls[idx]

        if isinstance(result, Exception):
            logger.error(f"❌ Unexpected error fetching from {url}: {result}")
            continue

        for prod in result:
            prod["source"] = url
            all_products.append(prod)

    # Assign stable IDs
    validated = [
        assign_product_id(prod, i)
        for i, prod in enumerate(all_products)
    ]

    logger.info(f"📦 Total products fetched from APIs: {len(validated)}")
    return validated


# ------------------------------------------------------------
# Load products with fallback
# ------------------------------------------------------------
async def load_products() -> List[Dict[str, Any]]:
    """
    Fetch products from APIs using API key. Fall back to static file if no APIs or all fail.
    """
    api_urls = config.ECOMMERCE_API_URLS

    if api_urls:
        products = await fetch_all_products(api_urls)
        if products:
            return products
        else:
            logger.warning("⚠️ All API fetches failed. Falling back to static file.")
    else:
        logger.warning("⚠️ No API URLs configured. Using static file.")

    static_path = config.PRODUCTS_FILE

    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            products = json.load(f)

        logger.info(f"📁 Loaded {len(products)} products from static file: {static_path}")

        validated = []
        for i, prod in enumerate(products):
            prod["source"] = "static"
            if "id" not in prod:
                prod = assign_product_id(prod, i)
            validated.append(prod)

        return validated

    raise RuntimeError("❌ No products could be loaded – check API URLs or products.json")


# ------------------------------------------------------------
# Background refresh
# ------------------------------------------------------------
async def refresh_catalog_periodically(app_state: dict, interval: int):
    """Background refresh, updates product list and search engine."""
    while True:
        await asyncio.sleep(interval)
        logger.info("🔄 Starting periodic catalog refresh...")

        try:
            new_products = await load_products()
            current_products = app_state.get("products_data", [])

            current_ids = {p.get("id") for p in current_products}
            new_ids = {p.get("id") for p in new_products}

            if current_ids != new_ids:
                logger.info(
                    f"✨ Catalog changed! Old: {len(current_ids)} products, "
                    f"New: {len(new_ids)}"
                )

                app_state["products_data"] = new_products

                from search_engine import SearchEngine
                app_state["search_engine"] = SearchEngine(new_products)

                logger.info("✅ Search engine reinitialised with updated catalog.")
            else:
                logger.info("📦 No changes detected in product catalog.")

        except Exception as e:
            logger.error(f"❌ Refresh failed: {e}", exc_info=True)