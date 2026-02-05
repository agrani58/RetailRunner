import aiohttp
import asyncio
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class ECommerceClient:
    def __init__(self):
        self.base_urls = {
            "urban_threads": "http://localhost:5001/api/"
        }
        self.session = None

    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def check_connection(self) -> Dict[str, str]:
        results = {}

        for store_name, base_url in self.base_urls.items():
            try:
                session = await self.get_session()
                health_url = urljoin(base_url, "health")

                async with session.get(health_url, timeout=5) as response:
                    if response.status == 200:
                        results[store_name] = "connected"
                    else:
                        results[store_name] = f"error: {response.status}"

            except Exception as e:
                results[store_name] = f"error: {str(e)}"

        return results

    async def search_products(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        all_products = []

        for store_name, base_url in self.base_urls.items():
            try:
                products = await self._search_store(base_url, store_name, params)
                all_products.extend(products)

            except Exception as e:
                logger.error(f"Error searching {store_name}: {e}")
                continue

        logger.info(f"Found {len(all_products)} products from all stores")
        return all_products

    async def _search_store(
        self,
        base_url: str,
        store_name: str,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:

        session = await self.get_session()
        search_url = urljoin(base_url, "products/search")

        logger.info(f"Searching {search_url} with params: {params}")

        try:
            clean_params = {k: v for k, v in params.items() if v is not None}

            async with session.get(
                search_url,
                params=clean_params,
                timeout=15
            ) as response:

                if response.status != 200:
                    logger.error(
                        f"{store_name} returned status {response.status}"
                    )
                    return []

                data = await response.json()

                # 🔥 Handle BOTH response formats
                if isinstance(data, dict):
                    products = data.get("products", [])
                elif isinstance(data, list):
                    products = data
                else:
                    logger.error(
                        f"Unexpected response format from {store_name}: {type(data)}"
                    )
                    return []

                logger.info(f"Got {len(products)} products from {store_name}")

                return self._format_products(products, store_name)

        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to store {store_name}")
            return []

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error connecting to {store_name}: {e}")
            return []

        except Exception as e:
            logger.error(f"Error connecting to store {store_name}: {e}")
            return []

    def _format_products(
        self,
        raw_products: List[Dict],
        store_name: str
    ) -> List[Dict[str, Any]]:

        formatted_products = []

        for product in raw_products:
            try:
                # -------- PRICE EXTRACTION --------
                price = 0.0
                price_fields = [
                    "price",
                    "current_price",
                    "sale_price",
                    "regular_price"
                ]

                for field in price_fields:
                    if field in product and product[field] is not None:
                        try:
                            price = float(product[field])
                            break
                        except (ValueError, TypeError):
                            continue

                # -------- IMAGE EXTRACTION --------
                image_url = ""
                image_fields = [
                    "image_url",
                    "image",
                    "thumbnail",
                    "product_image",
                    "img_url",
                    "picture"
                ]

                for field in image_fields:
                    if field in product and product[field]:
                        image_url = product[field]
                        break

                if image_url and not image_url.startswith(
                    ("http://", "https://")
                ):
                    if image_url.startswith("/"):
                        image_url = f"http://localhost:5001{image_url}"

                formatted = {
                    "id": str(
                        product.get("id", product.get("_id", ""))
                    ),
                    "name": product.get(
                        "name",
                        product.get("title", "Unknown Product")
                    ),
                    "price": price,
                    "rating": float(
                        product.get(
                            "rating",
                            product.get("avg_rating", 0)
                        )
                    ),
                    "review_count": int(
                        product.get(
                            "review_count",
                            product.get("reviews", 0)
                        )
                    ),
                    "category": product.get(
                        "category",
                        product.get("type", "Unknown")
                    ),
                    "stock": int(
                        product.get(
                            "stock",
                            product.get("quantity", 0)
                        )
                    ),
                    "image_url": image_url,
                    "description": product.get(
                        "description",
                        product.get("desc", "")
                    ),
                    "brand": product.get(
                        "brand",
                        product.get("manufacturer", "")
                    ),
                    "url": product.get(
                        "url",
                        product.get("product_url", "")
                    ),
                    "store": store_name,
                    "store_type": "urban",
                    "match_percentage": 0.0
                }

                formatted_products.append(formatted)

            except Exception as e:
                logger.error(f"Error formatting product: {e}")
                continue

        return formatted_products
