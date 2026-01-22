# backend/app.py - Main FastAPI Application with chat endpoint
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
from dotenv import load_dotenv
import json

# Import your modules
from vector_search import ProductSearchEngine
from db_connection import EcommerceAPI

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="E-commerce Chatbot API",
    description="AI-powered shopping assistant",
    version="1.0.0"
)

# CORS middleware - Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
search_engine = ProductSearchEngine()
api_client = EcommerceAPI()

# Pydantic Models
class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = None

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    products: List[Dict[str, Any]]
    query: str

class Product(BaseModel):
    id: int
    name: str
    price: float
    rating: float
    category: str
    stock: int
    image_url: str
    description: str
    similarity_score: Optional[float] = None
    match_percentage: Optional[int] = None
    matched_keywords: Optional[List[str]] = None

class SearchResponse(BaseModel):
    query: str
    results: List[Product]
    top_match_score: float
    total_matches: int
    status: str = "success"

# Helper function to format chat response
def format_chat_response(query: str, products: List[Dict[str, Any]]) -> str:
    """Format product search results into a friendly chat response"""
    if not products:
        return f"I couldn't find any products matching '{query}'. Could you try a different search term?"
    
    # Count products by category
    categories = {}
    for product in products:
        cat = product.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    category_summary = ", ".join([f"{count} {cat}" for cat, count in categories.items()])
    
    # Build response
    response = f"I found {len(products)} products matching '{query}':\n\n"
    
    for i, product in enumerate(products[:3], 1):  # Show top 3
        match_percent = product.get('match_percentage', 0)
        response += f"{i}. **{product['name']}** - ${product['price']:.2f}\n"
        response += f"   ⭐ {product['rating']}/5 | 📦 {product['stock']} in stock\n"
        response += f"   🎯 Match: {match_percent}%\n"
        response += f"   📝 {product['description'][:80]}...\n\n"
    
    if len(products) > 3:
        response += f"... and {len(products) - 3} more products.\n\n"
    
    response += "Which product would you like to know more about?"
    
    return response

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-commerce Chatbot API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "/chat": "POST - Main chatbot endpoint (for frontend)",
            "/api/chat/search": "POST - Search products with natural language",
            "/api/products": "GET - Get all products",
            "/api/products/search": "GET - Direct search",
            "/health": "GET - Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "search_engine_initialized": search_engine.is_initialized(),
        "api_url": api_client.base_url,
        "product_count": len(search_engine.products) if search_engine.is_initialized() else 0
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chatbot endpoint for frontend
    Expected by your React frontend
    """
    try:
        print(f"💬 Chat request: '{request.query}'")
        
        # Get products from API
        products = api_client.get_all_products()
        
        if not products:
            return ChatResponse(
                response="I'm sorry, but I couldn't fetch any products at the moment. Please try again later.",
                products=[],
                query=request.query
            )
        
        # Initialize or update search engine
        if not search_engine.is_initialized():
            search_engine.initialize(products)
        else:
            if len(products) != len(search_engine.products):
                search_engine.update_products(products)
        
        # Perform search
        results = search_engine.search(request.query, top_n=5)
        
        # Format response for chat
        chat_response = format_chat_response(request.query, results)
        
        return ChatResponse(
            response=chat_response,
            products=results,
            query=request.query
        )
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        return ChatResponse(
            response="I encountered an error while searching. Please try again with a different query.",
            products=[],
            query=request.query
        )

@app.post("/api/chat/search", response_model=SearchResponse)
async def chat_search(message: ChatMessage):
    """Search products based on natural language query"""
    try:
        print(f"📥 Received query: '{message.message}'")
        products = api_client.get_all_products()
        
        if not products:
            return SearchResponse(
                query=message.message,
                results=[],
                top_match_score=0,
                total_matches=0,
                status="no_products"
            )
        
        # Initialize or update search engine
        if not search_engine.is_initialized():
            search_engine.initialize(products)
        else:
            if len(products) != len(search_engine.products):
                search_engine.update_products(products)
        
        # Perform search
        query = message.message
        results = search_engine.search(query, top_n=5)
        
        return SearchResponse(
            query=query,
            results=results,
            top_match_score=results[0]["similarity_score"] if results else 0,
            total_matches=len(results)
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
async def get_all_products():
    """Get all products from eCommerce API"""
    try:
        products = api_client.get_all_products()
        return {
            "status": "success",
            "count": len(products),
            "products": products
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/search")
async def search_products_api(q: str = "", category: str = "", limit: int = 10):
    """Direct search endpoint for testing"""
    try:
        products = api_client.get_all_products()
        
        # Initialize search engine if needed
        if not search_engine.is_initialized():
            search_engine.initialize(products)
        
        if q:
            # Use vector search
            results = search_engine.search(q, top_n=limit)
            return {
                "query": q,
                "results": results,
                "count": len(results),
                "type": "vector_search"
            }
        
        # Filter by category if provided
        if category:
            filtered = [p for p in products if p["category"].lower() == category.lower()]
            return {
                "query": f"category: {category}",
                "results": filtered[:limit],
                "count": len(filtered),
                "type": "category_filter"
            }
        
        return {
            "results": products[:limit],
            "count": len(products),
            "type": "all_products"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("🚀 Starting up E-commerce Chatbot API...")
    print(f"📡 Connecting to eCommerce API at: {api_client.base_url}")
    
    # Try to fetch and initialize products
    try:
        products = api_client.get_all_products()
        if products:
            search_engine.initialize(products)
            print(f"✅ Initialized with {len(products)} products")
        else:
            print("⚠️ No products found, using sample data")
    except Exception as e:
        print(f"⚠️ Startup error: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )