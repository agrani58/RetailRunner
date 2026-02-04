import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from dotenv import load_dotenv
import traceback
from ner_model import NERModel
from ecommerce_client import ECommerceClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Fashion E-commerce Chatbot API",
    description="AI Chatbot for searching Urban Threads fashion store",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize models and clients
ner_model = NERModel()
ecommerce_client = ECommerceClient()

# Pydantic models
class ChatMessage(BaseModel):
    query: str
    session_id: Optional[str] = None

class Product(BaseModel):
    id: Optional[str] = None
    name: str
    price: float
    rating: Optional[float] = 0.0
    review_count: Optional[int] = 0
    category: Optional[str] = None
    stock: Optional[int] = 0
    image_url: Optional[str] = None
    description: Optional[str] = None
    match_percentage: Optional[float] = 0.0
    brand: Optional[str] = None
    url: Optional[str] = None
    store: Optional[str] = None
    store_type: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    products: List[Product]
    entities: Dict[str, Any]
    query_type: str
    intent_confidence: Optional[float] = None
    search_params: Optional[Dict[str, Any]] = None
    store_summary: Optional[Dict[str, int]] = None

class HealthCheck(BaseModel):
    status: str
    ner_model: str
    stores: Dict[str, str]

# Store for conversation context (simple in-memory store)
conversation_context = {}

def generate_response(query_type: str, entities: Dict, product_count: int, search_params: Dict) -> str:
    """Generate response text"""
    if query_type == "greeting":
        return "👋 Hello! I'm your fashion shopping assistant. How can I help you find products today?"
    
    elif query_type == "help":
        return "🛍️ I can help you search for fashion products! Try asking me about jackets, dresses, shoes, or anything else you're looking for."
    
    elif query_type == "product_search":
        if product_count == 0:
            return "🔍 I couldn't find any products matching your search. Try using different keywords or check the store."
        
        # We found products
        response = f"✅ Found {product_count} products"
        
        if "q" in search_params:
            response += f" matching '{search_params['q']}'"
        
        if "max_price" in search_params:
            response += f" under ${search_params['max_price']}"
        
        response += ". Here are the best matches:"
        return response
    
    else:
        if product_count == 0:
            return "I couldn't find any products. Try a different search."
        return f"Found {product_count} products. Here are the results:"

# Routes
@app.get("/")
async def root():
    return {
        "message": "Fashion E-commerce Chatbot API",
        "store": "Urban Threads",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "products": "GET /products"
        }
    }

@app.get("/health")
async def health_check() -> HealthCheck:
    """Health check endpoint"""
    try:
        # Test NER model
        ner_test = ner_model.extract_entities("test")
        
        # Test store connection
        store_status = await ecommerce_client.check_connection()
        
        return HealthCheck(
            status="healthy",
            ner_model="loaded" if ner_test else "error",
            stores=store_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy",
            ner_model="error",
            stores={}
        )

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Main chat endpoint"""
    try:
        logger.info(f"Received query: {message.query}")
        
        # Step 1: Extract entities
        entities = ner_model.extract_entities(message.query)
        logger.info(f"Extracted entities: {entities}")
        
        # Step 2: Determine query type
        query_type, intent_confidence = ner_model.classify_query_type(message.query, entities)
        logger.info(f"Query type: {query_type} (confidence: {intent_confidence})")
        
        # Step 3: Generate search parameters
        search_params = ner_model.generate_search_params(message.query, entities)
        logger.info(f"Search params: {search_params}")
        
        # Step 4: Check store connection
        store_status = await ecommerce_client.check_connection()
        operational_stores = [url for url, status in store_status.items() if "connected" in status]
        
        if not operational_stores:
            return ChatResponse(
                response="⚠️ I cannot connect to the store. Please make sure Urban Threads is running on port 5001.",
                products=[],
                entities=entities,
                query_type=query_type,
                intent_confidence=intent_confidence,
                search_params=search_params,
                store_summary={}
            )
        
        # Step 5: Search for products
        logger.info("Searching for products...")
        products = await ecommerce_client.search_products(search_params)
        logger.info(f"Found {len(products)} products")
        
        # Step 6: Calculate confidence scores
        search_terms = []
        if entities.get("product"):
            search_terms.extend(entities["product"])
        if entities.get("brand"):
            search_terms.extend(entities["brand"])
        
        for product in products:
            confidence_score = ner_model.calculate_confidence_score(
                product, 
                search_terms,
                message.query
            )
            product["match_percentage"] = confidence_score
        
        # Step 7: Sort by confidence score
        products.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)
        
        # Step 8: Generate response
        response_text = generate_response(query_type, entities, len(products), search_params)
        
        # Step 9: Store context for follow-up questions
        if message.session_id:
            conversation_context[message.session_id] = {
                "last_query": message.query,
                "last_entities": entities,
                "last_search_params": search_params,
                "found_products": len(products)
            }
        
        return ChatResponse(
            response=response_text,
            products=products[:20],
            entities=entities,
            query_type=query_type,
            intent_confidence=intent_confidence,
            search_params=search_params,
            store_summary={"urban_threads": len(products), "total": len(products)}
        )
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        logger.error(traceback.format_exc())
        
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/products")
async def get_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 20
):
    """Direct product search endpoint"""
    params = {}
    if q:
        params["q"] = q
    if category:
        params["category"] = category
    if min_price:
        params["min_price"] = min_price
    if max_price:
        params["max_price"] = max_price
    params["limit"] = limit
    
    products = await ecommerce_client.search_products(params)
    
    # Calculate confidence scores
    if q:
        for product in products:
            product["match_percentage"] = ner_model.calculate_confidence_score(
                product, [q], q
            )
        products.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)
    
    return {
        "products": products[:limit],
        "total": len(products),
        "search_params": params
    }

@app.get("/debug")
async def debug_info():
    """Debug information"""
    store_status = await ecommerce_client.check_connection()
    
    return {
        "status": "running",
        "stores_connected": [url for url, status in store_status.items() if "connected" in status],
        "stores_failed": [url for url, status in store_status.items() if "connected" not in status],
        "conversation_context_count": len(conversation_context)
    }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Chatbot API on port {port}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )