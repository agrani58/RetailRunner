import os
import random
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
import auth
from schemas import UserCreate, LoginRequest, TokenResponse, SimpleResponse, UserResponse, RefreshTokenRequest
from config import JWT_CONFIG, DB_CONFIG, config as app_config

# Import chatbot modules
from catalog_loader import load_products, refresh_catalog_periodically
from intent_model import get_intent_model
from ner_model import MLNERModel
from text_normalizer import TextNormalizer
from query_processor import QueryProcessor
from search_engine import SearchEngine
from order_bot import place_order_bot
from config import config, STORE_FRONTEND_MAP, STORE_NAMES
from recommendation_model import RecommendationModel

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logger = logging.getLogger("main")

# ---------- Chatbot app state ----------
app_state = {
    "products_data": [],
    "search_engine": None,
    "intent_model": None,
    "ner_model": None,
    "query_processor": None,
    "normalizer": TextNormalizer(),
    "recommendation_model": None,
}

# Chitchat responses
CHITCHAT_RESPONSES = [
    "Hi there! How can I help you find the perfect product today?",
    "Hello! I'm here to assist with your shopping needs. What are you looking for?",
    "Hey! Ready to explore some amazing products? Just tell me what you're interested in.",
]

# Known product terms to override low‑confidence chitchat
PRODUCT_TERMS_FOR_OVERRIDE = {
    "laptop", "laptops", "phone", "phones", "smartphone", "smartphones",
    "tv", "television", "televisions", "shoes", "footwear", "headphones",
    "watch", "smartwatch", "smartwatches", "tablet", "tablets", "camera",
    "cameras", "monitor", "monitors", "jeans", "dress", "dresses", "jacket",
    "jackets", "tshirt", "t-shirt", "t-shirts", "tees", "shirt", "shirts",
    "kurta", "ethnic", "gown", "gowns", "makeup", "foundation", "lipstick",
    "cream", "moisturizer", "sunscreen", "facewash", "face wash", "body lotion",
    "lotion", "serum", "mask", "cleanser", "toner"
}

# ---------- Lifespan: init DB and all models ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize database
    try:
        database.init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    # 2. Load products from APIs
    logger.info("🔄 Loading products from APIs...")
    products_data = await load_products()
    app_state["products_data"] = products_data
    logger.info(f"✅ Loaded {len(products_data)} products")

    # 3. Load intent model
    logger.info("🧠 Loading intent model...")
    intent_model = get_intent_model()
    if intent_model is None:
        raise RuntimeError("❌ Intent model failed to load – aborting")
    app_state["intent_model"] = intent_model

    # 4. Load NER model
    logger.info("🔍 Loading NER model...")
    try:
        ner_model = MLNERModel(app_config.NER_MODEL_PATH)
        app_state["ner_model"] = ner_model
        logger.info("✅ NER model ready")
    except Exception as e:
        logger.error(f"❌ NER model failed: {e}")
        raise

    # 5. Load recommendation model
    logger.info("💰 Loading recommendation model (price/rating)...")
    try:
        rec_model = RecommendationModel(app_config.PRICE_RATING_MODEL_PATH, device=app_config.DEVICE)
        app_state["recommendation_model"] = rec_model
        logger.info("✅ Recommendation model ready")
    except Exception as e:
        logger.error(f"❌ Recommendation model failed: {e}")
        raise

    # 6. Initialise search engine
    logger.info("🔧 Initialising search engine...")
    search_engine = SearchEngine(products_data)
    app_state["search_engine"] = search_engine

    # 7. Initialise query processor
    query_processor = QueryProcessor(ner_model, products_data, rec_model)
    app_state["query_processor"] = query_processor

    # 8. Start background catalog refresh if APIs configured
    if app_config.ECOMMERCE_API_URLS:
        refresh_task = asyncio.create_task(
            refresh_catalog_periodically(app_state, app_config.REFRESH_INTERVAL)
        )
        logger.info(f"⏰ Background refresh every {app_config.REFRESH_INTERVAL}s")
        yield
        refresh_task.cancel()
    else:
        yield

    logger.info("🛑 Shutting down.")

# ---------- FastAPI app ----------
app = FastAPI(title="Conversational Commerce + Auth API", lifespan=lifespan)

# CORS – allow frontend origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Auth routes (unchanged) ----------
@app.post("/signup", response_model=SimpleResponse)
def signup(user_data: UserCreate):
    try:
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        user = database.create_user(email=user_data.email, password=user_data.password)
        if user:
            return SimpleResponse(message="Account created successfully", email=user['email'], user_id=user['user_id'])
        raise HTTPException(status_code=500, detail="Failed to create user")
    except ValueError as e:
        if "Email already exists" in str(e):
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest):
    user = database.verify_user_credentials(email=login_data.email, password=login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = auth.create_access_token(data={"sub": str(user['user_id']), "email": user['email']})
    refresh_token, _ = auth.create_refresh_token(user['user_id'])
    if not refresh_token:
        raise HTTPException(status_code=500, detail="Failed to create token")
    user_data = {"id": user['user_id'], "email": user['email']}
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_data=user_data,
        expires_in=JWT_CONFIG["access_token_expire_minutes"] * 60
    )

@app.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_data: RefreshTokenRequest):
    user_id = auth.verify_refresh_token(refresh_data.refresh_token)
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access_token = auth.create_access_token(data={"sub": str(user['user_id']), "email": user['email']})
    new_refresh_token, _ = auth.create_refresh_token(user['user_id'])
    if not new_refresh_token:
        raise HTTPException(status_code=500, detail="Failed to create token")
    user_data = {"id": user['user_id'], "email": user['email']}
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user_data=user_data,
        expires_in=JWT_CONFIG["access_token_expire_minutes"] * 60
    )

@app.post("/logout")
def logout(refresh_data: RefreshTokenRequest, current_user: dict = Depends(auth.get_current_user)):
    try:
        auth.verify_refresh_token(refresh_data.refresh_token)
    except:
        pass
    database.revoke_refresh_token(current_user['user_id'])
    return {"message": "Logged out successfully", "email": current_user['email']}

@app.post("/logout-all")
def logout_all(current_user: dict = Depends(auth.get_current_user)):
    database.revoke_refresh_token(current_user['user_id'])
    return {"message": "Logged out from all devices", "email": current_user['email']}

@app.get("/protected")
def protected_route(current_user: dict = Depends(auth.get_current_user)):
    return {"message": f"Hello {current_user['email']}!", "email": current_user['email'], "user_id": current_user['user_id']}

@app.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: dict = Depends(auth.get_current_user)):
    user = database.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/auth/health")
def auth_health():
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ---------- Chatbot routes ----------
class ChatRequest(BaseModel):
    query: str

class PlaceOrderRequest(BaseModel):
    product_name: str
    user_info: Dict[str, str]   # name, email, password, phone, address

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


def get_intent(query: str) -> dict:
    """
    Determine intent using ML model, with rule‑based override for low‑confidence product terms.
    """
    intent_model = app_state.get("intent_model")
    if not intent_model:
        raise HTTPException(status_code=503, detail="Intent model not loaded")

    try:
        result = intent_model.predict(query)
        logger.info(f"🤖 Intent model used – result: {result}")
        intent = result["intent"]
        confidence = result["confidence"]

        # Rule‑based override: if confidence < 0.8 and query contains a known product term, force product_search
        if confidence < 0.8 and intent == "chitchat":
            query_lower = query.lower()
            if any(term in query_lower for term in PRODUCT_TERMS_FOR_OVERRIDE):
                logger.info(f"⚡ Overriding chitchat (conf={confidence:.2f}) to product_search because query contains product term")
                intent = "product_search"
                confidence = 1.0  # set high confidence for product search

        return {"label": intent, "confidence": confidence}
    except Exception as e:
        logger.error(f"Intent model error: {e}")
        raise HTTPException(status_code=503, detail="Intent model unavailable")


def format_products(products: list) -> List[ProductResponse]:
    """Deduplicate and format products, set store name from mapping."""
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

        # Determine store name
        store = p.get("store")  # if already present (e.g., from static)
        if not store:
            source = p.get("source", "")
            # Look up friendly name using full source URL
            store = STORE_NAMES.get(source)
            if not store and source:
                # Fallback: extract host
                if "://" in source:
                    source = source.split("://")[1].split("/")[0]
                store = source or "Unknown Store"

        formatted.append(ProductResponse(
            id=str(p.get("id", "")),
            name=p.get("name", "Unknown"),
            category=p.get("category", "Uncategorized"),
            price=round(price, 2),
            rating=float(p.get("rating")) if p.get("rating") else None,
            description=p.get("description", ""),
            image_url=p.get("image_url") or p.get("image"),
            store=store,
            tags=p.get("tags", []),
            relevance_score=p.get("relevance_score"),
        ))
    return formatted


