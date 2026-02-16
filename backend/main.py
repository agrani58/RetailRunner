import os
os.environ["TQDM_DISABLE"] = "1"

import random
import logging
import traceback
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from config import config
from catalog_loader import load_products, refresh_catalog_periodically
from intent_model import get_intent_model
from ner_model import MLNERModel
from text_normalizer import TextNormalizer
from query_processor import QueryProcessor
from search_engine import SearchEngine

logger = logging.getLogger("main")

app_state = {
    "products_data": [],
    "search_engine": None,
    "intent_model": None,
    "ner_model": None,
    "query_processor": None,
    "normalizer": TextNormalizer(),
}

# Product-related keywords that should force product_search
PRODUCT_KEYWORDS = [
    "laptop", "laptops", "phone", "phones", "smartphone", "smartphones",
    "headphone", "headphones", "earbud", "earbuds", "headset",
    "tablet", "tablets", "ipad", "camera", "cameras",
    "watch", "watches", "smartwatch", "smartwatches",
    "shoe", "shoes", "sneaker", "sneakers", "boot", "boots",
    "tv", "television", "monitor", "mouse", "keyboard",
    "gaming", "console", "playstation", "xbox", "nintendo",
    "price", "cost", "under", "over", "above", "below",
    "cheapest", "expensive", "budget", "affordable",
    "rating", "rated", "reviews", "stars", "best", "top",
    "jeans", "jacket", "shirt", "dress", "kurta", "saree",
    "jeenz",  # misspelling
    "sweater", "sweaters",  # added
    "all products", "everything",  # added to force product search
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🔄 Loading products...")
    products_data = await load_products(force_refresh=False)
    app_state["products_data"] = products_data
    logger.info(f"✅ Loaded {len(products_data)} products")

    logger.info("🧠 Loading intent model...")
    intent_model = get_intent_model()
    app_state["intent_model"] = intent_model

    logger.info("🔍 Loading NER model...")
    try:
        ner_model = MLNERModel(config.NER_MODEL_PATH)
        app_state["ner_model"] = ner_model
        logger.info("✅ NER model ready")
    except Exception as e:
        logger.error(f"❌ NER model failed: {e}")
        raise  # No fallback – require NER model

    logger.info("🔧 Initialising search engine...")
    search_engine = SearchEngine(products_data)
    app_state["search_engine"] = search_engine

    query_processor = QueryProcessor(ner_model, products_data)
    app_state["query_processor"] = query_processor

    if config.ECOMMERCE_API_URLS and config.ECOMMERCE_API_URLS != [""]:
        import asyncio
        refresh_task = asyncio.create_task(
            refresh_catalog_periodically(app_state, config.REFRESH_INTERVAL)
        )
        logger.info(f"⏰ Background refresh every {config.REFRESH_INTERVAL}s")
        yield
        refresh_task.cancel()
    else:
        yield

    logger.info("🛑 Shutting down.")

app = FastAPI(title="Conversational Commerce API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str

class ProductResponse(BaseModel):
    id: str
    name: str
    category: str
    price: float
    rating: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    store: Optional[str] = None
    tags: Optional[list] = None
    relevance_score: Optional[float] = None

class ChatResponse(BaseModel):
    response: str
    intent_label: str
    intent_confidence: float
    products: List[ProductResponse]
    query: str

CHITCHAT_RESPONSES = [
    "Hi there! How can I help you find the perfect product today?",
    "Hello! I'm here to assist with your shopping needs. What are you looking for?",
    "Hey! Ready to explore some amazing products? Just tell me what you're interested in.",
]

def get_intent(query: str) -> dict:
    """Intent classification with strong product override (kept as allowed fallback)."""
    q_lower = query.lower()

    # Check for product-related keywords first
    if any(keyword in q_lower for keyword in PRODUCT_KEYWORDS):
        logger.info(f"🎯 Product keyword detected, forcing product_search")
        return {"label": "product_search", "confidence": 0.95}

    # Use ML model
    intent_model = app_state.get("intent_model")
    if intent_model:
        try:
            result = intent_model.predict(query)
            return {"label": result["intent"], "confidence": result["confidence"]}
        except Exception as e:
            logger.error(f"Intent model error: {e}")

    # Simple chitchat fallback (allowed)
    if any(greet in q_lower for greet in ["hi", "hello", "hey", "greetings"]):
        return {"label": "chitchat", "confidence": 0.9}

    return {"label": "product_search", "confidence": 0.8}

def format_products(products: list) -> List[ProductResponse]:
    seen = set()
    unique_products = []
    for p in products:
        key = (p.get("name", ""), p.get("price", 0))
        if key not in seen:
            seen.add(key)
            unique_products.append(p)

    formatted = []
    for p in unique_products[:8]:
        price = p.get("price", 0)
        formatted.append(ProductResponse(
            id=str(p.get("id", "")),
            name=p.get("name", "Unknown"),
            category=p.get("category", "Uncategorized"),
            price=round(price, 2),
            rating=float(p.get("rating")) if p.get("rating") else None,
            description=p.get("description", ""),
            image_url=p.get("image_url") or p.get("image"),
            store=p.get("store", "Unknown Store"),
            tags=p.get("tags", []),
            relevance_score=p.get("relevance_score"),
        ))
    return formatted

def generate_response(query: str, products: list) -> str:
    if not products:
        return f"Sorry, I couldn't find anything for '{query}'. Try different words?"
    if len(products) == 1:
        return f"I found the perfect match: {products[0].name}"
    return f"I found {len(products)} great options for '{query}'. Here are the top picks:"

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Empty query")

        logger.info(f"💬 Query: '{query}'")

        intent = get_intent(query)
        logger.info(f"🎯 Intent: {intent['label']} ({intent['confidence']:.2f})")

        if intent["label"] == "chitchat":
            return ChatResponse(
                response=random.choice(CHITCHAT_RESPONSES),
                intent_label="chitchat",
                intent_confidence=intent["confidence"],
                products=[],
                query=query,
            )

        # Process query with full ML pipeline
        qp = app_state.get("query_processor")
        if not qp:
            raise HTTPException(status_code=503, detail="Query processor not ready")

        analysis = qp.process(query)
        logger.info(f"🔍 Query analysis: {analysis}")

        search_query = query
        brand = analysis.get('brand')
        search_category = analysis.get('search_category')
        subcategory_keywords = analysis.get('subcategory_keywords', [])
        constraints = analysis.get('constraints', {})

        logger.info(f"🔍 Search params:")
        logger.info(f"   Brand: {brand}")
        logger.info(f"   Category: {search_category}")
        logger.info(f"   Subcategory keywords: {subcategory_keywords}")
        logger.info(f"   Constraints: {constraints}")

        search_engine = app_state.get("search_engine")
        if not search_engine:
            raise HTTPException(status_code=503, detail="Search engine not ready")

        results = search_engine.search(
            query=search_query,
            brand=brand,
            constraints=constraints,
            search_category=search_category,
            subcategory_keywords=subcategory_keywords,
            top_k=10,
        )

        logger.info(f"🔎 Search engine returned {len(results)} raw results")
        formatted = format_products(results)
        response_text = generate_response(query, formatted)

        logger.info(f"✅ Returning {len(formatted)} products")
        return ChatResponse(
            response=response_text,
            intent_label="product_search",
            intent_confidence=intent["confidence"],
            products=formatted,
            query=query,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {
        "status": "ok",
        "products": len(app_state.get("products_data", [])),
        "intent_model": app_state.get("intent_model") is not None,
        "ner_model": app_state.get("ner_model") is not None,
        "search_engine": app_state.get("search_engine") is not None,
    }

@app.get("/")
def root():
    return {
        "message": "Conversational Commerce API",
        "catalog_source": "APIs" if config.ECOMMERCE_API_URLS else "static file",
    }

if __name__ == "__main__":
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)