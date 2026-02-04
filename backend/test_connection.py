# test_connection.py in conversational/backend
import requests
import sys

def test_techhaven():
    try:
        print("Testing TechHaven connection...")
        
        # Test 1: Check if TechHaven is accessible
        response = requests.get("http://localhost:5002/api/products", timeout=5)
        print(f"✅ TechHaven responded with status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📦 Found {len(data)} products in TechHaven")
            
            # Show some products
            for i, product in enumerate(data[:3]):
                print(f"  {i+1}. {product['name']} - ${product['price']}")
        
        # Test 2: Check search endpoint
        print("\nTesting search for 'phone'...")
        search_response = requests.get(
            "http://localhost:5002/api/products/search", 
            params={"q": "phone"},
            timeout=5
        )
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            print(f"🔍 Found {len(search_data)} products matching 'phone'")
        else:
            print(f"⚠️ Search endpoint returned: {search_response.status_code}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to TechHaven: {e}")
        return False

if __name__ == "__main__":
    success = test_techhaven()
    sys.exit(0 if success else 1)