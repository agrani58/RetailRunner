import os
# Disable all tqdm progress bars globally (silence sentence‑transformers)
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

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")

# -------------------------------------------------
# Global application state (will be populated in lifespan)
# -------------------------------------------------
app_state = {
    "products_data": [],
    "search_engine": None,
    "intent_model": None,
    "ner_model": None,
    "query_processor": None,
}

# -------------------------------------------------
# Lifespan: startup & shutdown events
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("🔄 Loading products...")
    products_data = await load_products(force_refresh=False)
    app_state["products_data"] = products_data
    logger.info(f"✅ Loaded {len(products_data)} products")

    logger.info("🧠 Loading intent model...")
    intent_model = get_intent_model()
    app_state["intent_model"] = intent_model
    if intent_model:
        logger.info("✅ Intent model ready")
    else:
        logger.warning("⚠️ Intent model not available – using rule‑based fallback.")

    logger.info("🔍 Loading NER model...")
    try:
        ner_model = MLNERModel(config.NER_MODEL_PATH)
        app_state["ner_model"] = ner_model
        logger.info("✅ NER model ready")
    except Exception as e:
        logger.error(f"❌ NER model failed: {e}")
        ner_model = None

    logger.info("🔧 Initialising search engine...")
    search_engine = SearchEngine(products_data)
    app_state["search_engine"] = search_engine

    # ✅ Pass the FULL product list to QueryProcessor for dynamic spelling correction
    if ner_model:
        query_processor = QueryProcessor(ner_model, products_data)
        app_state["query_processor"] = query_processor
    else:
        app_state["query_processor"] = None

    # Start background refresh task
    if config.ECOMMERCE_API_URLS and config.ECOMMERCE_API_URLS != [""]:
        import asyncio
        refresh_task = asyncio.create_task(
            refresh_catalog_periodically(app_state, config.REFRESH_INTERVAL)
        )
        logger.info(f"⏰ Background catalog refresh scheduled every {config.REFRESH_INTERVAL}s")
        yield
        refresh_task.cancel()
    else:
        logger.info("⏹️ No API URLs configured – background refresh disabled.")
        yield
    # --- SHUTDOWN ---
    logger.info("🛑 Shutting down.")

# -------------------------------------------------
# FastAPI app
# -------------------------------------------------
app = FastAPI(title="Conversational Commerce API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Pydantic models
# -------------------------------------------------
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

# -------------------------------------------------
# Chitchat responses
# -------------------------------------------------
CHITCHAT_RESPONSES = [
    "Hi there! How can I help you find the perfect product today?",
    "Hello! I'm here to assist with your shopping needs. What are you looking for?",
    "Hey! Ready to explore some amazing products? Just tell me what you're interested in.",
]

# -------------------------------------------------
# Helper functions
# -------------------------------------------------
def get_intent(query: str) -> dict:
    """Intent classification – with rule override for common product terms."""
    intent_model = app_state.get("intent_model")
    if intent_model:
        try:
            result = intent_model.predict(query)
            label = result["intent"]
            conf = result["confidence"]

            # 🔥 OVERRIDE: if model says chitchat but query clearly wants product
            if label == "chitchat" and conf > 0.6:
                product_triggers = [
                    "face wash", "facewash", "lip balm", "lipbalm",
                    "laptop", "jacket", "shoe", "shoes", "cream", "serum",
                    "hair oil", "sunscreen", "spf", "watch", "phone",
                    "kurti", "kurta", "kurtha", "ethnic", "sweater",
                    "tshirt", "shirt", "boot", "boots", "sneaker",
                    "gaming laptop", "gaming", "iphone", "samsung",
                    "ssd", "spf", "day cream", "night cream"
                ]
                if any(trigger in query.lower() for trigger in product_triggers):
                    logger.info(f"⚠️ Overriding chitchat → product_search (trigger: {query})")
                    label = "product_search"
                    conf = 0.6

            return {"label": label, "confidence": conf}
        except Exception as e:
            logger.error(f"Intent model error: {e}")

    # Rule-based fallback
    q = query.lower()
    if any(greet in q for greet in ["hi", "hello", "hey", "greetings"]):
        return {"label": "chitchat", "confidence": 0.9}
    if any(shop in q for shop in ["show", "find", "buy", "need", "want"]):
        return {"label": "product_search", "confidence": 0.8}
    return {"label": "product_search", "confidence": 0.6}


def format_products(products: list) -> List[ProductResponse]:
    """Convert product dicts to Pydantic model, with deduplication."""
    # 🧹 Final deduplication by product name + price
    seen = set()
    unique_products = []
    for p in products:
        key = (p.get("name", ""), p.get("price", 0))
        if key not in seen:
            seen.add(key)
            unique_products.append(p)

    formatted = []
    for p in unique_products[:8]:
        formatted.append(ProductResponse(
            id=str(p.get("id", "")),
            name=p.get("name", "Unknown"),
            category=p.get("category", "Uncategorized"),
            price=float(p.get("price", 0)),
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


# -------------------------------------------------
# Endpoints
# -------------------------------------------------
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

        # Process query (NER, brand, spelling correction, exact match)
        qp = app_state.get("query_processor")
        if qp:
            analysis = qp.process(query)
            # Use spelling‑corrected version if available, otherwise normalized
            search_query = analysis.get("corrected") or analysis.get("normalized") or query
            product_entities = analysis["product_entities"]
            brand = analysis["brand"]
            exact_name = analysis["exact_product_match"]
        else:
            search_query = query
            product_entities = []
            brand = None
            exact_name = None

        logger.info(f"🔍 Search query: '{search_query}', Entities: {product_entities}, Brand: {brand}, Exact: {exact_name}")

        # Search
        search_engine = app_state.get("search_engine")
        if not search_engine:
            raise HTTPException(status_code=503, detail="Search engine not ready")

        results = search_engine.search(
            query=search_query,
            product_entities=product_entities,
            brand=brand,
            exact_name=exact_name,
            top_k=10,
        )

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
        "refresh_interval": config.REFRESH_INTERVAL,
        "api_endpoints": config.ECOMMERCE_API_URLS,
    }


@app.get("/")
def root():
    return {
        "message": "Conversational Commerce API – Fully Dynamic Edition",
        "catalog_source": "APIs" if config.ECOMMERCE_API_URLS else "static file",
        "refresh_interval_sec": config.REFRESH_INTERVAL,
        "spelling_correction": True,
        "intent_override": True,
    }


@app.post("/admin/refresh")
async def admin_refresh():
    """Force an immediate catalog refresh (for manual use)."""
    logger.info("🔄 Manual refresh triggered")
    try:
        new_products = await load_products(force_refresh=True)
        app_state["products_data"] = new_products

        # Re‑initialise search engine
        from search_engine import SearchEngine
        app_state["search_engine"] = SearchEngine(new_products)

        # Re‑initialise query processor with new product list
        if app_state.get("ner_model"):
            app_state["query_processor"] = QueryProcessor(
                app_state["ner_model"],
                new_products
            )

        return {"status": "success", "product_count": len(new_products)}
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)