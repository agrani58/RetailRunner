# debug_api.py - Test connection to your eCommerce API
import requests
import json

def test_ecommerce_api():
    """Test if your eCommerce API is working"""
    url = "http://localhost:5001/api/products"
    
    print(f"🧪 Testing connection to: {url}")
    print("=" * 60)
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ Success! Found {len(data)} products")
                
                if data:
                    print("\n📦 First 3 products:")
                    for i, product in enumerate(data[:3], 1):
                        print(f"\n{i}. {product.get('name', 'No name')}")
                        print(f"   ID: {product.get('id')}")
                        print(f"   Price: ${product.get('price')}")
                        print(f"   Category: {product.get('category')}")
                        print(f"   Image field: {product.get('image')}")
                        print(f"   Image_url field: {product.get('image_url')}")
                        print(f"   Reviews field: {product.get('reviews')}")
                        print(f"   Review_count field: {product.get('review_count')}")
                        print(f"   Description: {product.get('description', '')[:50]}...")
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON: {e}")
                print(f"Response text: {response.text[:500]}")
        else:
            print(f"❌ API error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the eCommerce API")
        print("\n💡 Make sure your eCommerce backend is running:")
        print("   1. cd to your ecommerce project folder")
        print("   2. Run: python app.py")
        print("   3. It should run on http://localhost:5001")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_ecommerce_api()