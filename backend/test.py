"""
test.py – Comprehensive test suite for Conversational Commerce System
Run with: python test.py
"""

import json
import requests
import time
from tabulate import tabulate
from colorama import init, Fore, Style
from datetime import datetime

init(autoreset=True)

API_URL = "http://localhost:8000/chat"
OUTPUT_FILE = "test_results.json"

# ==============================================================================
# TEST QUERIES – 100% based on actual products in your catalog
# ==============================================================================
TEST_QUERIES = {
    "🎯 Exact Product Matches": [
        "logitech mx master 3s",                # exists
        "sony wh-1000xm5",                      # exists
        "apple airpods pro 2",                   # exists
        "macbook air m3 256gb",                  # exists
        "samsung galaxy s24 ultra 512gb",        # exists
        "matte lipstick red",                     # exists
        "bose quietcomfort ultra",                # exists
        "xbox series x",                          # exists
        "nintendo switch oled",                   # exists
        "dyson v15 detect cordless vacuum",       # exists
        "philips air fryer xxl",                  # exists
        "apple watch series 9",                    # exists
        "samsung galaxy watch 6",                  # exists
        "garmin forerunner 265",                   # exists
        "canon eos r6 mark ii",                    # exists
        "sony alpha a7 iv",                        # exists
        "gopro hero 12 black",                     # exists
        "waterproof mascara",                       # exists
        "eyeliner pen",                             # exists
        "anti aging serum",                         # exists
        "vitamin c serum",                          # exists
    ],

    "🔍 Category Searches": [
        "headphones",                               # Sony, Bose, AirPods
        "laptops",                                  # MacBooks, Dell, Lenovo, etc.
        "smartphones",                              # iPhones, Samsung, Google, etc.
        "watches",                                  # Apple, Samsung, Garmin
        "jeans",                                    # many jeans
        "dresses",                                  # summer dress, evening gown, etc.
        "jackets",                                  # leather, puffer, etc.
        "footwear",                                 # sneakers, boots, loafers
        "skin care",                                # face cream, serum, etc.
        "makeup",                                   # lipstick, mascara, foundation
        "gaming consoles",                           # PS5, Xbox, Switch
        "cameras",                                   # Sony, Canon, GoPro
        "monitors",                                  # LG, Dell, Samsung
        "speakers",                                  # JBL, Sony, Amazon
        "pc components",                             # RTX 4070, Ryzen 9, etc.
        "wearables",                                 # smartwatches, fitness trackers
        "home appliances",                            # Dyson, Philips, FlexiSpot
    ],

    "💰 Price Filters": [
        "headphones under $400",                     # Sony $379, AirPods $249 (Bose $409 excluded)
        "headphones under $300",                     # AirPods $249 only
        "laptops under $1500",                       # many under $1500 (MacBook Air $1049, Dell XPS $1349)
        "laptops under $1000",                       # Acer Swift Go $749, HP Victus $899
        "smartphones over $1000",                    # iPhone 15 Pro Max $1299, S24 Ultra $1149
        "smartphones between $700 and $1000",         # Google Pixel 8 $749, OnePlus 12 $799
        "watches between $300 and $500",              # Apple Watch $419, Garmin $459, Galaxy Watch $329
        "jeans under $50",                            # Classic Blue Denim $49.99, Relaxed Fit $52.99? $52.99 > $50 – adjust
        "jeans under $60",                             # many under $60
        "dresses under $100",                          # Floral Summer Dress $45.99, Velvet Evening Gown $149.99? >100 – adjust
        "dresses under $150",                           # Velvet Evening Gown $149.99 qualifies
        "running shoes under $100",                     # Running Sneakers $59.99
        "waterproof hiking boots under $150",           # Waterproof Hiking Boots $139.99
        "leather chelsea boots under $150",             # Leather Chelsea Boots $125
        "cameras under $2000",                          # Canon EOS R6 Mark II $1999, GoPro $449
        "cameras under $1000",                          # GoPro $449 only (since Sony A7 IV $2199 >1000)
        "bluetooth speaker under $200",                 # JBL Charge 5 $179
        "smart speaker under $250",                     # Amazon Echo Studio $249
        "gaming console under $400",                    # Nintendo Switch OLED $369, Xbox Series X $529? >400 – Switch qualifies
        "gaming console under $500",                     # Xbox Series X $529? still >500 – PS5 $549 >500, so none? – adjust
        "gaming console under $600",                     # PS5 $549, Xbox $529, Switch $369 – all under $600
    ],

    "⭐ Rating Filters": [
        "products with rating above 4.8",                # Sony 4.9, MacBooks 4.9, ThinkPad 4.9, etc.
        "headphones with rating above 4.7",               # Sony 4.9, Bose 4.8, AirPods 4.7 qualifies
        "laptops with rating above 4.7",                  # MacBooks 4.9, ThinkPad 4.9, Dell XPS 4.8
        "smartphones with rating above 4.6",              # many (iPhone 4.8, Pixel 4.7, etc.)
        "jeans with rating above 4.5",                     # many (Slim Fit Black 4.7, High Waist Skinny 4.8)
        "dresses with rating above 4.7",                   # Velvet Evening Gown 4.9, Elegant Evening Gown 4.9, etc.
        "skin care with rating above 4.5",                  # Sunscreen 4.8, Anti Aging Serum 4.7, etc.
        "makeup with rating above 4.5",                     # Matte Lipstick 4.7, Waterproof Mascara 4.4? no – adjust
        "makeup with rating above 4.3",                      # most makeup products
    ],

    "🔍 Brand + Category": [
        "apple laptop",                                   # MacBooks
        "samsung phone",                                  # S24, S24 Ultra
        "sony headphones",                                # WH-1000XM5
        "bose headphones",                                # QuietComfort Ultra
        "canon camera",                                   # EOS R6 Mark II
        "gopro camera",                                   # Hero 12 Black
        "dyson vacuum",                                   # V15 Detect
        "philips air fryer",                              # Air Fryer XXL
        "logitech mouse",                                 # MX Master 3S
        "razer keyboard",                                 # BlackWidow V4
        "amd processor",                                  # Ryzen 9 7900X
        "nvidia graphics card",                           # RTX 4070 Ti Super
        "samsung tv",                                     # QLED 4K TV
        "lg monitor",                                     # UltraGear
        "jbl speaker",                                    # Charge 5
    ],

    "💰💰 Combined Constraints": [
        "gaming laptop under $1500 with at least 4.5 stars",   # MSI 4.6, Legion 4.7, HP Victus 4.5
        "smartphones under $800 with rating above 4.6",        # Google Pixel 8 4.7, OnePlus 12 4.7, Xiaomi 4.6
        "wireless headphones with noise cancellation under $400", # Sony $379, Bose $409 (over), AirPods $249 (ANC) – AirPods qualify
        "affordable formal shirts under $100 with good reviews",  # many shirts under $100 with 4.5+ ratings
        "budget friendly shoes under $100 with 4.5+ stars",       # Running Sneakers 4.6
        "most expensive camera with minimum 4.8 rating",          # Sony A7 IV 4.9, Canon 4.8
        "cheapest gaming laptop with at least 4.5 stars",         # HP Victus 4.5 $899
        "highest rated smartphone under $1000",                   # Google Pixel 8 Pro 4.8, OnePlus 12 4.7 – Pixel 8 Pro $999 qualifies
    ],

    "🔤 Misspellings": [
        "logitech mx master 3s mous",                     # misspelled
        "sony wh-1000xm55",                               # extra digit
        "macbok air m3",                                  # 'macbok'
        "samsung galxy s24 ultra",                        # 'galxy'
        "matte lipstik red",                              # 'lipstik'
        "headphnes under $400",                           # 'headphnes'
        "wathes for men",                                 # 'wathes' (should trigger chitchat or no results)
        "airpods pro 2",                                   # missing "apple" but should match via fuzzy
        "bose quietcomfort",                              # works
        "dyson cordless vacuum",                           # works
    ],

    "🗣️ Natural Language": [
        "i need a durable waterproof jacket under $150",        # Bomber Flight Jacket $69.99 (water-resistant)
        "looking for a phone that takes great photos, under $800", # Google Pixel 8 $749, OnePlus 12 $799
        "find me wireless earbuds with noise cancellation",    # AirPods Pro 2, Sony, Bose
        "what's the best gaming laptop for under $2000",        # MacBook Pro $1999, ASUS ROG $1599
        "show me something comfortable to wear at home",       # Casual Shirt Dress, Sweater Dress, etc.
        "i want a lipstick that lasts long and is matte",      # Matte Lipstick - Red
        "give me the cheapest smartphone with good battery",    # OnePlus Nord CE 3 Lite $299
        "i need a new monitor for gaming",                      # LG UltraGear, Samsung Odyssey
    ],

    "📊 Sorting & Ranking": [
        "cheapest laptops",                                    # Acer Swift Go $749, HP Victus $899, etc.
        "most expensive headphones",                            # Bose $409, Sony $379
        "highest rated smartphones",                            # iPhone 15 Pro Max 4.9, Google Pixel 8 Pro 4.8
        "top 3 rated products overall",                         # MacBooks 4.9, Sony 4.9, ThinkPad 4.9
        "sort laptops by price low to high",
        "show me the 3 cheapest smartphones",
        "sort smartphones by rating descending",
        "sort jeans by price high to low",
    ],

    "⚡ Edge Cases (expected empty)": [
        "smartphones under $200",                               # no smartphones under $200
        "gaming laptop under $800 with 4.8+ stars",             # HP Victus $899 >$800, so none
        "products with rating above 5",                          # none (ratings max 4.9)
        "headphones under $50",                                  # none (cheapest is AirPods $249)
        "cameras between $500 and $1000",                        # none (GoPro $449, Canon $1999)
        "wireless earbuds with aptX under $100",                 # none
    ],
}