def generate_response(query: str, products: list, search_category: str = None) -> str:
    if not products:
        if search_category:
            return f"Sorry, we currently don't have any {search_category} in our catalog. Try a different category or check back later."
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

        qp = app_state.get("query_processor")
        if not qp:
            raise HTTPException(status_code=503, detail="Query processor not ready")

        analysis = qp.process(query)
        logger.info(f"🔍 Query analysis: {analysis}")

        skip_entity_filter = analysis.get('skip_entity_filter', False)

        search_query = query
        brand = analysis.get('brand')
        search_category = analysis.get('search_category')
        subcategory_keywords = analysis.get('subcategory_keywords', [])
        constraints = analysis.get('constraints', {})
        product_entities = analysis.get('product_entities', [])

        logger.info(f"🔍 Search params: brand={brand}, category={search_category}, "
                    f"subcategory={subcategory_keywords}, constraints={constraints}, "
                    f"entities={product_entities}, skip_entity_filter={skip_entity_filter}")

        search_engine = app_state.get("search_engine")
        if not search_engine:
            raise HTTPException(status_code=503, detail="Search engine not ready")

        results = search_engine.search(
            query=search_query,
            product_entities=product_entities,
            brand=brand,
            constraints=constraints,
            search_category=search_category,
            subcategory_keywords=subcategory_keywords,
            exclude_terms=analysis.get('exclude_terms', []),
            skip_entity_filter=skip_entity_filter,
            top_k=10,
        )
        logger.info(f"🔎 Search engine returned {len(results)} raw results")

        formatted = format_products(results)
        response_text = generate_response(query, formatted, search_category)

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


@app.post("/place-order")
async def place_order(request: PlaceOrderRequest):
    """
    Starts a Playwright bot to place an order for the given product using user profile data.
    """
    try:
        product_name = request.product_name
        user_info = request.user_info

        logger.info(f"📦 Place-order request: product='{product_name}', user_info={user_info}")

        products = app_state.get("products_data", [])
        found_product = None
        for p in products:
            p_name = p.get("name", "")
            if p_name.lower() == product_name.lower():
                found_product = p
                logger.info(f"✅ Exact match: '{p_name}'")
                break

        if not found_product:
            for p in products:
                p_name = p.get("name", "")
                if product_name.lower() in p_name.lower() or p_name.lower() in product_name.lower():
                    found_product = p
                    logger.info(f"✅ Partial match: '{p_name}'")
                    break

        if not found_product:
            logger.error(f"Product '{product_name}' not found in catalog")
            raise HTTPException(status_code=404, detail=f"Product '{product_name}' not found in catalog")

        source_api = found_product.get("source")
        logger.info(f"🔍 Product source: '{source_api}'")

        if not source_api:
            raise HTTPException(status_code=400, detail="Product has no source information")

        # Handle products from static file
        if source_api == "static":
            logger.warning("Product from static file cannot be ordered via bot.")
            return {
                "message": "This product is from a static catalog and cannot be ordered automatically. Please visit the store website.",
                "product_name": product_name
            }

        frontend_url = STORE_FRONTEND_MAP.get(source_api)
        if not frontend_url:
            logger.error(f"No frontend mapping for source: {source_api}")
            raise HTTPException(status_code=400, detail=f"No frontend mapping for source: {source_api}")

        logger.info(f"✅ Found frontend URL: {frontend_url}")

        asyncio.create_task(place_order_bot(frontend_url, user_info, product_name))
        logger.info(f"✅ Order bot started for '{product_name}' on {frontend_url}")

        return {
            "message": f"🤖 Order bot started for '{product_name}'. A browser window should open shortly.",
            "frontend_url": frontend_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in /place-order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "products": len(app_state.get("products_data", [])),
        "intent_model": app_state.get("intent_model") is not None,
        "ner_model": app_state.get("ner_model") is not None,
        "recommendation_model": app_state.get("recommendation_model") is not None,
        "search_engine": app_state.get("search_engine") is not None,
    }


@app.get("/")
def root():
    return {
        "message": "Conversational Commerce + Auth API",
        "catalog_source": "APIs" if app_config.ECOMMERCE_API_URLS else "static file",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app_config.API_HOST, port=app_config.API_PORT)