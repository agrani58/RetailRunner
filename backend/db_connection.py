# db_connection.py 
import requests
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import json

load_dotenv()

class EcommerceAPI:
    def __init__(self):
        self.base_url = os.getenv("ECOMMERCE_API_URL", "http://localhost:5001")
        print(f"🔗 Connecting to eCommerce API at: {self.base_url}")
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        try:
            print(f" Fetching products from {self.base_url}/api/products")
            response = requests.get(f"{self.base_url}/api/products", timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Content Type: {response.headers.get('content-type')}")
            
            if response.status_code != 200:
                print(f"   ❌ API returned error: {response.status_code}")
                print(f"   Response text: {response.text[:200]}...")
                return self._get_sample_products()
            
            try:
                products_data = response.json()
                print(f"   ✅ Successfully parsed JSON, got {len(products_data)} products")
            except json.JSONDecodeError as e:
                print(f"   ❌ Failed to parse JSON: {e}")
                print(f"   Response text: {response.text[:500]}")
                return self._get_sample_products()

            transformed_products = []
            for product in products_data:
                transformed_products.append({
                    "id": product.get("id"),
                    "name": product.get("name", ""),
                    "price": float(product.get("price", 0)),
                    "rating": float(product.get("rating", 0)),
                    "category": product.get("category", ""),
                    "stock": product.get("stock", 0),
                    "image_url": product.get("image") or product.get("image_url", ""),
                    "description": product.get("description", ""),
                    "review_count": product.get("reviews") or product.get("review_count", 0)
                })
            
            print(f"   Transformed {len(transformed_products)} products")
            return transformed_products
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ API Connection Error: {e}")
            print("   Falling back to sample data...")
            return self._get_sample_products()
        except Exception as e:
            print(f"⚠️ Unexpected Error: {e}")
            import traceback
            traceback.print_exc()
            return self._get_sample_products()
    
    def _get_sample_products(self):
        """Sample products in case API is unavailable"""
        print("⚠️ Using sample data")
        return [
            {
                "id": 1,
                "name": "Blue Denim Jacket",
                "price": 45.99,
                "rating": 4.7,
                "category": "Jackets",
                "stock": 35,
                "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=300",
                "description": "Classic blue denim jacket, perfect for casual outings.",
                "review_count": 189
            },
            {
                "id": 2,
                "name": "White Summer Dress",
                "price": 39.99,
                "rating": 4.8,
                "category": "Dresses",
                "stock": 50,
                "image_url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=300",
                "description": "Light and breezy white summer dress with floral pattern.",
                "review_count": 245
            },
            {
                "id": 3,
                "name": "Leather Ankle Boots",
                "price": 79.99,
                "rating": 4.6,
                "category": "Footwear",
                "stock": 25,
                "image_url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=300",
                "description": "Genuine leather ankle boots for all seasons.",
                "review_count": 178
            },
            {
                "id": 4,
                "name": "Cashmere Sweater",
                "price": 89.99,
                "rating": 4.9,
                "category": "Sweaters",
                "stock": 40,
                "image_url": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=300",
                "description": "100% cashmere sweater, ultra soft and warm.",
                "review_count": 312
            },
            {
                "id": 5,
                "name": "Slim Fit Chinos",
                "price": 34.99,
                "rating": 4.5,
                "category": "Pants",
                "stock": 60,
                "image_url": "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=300",
                "description": "Comfortable slim fit chinos in multiple colors.",
                "review_count": 267
            },
            {
                "id": 6,
                "name": "Designer Handbag",
                "price": 129.99,
                "rating": 4.7,
                "category": "Accessories",
                "stock": 20,
                "image_url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=300",
                "description": "Premium designer handbag with multiple compartments.",
                "review_count": 156
            },
            {
                "id": 7,
                "name": "Cotton T-Shirt Pack",
                "price": 29.99,
                "rating": 4.4,
                "category": "T-Shirts",
                "stock": 100,
                "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=300",
                "description": "Pack of 3 basic cotton t-shirts in assorted colors.",
                "review_count": 421
            }
        ]