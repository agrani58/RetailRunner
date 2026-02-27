import os
import json
import random
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

import database
import auth
from schemas import UserCreate, LoginRequest, TokenResponse, SimpleResponse, UserResponse, RefreshTokenRequest
from config import JWT_CONFIG, DB_CONFIG, config as app_config

from catalog_loader import load_products, refresh_catalog_periodically
from intent_model import get_intent_model
from ner_model import MLNERModel
from text_normalizer import TextNormalizer
from query_processor import QueryProcessor
from search_engine import SearchEngine
from order_bot import place_order_bot
from config import config, STORE_FRONTEND_MAP, STORE_NAMES
from recommendation_model import RecommendationModel
from review_bot import submit_review_bot

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

# ---------- App state ----------
app_state = {
    "products_data": [],
    "search_engine": None,
    "intent_model": None,
    "ner_model": None,
    "query_processor": None,
    "normalizer": TextNormalizer(),
    "recommendation_model": None,
}

def enrich_with_catalog(items: list, key_field: str = "product_id") -> list:
    products = {p["id"]: p for p in app_state.get("products_data", []) if p.get("id")}
    enriched = []
    for item in items:
        pid = item.get(key_field)
        product = products.get(pid, {})
        combined = {**product, **item}
        if "store" not in combined and product.get("source"):
            combined["store"] = STORE_NAMES.get(product["source"], product["source"])
        enriched.append(combined)
    return enriched

CHITCHAT_RESPONSES = [
    "Hi there! How can I help you find the perfect product today?",
    "Hello! I'm here to assist with your shopping needs. What are you looking for?",
    "Hey! Ready to explore some amazing products? Just tell me what you're interested in.",
]

PRODUCT_TERMS_FOR_OVERRIDE = {
    "laptop", "laptops", "phone", "phones", "smartphone", "smartphones",
    "tv", "television", "televisions", "shoes", "footwear", "headphones",
    "watch", "smartwatch", "smartwatches", "tablet", "tablets", "camera",
    "cameras", "monitor", "monitors", "jeans", "dress", "dresses", "jacket",
    "jackets", "tshirt", "t-shirt", "t-shirts", "tees", "shirt", "shirts",
    "kurta", "ethnic", "gown", "gowns", "makeup", "foundation", "lipstick",
    "cream", "moisturizer", "sunscreen", "facewash", "face wash", "body lotion",
    "lotion", "serum", "mask", "cleanser", "toner",
    "hair", "oil", "oils", "shampoo", "shampoos", "conditioner", "conditioners",
    "sweater", "sweaters", "hoodie",
}


# ---------- WebSocket connection manager ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        # payment_confirm_events[user_id] = asyncio.Event
        self.payment_confirm_events: Dict[int, asyncio.Event] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user {user_id}")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_personal_message(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending WS message to user {user_id}: {e}")
                self.disconnect(user_id)
        return False

    def create_payment_event(self, user_id: int) -> asyncio.Event:
        """Create (or reset) a payment confirmation event for a user's active order."""
        event = asyncio.Event()
        self.payment_confirm_events[user_id] = event
        return event

    def confirm_payment(self, user_id: int):
        """Called when the user clicks Confirm Payment in the chat UI."""
        event = self.payment_confirm_events.get(user_id)
        if event:
            event.set()
            logger.info(f"✅ Payment confirmed by user {user_id}")

    def clear_payment_event(self, user_id: int):
        self.payment_confirm_events.pop(user_id, None)


manager = ConnectionManager()


