import asyncio
import json
import logging
from search_engine import SearchEngine
from catalog_loader import load_products

logging.basicConfig(level=logging.INFO)

async def test():
    products = await load_products(force_refresh=False)
    print(f"Loaded {len(products)} products")
    if not products:
        print("❌ No products loaded!")
        return
    
    se = SearchEngine(products)
    
    # Test simple queries
    for query in ["laptops", "jackets", "tshort"]:
        print(f"\n🔍 Testing query: '{query}'")
        results = se.search(query=query, top_k=5)
        print(f"   Found {len(results)} results")
        for i, p in enumerate(results[:3]):
            print(f"   {i+1}. {p.get('name')} (${p.get('price')})")

if __name__ == "__main__":
    asyncio.run(test())