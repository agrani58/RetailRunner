import os
import random
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
import auth
from schemas import UserCreate, LoginRequest, TokenResponse, SimpleResponse, UserResponse, RefreshTokenRequest
from config import JWT_CONFIG, DB_CONFIG  # also imports chatbot config via from config import config

# Import chatbot modules
from catalog_loader import load_products, refresh_catalog_periodically
from intent_model import get_intent_model
from ner_model import MLNERModel
from text_normalizer import TextNormalizer
from query_processor import QueryProcessor
from search_engine import SearchEngine

logger = logging.getLogger("main")

# ---------- Chatbot app state ----------
app_state = {
    "products_data": [],
    "search_engine": None,
    "intent_model": None,
    "ner_model": None,
    "query_processor": None,
    "normalizer": TextNormalizer(),
}

# Product keywords (unchanged)
# Product keywords (unchanged)
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

# Chitchat responses
CHITCHAT_RESPONSES = [
    "Hi there! How can I help you find the perfect product today?",
    "Hello! I'm here to assist with your shopping needs. What are you looking for?",
    "Hey! Ready to explore some amazing products? Just tell me what you're interested in.",
]
# ---------- Lifespan: init both DB and chatbot models ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize database
    try:
        database.init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    # 2. Load chatbot models and products
    logger.info("🔄 Loading products...")
    products_data = await load_products(force_refresh=False)
    app_state["products_data"] = products_data
    logger.info(f"✅ Loaded {len(products_data)} products")

    logger.info("🧠 Loading intent model...")
    intent_model = get_intent_model()
    app_state["intent_model"] = intent_model

    logger.info("🔍 Loading NER model...")
    try:
        ner_model = MLNERModel(os.getenv("NER_MODEL_PATH", "models/spacy_product_ner"))
        app_state["ner_model"] = ner_model
        logger.info("✅ NER model ready")
    except Exception as e:
        logger.error(f"❌ NER model failed: {e}")
        raise

    logger.info("🔧 Initialising search engine...")
    search_engine = SearchEngine(products_data)
    app_state["search_engine"] = search_engine

    query_processor = QueryProcessor(ner_model, products_data)
    app_state["query_processor"] = query_processor

    # 3. Start background catalog refresh if APIs configured
    if os.getenv("ECOMMERCE_API_URLS"):
        refresh_task = asyncio.create_task(
            refresh_catalog_periodically(app_state, int(os.getenv("REFRESH_INTERVAL", 2500)))
        )
        logger.info(f"⏰ Background refresh every {os.getenv('REFRESH_INTERVAL')}s")
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
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and CRA default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Auth routes ----------
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
    user_id = auth.verify_refresh_token(refresh_data.refresh_token)  # you need to implement this in auth.py
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

# ---------- Chatbot routes (unchanged) ----------
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

def get_intent(query: str) -> dict:
    q_lower = query.lower()
    if any(keyword in q_lower for keyword in PRODUCT_KEYWORDS):
        logger.info(f"🎯 Product keyword detected, forcing product_search")
        return {"label": "product_search", "confidence": 0.95}
    intent_model = app_state.get("intent_model")
    if intent_model:
        try:
            result = intent_model.predict(query)
            return {"label": result["intent"], "confidence": result["confidence"]}
        except Exception as e:
            logger.error(f"Intent model error: {e}")
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
        logger.info(f"🔍 Search params: brand={brand}, category={search_category}, subcategory={subcategory_keywords}, constraints={constraints}")
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
        "message": "Conversational Commerce + Auth API",
        "catalog_source": "APIs" if os.getenv("ECOMMERCE_API_URLS") else "static file",
    }

# ---------- Run ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("API_HOST", "0.0.0.0"), port=int(os.getenv("API_PORT", 8000)))