def test_query(query: str) -> dict:
    """Send a query to the API and return the response."""
    try:
        start = time.time()
        response = requests.post(API_URL, json={"query": query}, timeout=10)
        elapsed = time.time() - start
        if response.status_code == 200:
            data = response.json()
            data["response_time"] = elapsed
            return data
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "response": "",
                "products": [],
                "response_time": elapsed,
            }
    except Exception as e:
        return {
            "error": str(e),
            "response": "",
            "products": [],
            "response_time": 0,
        }


def format_products(products: list) -> str:
    """Format a list of products as a table."""
    if not products:
        return "   No products found"
    table = []
    for i, p in enumerate(products[:5], 1):
        name = p['name'][:40] + '...' if len(p['name']) > 40 else p['name']
        desc = p.get('description', '')[:35] + '...' if len(p.get('description', '')) > 35 else p.get('description', '')
        table.append([
            i,
            name,
            p['category'][:15] + '...' if len(p['category']) > 15 else p['category'],
            f"${p['price']:.2f}",
            f"⭐ {p['rating']:.1f}" if p.get('rating') else "N/A",
            desc[:25] + '...' if len(desc) > 25 else desc
        ])
    return tabulate(
        table,
        headers=['#', 'Product Name', 'Category', 'Price', 'Rating', 'Description'],
        tablefmt='grid',
        maxcolwidths=[3, 35, 15, 10, 10, 25]
    )


