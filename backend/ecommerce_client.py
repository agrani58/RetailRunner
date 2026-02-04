import os
import aiohttp
import json
from typing import Dict, List, Optional, Any
import logging
from dotenv import load_dotenv
import asyncio
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class ECommerceClient:
    """Client for interacting with Urban Threads e-commerce API"""
    
    def __init__(self):
        load_dotenv()
        # Get store URL from environment
        store_urls = os.getenv("ECOMMERCE_URLS", "http://localhost:5001")
        self.base_urls = [url.strip() for url in store_urls.split(",") if url.strip()]
        self.session = None
        logger.info(f"ECommerceClient initialized with stores: {self.base_urls}")
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def check_connection(self) -> Dict[str, str]:
        """Check if e-commerce API is reachable"""
        results = {}
        session = await self.get_session()
        
        for base_url in self.base_urls:
            try:
                # Try to connect to the API
                async with session.get(f"{base_url}/api/products", timeout=5) as response:
                    if response.status == 200:
                        results[base_url] = "connected"
                    else:
                        results[base_url] = f"error: {response.status}"
            except Exception as e:
                results[base_url] = f"error: {str(e)[:50]}"
        
        return results
    
    async def search_products(self, params: Dict[str, Any]) -> List[Dict]:
        """Search products from Urban Threads"""
        try:
            session = await self.get_session()
            
            # Search all stores in parallel
            tasks = []
            for base_url in self.base_urls:
                task = self._search_single_store(session, base_url, params.copy())
                tasks.append(task)
            
            # Wait for all stores to respond
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine all products
            all_products = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error searching store {self.base_urls[i]}: {result}")
                    continue
                
                if result:
                    all_products.extend(result)
            
            logger.info(f"Found {len(all_products)} products from all stores")
            return all_products
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def _search_single_store(self, session: aiohttp.ClientSession, base_url: str, params: Dict) -> List[Dict]:
        """Search products from a single store"""
        try:
            # Prepare search parameters for Urban Threads API
            search_params = {}
            
            # Map our params to Urban Threads API params
            if "q" in params:
                search_params["q"] = params["q"]
            if "category" in params:
                search_params["category"] = params["category"]
            if "min_price" in params:
                search_params["min_price"] = params["min_price"]
            if "max_price" in params:
                search_params["max_price"] = params["max_price"]
            if "limit" in params:
                search_params["limit"] = params["limit"]
            
            # Urban Threads endpoints to try (in order of preference)
            endpoints_to_try = [
                "/api/products/search",
                "/api/products"
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    url = urljoin(base_url, endpoint)
                    logger.info(f"Searching {url} with params: {search_params}")
                    
                    async with session.get(url, params=search_params, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Got response from {url}")
                            
                            # Format products for our frontend
                            formatted_products = self._format_store_products(data, base_url)
                            return formatted_products
                        elif response.status == 404:
                            # Try next endpoint
                            continue
                        else:
                            logger.warning(f"Store {base_url} returned status {response.status}")
                            continue
                            
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout for endpoint {endpoint} on {base_url}")
                    continue
                except Exception as e:
                    logger.warning(f"Error for endpoint {endpoint} on {base_url}: {e}")
                    continue
            
            logger.warning(f"All endpoints failed for store {base_url}")
            return []
            
        except Exception as e:
            logger.error(f"Error searching {base_url}: {e}")
            return []
    
    def _format_store_products(self, data: Any, base_url: str) -> List[Dict]:
        """Format Urban Threads products for our frontend"""
        formatted_products = []
        
        # Extract products array from response
        products = []
        if isinstance(data, list):
            products = data
        elif isinstance(data, dict):
            if "products" in data:
                products = data["products"]
            elif "items" in data:
                products = data["items"]
        
        logger.info(f"Formatting {len(products)} products from {base_url}")
        
        for product in products:
            try:
                # Extract product data with fallbacks
                product_id = str(product.get("id", product.get("_id", "")))
                name = product.get("name", product.get("title", "Unknown Product")).strip()
                
                # Price handling
                price = 0.0
                price_raw = product.get("price", product.get("unit_price", 0))
                if isinstance(price_raw, (int, float)):
                    price = float(price_raw)
                elif isinstance(price_raw, str):
                    try:
                        price_str = price_raw.replace('$', '').replace(',', '').strip()
                        price = float(price_str)
                    except:
                        price = 0.0
                
                # Rating handling
                rating = 0.0
                rating_raw = product.get("rating", product.get("average_rating", 0))
                if isinstance(rating_raw, (int, float)):
                    rating = float(rating_raw)
                elif isinstance(rating_raw, str):
                    try:
                        rating = float(rating_raw)
                    except:
                        rating = 0.0
                
                # Review count handling
                review_count = 0
                reviews_raw = product.get("review_count", product.get("reviews", 0))
                if isinstance(reviews_raw, (int, float)):
                    review_count = int(reviews_raw)
                elif isinstance(reviews_raw, str):
                    try:
                        review_count = int(reviews_raw)
                    except:
                        review_count = 0
                
                # Category handling
                category = product.get("category", "General")
                
                # Stock handling
                stock = 0
                stock_raw = product.get("stock", product.get("quantity", 0))
                if isinstance(stock_raw, (int, float)):
                    stock = int(stock_raw)
                elif isinstance(stock_raw, str):
                    try:
                        stock = int(stock_raw)
                    except:
                        stock = 0
                
                # Image URL handling
                image_url = product.get("image_url") or product.get("image") or product.get("imageUrl", "")
                
                # Description
                description = product.get("description", "")
                
                # Brand extraction
                brand = product.get("brand", "")
                
                # Product URL
                product_url = product.get("url", f"{base_url}/product/{product_id}")
                
                formatted_product = {
                    "id": product_id,
                    "name": name,
                    "price": round(price, 2),
                    "rating": min(max(rating, 0), 5),
                    "review_count": max(review_count, 0),
                    "category": str(category),
                    "stock": max(stock, 0),
                    "image_url": image_url if image_url else self._generate_placeholder_image(name),
                    "description": str(description)[:200] + "..." if len(str(description)) > 200 else str(description),
                    "brand": brand,
                    "url": product_url,
                    "store": base_url,
                    "store_type": "fashion",
                    "match_percentage": 0.0
                }
                
                formatted_products.append(formatted_product)
                
            except Exception as e:
                logger.error(f"Error formatting product: {e}")
                continue
        
        return formatted_products
    
    def _generate_placeholder_image(self, product_name: str) -> str:
        """Generate placeholder image URL"""
        encoded_name = product_name[:20].replace(' ', '+')
        return f"https://placehold.co/300x300/f7f0e8/1e1b18?text={encoded_name}"