async def notify_user(user_id: int, message: str, msg_type: str = "bot_status"):
    """Send a typed WebSocket notification to a specific user."""
    payload = {"type": msg_type, "message": message}
    sent = await manager.send_personal_message(user_id, payload)
    return sent


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        database.init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    logger.info("🔄 Loading products from APIs...")
    products_data = await load_products()
    app_state["products_data"] = products_data
    logger.info(f"✅ Loaded {len(products_data)} products")

    logger.info("🧠 Loading intent model...")
    intent_model = get_intent_model()
    if intent_model is None:
        raise RuntimeError("❌ Intent model failed to load")
    app_state["intent_model"] = intent_model

    logger.info("🔍 Loading NER model...")
    try:
        ner_model = MLNERModel(app_config.NER_MODEL_PATH)
        app_state["ner_model"] = ner_model
        logger.info("✅ NER model ready")
    except Exception as e:
        logger.error(f"❌ NER model failed: {e}"); raise

    logger.info("💰 Loading recommendation model...")
    try:
        rec_model = RecommendationModel(app_config.PRICE_RATING_MODEL_PATH, device=app_config.DEVICE)
        app_state["recommendation_model"] = rec_model
        logger.info("✅ Recommendation model ready")
    except Exception as e:
        logger.error(f"❌ Recommendation model failed: {e}"); raise

    logger.info("🔧 Initialising search engine...")
    search_engine = SearchEngine(products_data)
    app_state["search_engine"] = search_engine

    query_processor = QueryProcessor(ner_model, products_data, rec_model)
    app_state["query_processor"] = query_processor

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_data={"id": user['user_id'], "email": user['email']},
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
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user_data={"id": user['user_id'], "email": user['email']},
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
    return {"message": f"Hello {current_user['email']}!", "user_id": current_user['user_id']}

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
        cur.close(); conn.close()
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ---------- WebSocket endpoint ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    user = await auth.get_user_from_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return

    user_id = user['user_id']
    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                # Handle payment confirmation signal from chat UI
                if data.get("type") == "payment_confirmed":
                    manager.confirm_payment(user_id)
                    await manager.send_personal_message(user_id, {
                        "type": "bot_status",
                        "message": "✅ Payment confirmation received — completing your order…"
                    })
            except Exception:
                pass  # ignore malformed messages
    except WebSocketDisconnect:
        manager.disconnect(user_id)


# ---------- Chatbot routes ----------
class ChatRequest(BaseModel):
    query: str

