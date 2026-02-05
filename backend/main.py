import os
import re
import logging
import traceback
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from ecommerce_client import ECommerceClient
from ner_model import MLNERModel
from rapidfuzz import fuzz, process

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Fashion E-commerce Chatbot API",
    description="AI Chatbot for searching Urban Threads fashion store",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MLNERModel
ner_model = MLNERModel(
    classifier_path="models/intent_classifier.pth",
    preprocessor_path="models/preprocessor.pkl",
    device='cuda' if os.getenv("USE_CUDA", "0") == "1" else 'cpu'
)

# Initialize e-commerce client
ecommerce_client = ECommerceClient()

# Session-based conversation context
conversation_context = {}

# ------------------- Pydantic Models -------------------
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
    intent_label: Optional[str] = None
    intent_badge: Optional[Dict[str, Any]] = None
    search_params: Optional[Dict[str, Any]] = None
    store_summary: Optional[Dict[str, int]] = None

class HealthCheck(BaseModel):
    status: str
    ner_model: str
    stores: Dict[str, str]

# ------------------- Helper Functions -------------------
def build_intent_badge(intent: str, confidence: float):
    return {
        "intent": intent,
        "confidence": round(confidence * 100, 1),
        "level": (
            "high" if confidence >= 0.85
            else "medium" if confidence >= 0.70
            else "low"
        )
    }

def generate_response(query_type: str, entities: Dict, product_count: int, search_params: Dict) -> str:
    if query_type == "greeting":
        return "👋 Hello! I'm your fashion shopping assistant. How can I help you find products today?"
    elif query_type == "help":
        return "🛍️ I can help you search for fashion products! Ask me about jackets, dresses, shoes, or anything else."
    elif query_type == "product_search":
        if product_count == 0:
            return "🔍 I couldn't find any products matching your search. Try using different keywords or check the store."
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

def normalize_product_name(query: str, product_names: List[str]) -> str:
    """
    Fuzzy match user query to closest product name in store.
    Returns the normalized product name.
    """
    best_match, score, _ = process.extractOne(
        query,
        product_names,
        scorer=fuzz.token_sort_ratio
    )
    return best_match if score >= 60 else query  # Threshold 60 for match

# ------------------- Routes -------------------
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
    try:
        ner_test = ner_model.extract_entities("test")
        store_status = await ecommerce_client.check_connection()
        return HealthCheck(
            status="healthy",
            ner_model="loaded" if ner_test else "error",
            stores=store_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(status="unhealthy", ner_model="error", stores={})

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        logger.info(f"Received query: {message.query}")

        # 1️⃣ INTENT — ONLY MODEL
        query_type, intent_confidence, intent_label = (
            ner_model.classify_query_type(message.query)
        )

        # 2️⃣ CHITCHAT — STOP HERE
        if query_type == "chitchat":
            return ChatResponse(
                response=ner_model.get_chitchat_response(),
                products=[],
                entities={},
                query_type="chitchat",
                intent_confidence=intent_confidence,
                intent_label="chitchat",
                intent_badge=build_intent_badge("chitchat", intent_confidence)
            )




        # 3️⃣ PRODUCT SEARCH
        entities = ner_model.extract_entities(message.query)
        search_params = ner_model.generate_search_params(entities)

        if not search_params:
            return ChatResponse(
                response=f"[INTENT={intent_label}] "
                         "Tell me which product you want to search.",
                products=[],
                entities=entities,
                query_type="product",
                intent_confidence=intent_confidence
            )

        products = await ecommerce_client.search_products(search_params)

        for product in products:
            product["match_percentage"] = ner_model.calculate_confidence_score(
                product,
                entities.get("product", []),
                message.query
            )

        products.sort(
            key=lambda x: x.get("match_percentage", 0),
            reverse=True
        )

        return ChatResponse(
            response=f"[INTENT={intent_label}] "
                     f"Found {len(products)} products.",
            products=products[:20],
            entities=entities,
            query_type="product",
            intent_confidence=intent_confidence,
            search_params=search_params,
            store_summary={"total": len(products)}
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products")
async def get_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 20
):
    try:
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
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug")
async def debug_info():
    store_status = await ecommerce_client.check_connection()
    return {
        "status": "running",
        "stores_connected": [url for url, status in store_status.items() if "connected" in status],
        "stores_failed": [url for url, status in store_status.items() if "connected" not in status],
        "conversation_context_count": len(conversation_context)
    }

# ------------------- Run -------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Chatbot API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