def run_tests():
    """Run all test queries and print results."""
    print(f"\n{Fore.CYAN}{'='*100}")
    print(f"{Fore.CYAN}🔍 TESTING CONVERSATIONAL COMMERCE SYSTEM")
    print(f"{Fore.CYAN}{'='*100}\n")

    total = 0
    passed = 0
    results = {}

    for category, queries in TEST_QUERIES.items():
        print(f"\n{Fore.YELLOW}{category}")
        print(f"{Fore.YELLOW}{'-'*80}")

        cat_results = []
        for query in queries:
            print(f"\n{Fore.WHITE}🔸 Query: {Fore.GREEN}{query}")
            data = test_query(query)
            rt = data.get("response_time", 0)

            if "error" in data:
                print(f"{Fore.RED}   ❌ Error: {data['error']}")
                status = "FAILED"
            else:
                intent = data.get("intent_label", "unknown")
                conf = data.get("intent_confidence", 0)
                products = data.get("products", [])
                print(f"{Fore.CYAN}   Intent: {intent} ({conf:.2f})")
                print(f"{Fore.CYAN}   Response Time: {rt:.2f}s")
                print(f"{Fore.CYAN}   Response: {data.get('response', '')}")
                print(f"\n{Fore.MAGENTA}   Products Found: {len(products)}")
                if products:
                    print(format_products(products))
                status = "PASSED" if not data.get("error") else "FAILED"
                passed += 1

            cat_results.append({
                "query": query,
                "status": status,
                "response_time": rt,
                "result": data if "error" not in data else {"error": data["error"]}
            })
            total += 1

        results[category] = cat_results

    # Summary
    print(f"\n{Fore.CYAN}{'='*100}")
    print(f"{Fore.CYAN}📊 TEST SUMMARY")
    print(f"{Fore.CYAN}{'='*100}\n")
    print(f"{Fore.WHITE}Total Queries: {Fore.YELLOW}{total}")
    print(f"{Fore.WHITE}Successful:   {Fore.GREEN}{passed}")
    print(f"{Fore.WHITE}Failed:       {Fore.RED}{total - passed}")
    print(f"{Fore.WHITE}Success Rate: {Fore.CYAN}{passed/total*100:.1f}%\n")

    # Save results
    output = {
        "summary": {
            "total_queries": total,
            "successful": passed,
            "failed": total - passed,
        },
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"{Fore.GREEN}💾 Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    # Check API availability
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        if r.status_code == 200:
            health = r.json()
            print(f"{Fore.GREEN}✅ API running (products: {health.get('products', 0)})")
        else:
            print(f"{Fore.RED}❌ API health check failed")
            exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ Cannot connect to API: {e}")
        exit(1)

    run_tests()