class PlaceOrderRequest(BaseModel):
    product_name: str
    user_info: Dict[str, str]

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
    intent_model = app_state.get("intent_model")
    if not intent_model:
        raise HTTPException(status_code=503, detail="Intent model not loaded")
    try:
        result = intent_model.predict(query)
        intent = result["intent"]
        confidence = result["confidence"]
        if confidence < 0.8 and intent == "chitchat":
            query_lower = query.lower()
            if any(term in query_lower for term in PRODUCT_TERMS_FOR_OVERRIDE):
                intent = "product_search"
                confidence = 1.0
        return {"label": intent, "confidence": confidence}
    except Exception as e:
        logger.error(f"Intent model error: {e}")
        raise HTTPException(status_code=503, detail="Intent model unavailable")


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
        store = p.get("store")
        if not store:
            source = p.get("source", "")
            store = STORE_NAMES.get(source)
            if not store and source:
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
            return f"Sorry, we currently don't have any {search_category} in our catalog."
        return f"Sorry, I couldn't find anything for '{query}'. Try different words?"
    if len(products) == 1:
        return f"I found the perfect match: {products[0].name}"
    return f"I found {len(products)} great options for '{query}'. Here are the top picks:"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(auth.get_current_user_optional)):
    try:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Empty query")

        intent = get_intent(query)

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
        search_engine = app_state.get("search_engine")
        if not search_engine:
            raise HTTPException(status_code=503, detail="Search engine not ready")

        results = search_engine.search(
            query=query,
            product_entities=analysis.get('product_entities', []),
            brand=analysis.get('brand'),
            constraints=analysis.get('constraints', {}),
            search_category=analysis.get('search_category'),
            subcategory_keywords=analysis.get('subcategory_keywords', []),
            exclude_terms=analysis.get('exclude_terms', []),
            skip_entity_filter=analysis.get('skip_entity_filter', False),
            top_k=10,
        )

        formatted = format_products(results)
        response_text = generate_response(query, formatted, analysis.get('search_category'))

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
async def place_order(request: PlaceOrderRequest, current_user: dict = Depends(auth.get_current_user)):
    try:
        product_name = request.product_name
        user_info    = request.user_info

        logger.info(f"📦 Place-order request: product='{product_name}'")

        products      = app_state.get("products_data", [])
        found_product = None
        for p in products:
            if p.get("name", "").lower() == product_name.lower():
                found_product = p; break
        if not found_product:
            for p in products:
                pname = p.get("name", "")
                if product_name.lower() in pname.lower() or pname.lower() in product_name.lower():
                    found_product = p; break

        if not found_product:
            raise HTTPException(status_code=404, detail=f"Product '{product_name}' not found in catalog")

        source_api = found_product.get("source")
        if not source_api:
            raise HTTPException(status_code=400, detail="Product has no source information")

        if source_api == "static":
            return {"message": "This product is from a static catalog and cannot be ordered automatically.", "product_name": product_name}

        frontend_url = STORE_FRONTEND_MAP.get(source_api)
        if not frontend_url:
            raise HTTPException(status_code=400, detail=f"No frontend mapping for source: {source_api}")

        user_id = current_user['user_id']

        # Create payment confirmation event — bot will wait on this
        payment_event = manager.create_payment_event(user_id)

        async def notify(msg: str, msg_type: str = "bot_status"):
            sent = await notify_user(user_id, msg, msg_type)
            if not sent and msg_type == "order_confirmation":
                # Fallback: queue in DB if WS not connected
                database.store_order_confirmation(
                    user_id=user_id,
                    product_name=product_name,
                    delivery_date="",
                    order_id=None,
                )

        await notify("🤖 Order bot starting — browser will open shortly.")

        asyncio.create_task(place_order_bot(
            frontend_url,
            user_info,
            product_name,
            user_id=user_id,
            notify_callback=notify,
            payment_confirm_event=payment_event,
        ))

        return {
            "message": f"🤖 Order bot started for '{product_name}'. Watch the chat for live updates.",
            "frontend_url": frontend_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in /place-order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Order confirmation endpoint (called by bot) ----------
class OrderConfirmRequest(BaseModel):
    email: EmailStr
    product_name: str
    delivery_date: str
    order_id: Optional[str] = None

@app.post("/order-confirm")
async def order_confirm(request: OrderConfirmRequest):
    try:
        user = database.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        confirmation_msg = (
            f"✅ Order confirmed for '{request.product_name}'. "
            f"Expected delivery: {request.delivery_date}."
            + (f" Order ID: {request.order_id}" if request.order_id else "")
        )

        sent = await manager.send_personal_message(user['user_id'], {
            "type": "order_confirmation",
            "message": confirmation_msg,
            "product_name": request.product_name,
            "delivery_date": request.delivery_date,
            "order_id": request.order_id,
        })
        if not sent:
            database.store_order_confirmation(
                user_id=user['user_id'],
                product_name=request.product_name,
                delivery_date=request.delivery_date,
                order_id=request.order_id,
            )

        # Persist to user_orders
        products_list = app_state.get("products_data", [])
        product = next(
            (p for p in products_list if p.get("name", "").strip().lower() == request.product_name.strip().lower()),
            None
        )
        if not product:
            product = next(
                (p for p in products_list if request.product_name.strip().lower() in p.get("name", "").strip().lower()),
                None
            )

        if product:
            product_id = product.get("id")
            product_source = product.get("source", "unknown")
            store_frontend_url = STORE_FRONTEND_MAP.get(product_source)
            if product_id is not None:
                try:
                    product_id = int(product_id) % 2_147_483_647
                    if product_id == 0: product_id = 1
                except (ValueError, TypeError):
                    product_id = None
            if product_id is not None:
                database.add_user_order(
                    user_id=user['user_id'], product_id=product_id,
                    product_name=request.product_name, product_source=product_source,
                    store_frontend_url=store_frontend_url,
                    delivery_date=request.delivery_date, order_reference=request.order_id,
                )
        else:
            database.add_user_order(
                user_id=user['user_id'], product_id=0,
                product_name=request.product_name, product_source="unknown",
                store_frontend_url=None, delivery_date=request.delivery_date,
                order_reference=request.order_id,
            )

        # Clear the payment event now that order is done
        manager.clear_payment_event(user['user_id'])

        return {"status": "ok", "message": "Confirmation recorded"}
    except Exception as e:
        logger.error(f"Error in /order-confirm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Review routes ----------
class SubmitReviewRequest(BaseModel):
    order_id: int = 0
    product_name: str = ""
    store_url: str = ""
    rating: int = 5
    review_text: Optional[str] = ""
    store_credentials: Dict[str, str] = {}

class MarkReviewedRequest(BaseModel):
    order_id: int = 0
# ── REPLACE the existing /submit-review endpoint in main.py with this ──
# (Everything else in main.py stays the same)

@app.post("/submit-review")
async def submit_review(request: SubmitReviewRequest, current_user: dict = Depends(auth.get_current_user)):
    try:
        if not 1 <= request.rating <= 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        if not request.store_url:
            raise HTTPException(status_code=400, detail="No store URL available for this order")

        user_info = {
            "email":        request.store_credentials.get("email", ""),
            "password":     request.store_credentials.get("password", ""),
            "display_name": request.store_credentials.get("display_name", ""),
        }
        if not user_info["email"] or not user_info["password"]:
            raise HTTPException(status_code=400, detail="Store email and password are required")

        user_id = current_user["user_id"]

        # ── Fetch the store's own order reference (e.g. "21") from the DB ──
        order_reference = None
        if request.order_id:
            orders = database.get_user_orders(user_id)
            for order in orders:
                if order.get("id") == request.order_id or order.get("order_id") == request.order_id:
                    order_reference = order.get("order_reference")
                    break
        logger.info("📝 Review bot: order_id=%s, order_reference=%s", request.order_id, order_reference)

        async def notify(msg: str):
            await manager.send_personal_message(user_id, {"type": "review_status", "message": msg})

        asyncio.create_task(submit_review_bot(
            frontend_url=request.store_url,
            product_name=request.product_name,
            user_info=user_info,
            rating=request.rating,
            review_text=request.review_text or "",
            user_id=user_id,
            order_id=request.order_id,
            notify_callback=notify,
            order_reference=order_reference,
        ))

        return {"message": "Review bot started. You'll be notified when it completes.", "order_id": request.order_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in /submit-review: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mark-reviewed")
async def mark_reviewed(request: MarkReviewedRequest):
    try:
        ok = database.mark_order_reviewed(request.order_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"status": "ok", "order_id": request.order_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Wishlist endpoints ----------
class WishlistItemRequest(BaseModel):
    product_id: int
    product_name: str
    product_source: str
    store_name: Optional[str] = None

@app.get("/wishlist", response_model=List[Dict])
def get_wishlist(current_user: dict = Depends(auth.get_current_user)):
    items = database.get_wishlist(current_user['user_id'])
    return enrich_with_catalog(items, key_field="product_id")

@app.post("/wishlist")
def add_to_wishlist(item: WishlistItemRequest, current_user: dict = Depends(auth.get_current_user)):
    success = database.add_to_wishlist(
        user_id=current_user['user_id'], product_id=item.product_id,
        product_name=item.product_name, product_source=item.product_source,
        store_name=item.store_name
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add to wishlist")
    return {"message": "Added to wishlist"}

@app.delete("/wishlist/{product_id}")
def remove_from_wishlist(product_id: int, current_user: dict = Depends(auth.get_current_user)):
    success = database.remove_from_wishlist(current_user['user_id'], product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found in wishlist")
    return {"message": "Removed from wishlist"}


# ---------- Orders endpoint ----------
@app.get("/orders")
def get_orders(current_user: dict = Depends(auth.get_current_user)):
    orders = database.get_user_orders(current_user['user_id'])
    return enrich_with_catalog(orders, key_field="product_id")


# ---------- Health ----------
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
    return {"message": "Conversational Commerce + Auth API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app_config.API_HOST, port=app_config.API_PORT)