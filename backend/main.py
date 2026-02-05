import os
import re
import logging
import traceback
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from ecommerce_client import ECommerceClient
from ner_model import MLNERModel

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
    version="2.0.0"  # Updated version
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MLNERModel with verification
try:
    ner_model = MLNERModel(
        classifier_path="models/intent_classifier.pth",
        preprocessor_path="models/preprocessor.pkl",
    )
    logger.info("✅ MLNERModel initialized successfully")
    
    # Test the model immediately
    test_results = [
        ner_model.classify_query_type("hello"),
        ner_model.classify_query_type("show me shoes"),
        ner_model.classify_query_type("watch out for that car"),
    ]
    logger.info(f"✅ Model test results: {test_results}")
    
except Exception as e:
    logger.error(f"❌ Failed to initialize MLNERModel: {e}")
    raise

# Initialize e-commerce client
ecommerce_client = ECommerceClient()

# ------------------- Pydantic Models -------------------
class ChatMessage(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    products: List[Dict[str, Any]]
    entities: Dict[str, Any]
    query_type: str
    intent_confidence: float
    intent_label: str
    intent_badge: Dict[str, Any]
    search_params: Optional[Dict[str, Any]] = None
    model_used: str = "100% Intent Classifier"  # Always true now

class HealthCheck(BaseModel):
    status: str
    ner_model: str
    stores: Dict[str, str]
    model_usage: str = "100% ML Classifier"

class DebugIntentRequest(BaseModel):
    query: str

# ------------------- Helper Functions -------------------
def build_intent_badge(intent: str, confidence: float) -> Dict[str, Any]:
    return {
        "intent": intent,
        "confidence": round(confidence * 100, 1),
        "level": (
            "high" if confidence >= 0.85
            else "medium" if confidence >= 0.65
            else "low"
        ),
        "source": "ML Classifier"  # Always from ML model now
    }

def enhance_product_images(product: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure product has proper image URL"""
    image_fields = ["image_url", "image", "thumbnail", "product_image", "img_url", "picture"]
    
    for field in image_fields:
        if product.get(field):
            product["image_url"] = product[field]
            break
    
    if not product.get("image_url"):
        product_name = product.get("name", "Product")[:20]
        category = product.get("category", "").lower()
        colors = {
            "jacket": "555555/ffffff",
            "dress": "666666/ffffff", 
            "shoes": "777777/ffffff",
            "shirt": "888888/ffffff",
            "pants": "999999/ffffff",
            "default": "1e1b18/f7f0e8"
        }
        color = colors.get(category, colors["default"])
        product["image_url"] = f"https://placehold.co/300x300/{color}?text={product_name}"
    
    return product

# ------------------- Routes -------------------
@app.get("/")
async def root():
    return {
        "message": "Fashion E-commerce Chatbot API v2.0",
        "store": "Urban Threads",
        "intent_model": "100% ML Classifier Usage",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "products": "GET /products",
            "debug": "GET /debug/intent/{query}"
        }
    }

@app.get("/health")
async def health_check() -> HealthCheck:
    try:
        ner_test = ner_model.classify_query_type("test health check")
        store_status = await ecommerce_client.check_connection()
        return HealthCheck(
            status="healthy",
            ner_model=f"loaded - test: {ner_test[0]} (conf: {ner_test[1]:.2f})",
            stores=store_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(status="unhealthy", ner_model="error", stores={})

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        query = message.query.strip()
        logger.info(f"📩 Received query: '{query}'")
        
        # ✅ 100% ML CLASSIFIER USAGE - NO EXCEPTIONS
        query_type, intent_conf, intent_label = ner_model.classify_query_type(query)
        logger.info(f"🤖 ML Classifier Result: {query_type} (confidence: {intent_conf:.2f})")
        
        # Build intent badge
        intent_name = "product" if intent_label == 1 else "chitchat"
        intent_badge = build_intent_badge(intent_name, intent_conf)
        
        # Handle chitchat
        if query_type == "chitchat":
            return ChatResponse(
                response=ner_model.get_chitchat_response(),
                products=[],
                entities={},
                query_type="chitchat",
                intent_confidence=intent_conf,
                intent_label="chitchat",
                intent_badge=intent_badge
            )
        
        # Extract entities (only for product search, not for classification)
        entities = ner_model.extract_entities(query)
        logger.info(f"🔍 Extracted entities: {entities}")
        
        # Generate search params
        search_params = ner_model.generate_search_params(entities)
        logger.info(f"🔎 Search params: {search_params}")
        
        # Search products
        products = []
        if search_params:
            products = await ecommerce_client.search_products(search_params)
            logger.info(f"📦 Found {len(products)} raw products")
        
        # Enhance products with match scores and images
        enhanced_products = []
        for product in products:
            product["match_percentage"] = ner_model.calculate_confidence_score(
                product, entities["product"], query
            )
            product = enhance_product_images(product)
            enhanced_products.append(product)
        
        # Sort by match percentage
        enhanced_products.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)
        logger.info(f"✨ Returning {len(enhanced_products)} enhanced products")
        
        # Generate response
        if enhanced_products:
            response_msg = f"✅ Found {len(enhanced_products)} product"
            if len(enhanced_products) != 1:
                response_msg += "s"
            if search_params.get('q'):
                response_msg += f" for '{search_params['q']}'"
        else:
            response_msg = "🔍 No products found"
            if search_params.get('q'):
                response_msg += f" for '{search_params['q']}'. Try different keywords."
            else:
                response_msg += ". Please specify what you're looking for."
        
        return ChatResponse(
            response=response_msg,
            products=enhanced_products,
            entities=entities,
            query_type="product",
            intent_confidence=intent_conf,
            intent_label="product",
            intent_badge=intent_badge,
            search_params=search_params
        )
        
    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/intent/{query:path}")
async def debug_intent(query: str):
    """Debug endpoint to see intent classification details"""
    try:
        normalized = ner_model.preprocessor.normalize(query)
        
        # Get direct classifier prediction
        classifier_result = ner_model.classifier.predict(normalized)
        
        # Get final classification (100% from model)
        query_type, intent_conf, intent_label = ner_model.classify_query_type(query)
        
        # Extract entities separately
        entities = ner_model.extract_entities(query)
        
        return {
            "query": query,
            "normalized": normalized,
            "classifier_raw_output": classifier_result,
            "final_classification": {
                "type": query_type,
                "confidence": intent_conf,
                "label": intent_label,
                "source": "ML Model Only"
            },
            "entities": entities,
            "model_info": {
                "usage": "100% ML Classifier",
                "no_overrides": True,
                "no_entity_based_override": True
            }
        }
    except Exception as e:
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
        
        # Enhance products
        enhanced_products = []
        for product in products:
            product = enhance_product_images(product)
            if q:
                product_name = product.get("name", "").lower()
                if q.lower() in product_name:
                    product["match_percentage"] = 100
                else:
                    product["match_percentage"] = 50
            enhanced_products.append(product)
        
        if q:
            enhanced_products.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)
        
        return {
            "products": enhanced_products[:limit],
            "total": len(enhanced_products),
            "search_params": params
        }
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------- Run -------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting Chatbot API v2.0 on port {port}")
    logger.info("✅ Intent Model: 100% ML Classifier Usage")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")