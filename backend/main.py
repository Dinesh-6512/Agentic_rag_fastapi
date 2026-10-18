import time
import uuid
import logging
import concurrent.futures
from collections import defaultdict
from typing import List, Optional, Dict
from fastapi import FastAPI, Depends, HTTPException, status, Query, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend import models, database, schemas, auth
from backend.rag_flow import run_agentic_rag_flow

# Configure structured observability logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rag_observability")

# Create tables and seed initial catalog if empty
try:
    models.Base.metadata.create_all(bind=database.engine)
    
    def _seed_products():
        db = database.SessionLocal()
        try:
            if db.query(models.Product).count() == 0:
                cat_elec = models.Category(name="Electronics")
                cat_wear = models.Category(name="Wearables")
                cat_audio = models.Category(name="Audio")
                db.add_all([cat_elec, cat_wear, cat_audio])
                db.flush()
                
                db.add_all([
                    models.Product(
                        name="Lumina Silent Wireless Mouse",
                        description="Ergonomic silent-click wireless mouse with Bluetooth and 2.4GHz connectivity.",
                        price=29.99,
                        stock=50,
                        category_id=cat_elec.id
                    ),
                    models.Product(
                        name="Lumina Fit Smart Watch",
                        description="Advanced fitness tracking smartwatch with 1.43-inch AMOLED display and 5 ATM water resistance.",
                        price=89.99,
                        stock=30,
                        category_id=cat_wear.id
                    ),
                    models.Product(
                        name="Lumina Wave ANC Headphones",
                        description="Over-ear active noise cancelling headphones with 40-60 hours battery life.",
                        price=129.99,
                        stock=25,
                        category_id=cat_audio.id
                    )
                ])
                db.commit()
        except Exception as err:
            db.rollback()
            print("Product seeding error:", err)
        finally:
            db.close()
            
    _seed_products()
except Exception as e:
    print("Could not create tables:", e)

app = FastAPI(title="E-commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to E-commerce API"}

@app.get("/health")
def health_check(db: Session = Depends(database.get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection failed")

# --- AUTHENTICATION ROUTES ---

@app.post("/api/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(name=user.name, email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # Authenticate customer
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = auth.create_access_token(data={"sub": str(user.id), "is_admin": user.is_admin})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/admin/login", response_model=schemas.Token)
def admin_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # Authenticate admin
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not an admin user")
    
    access_token = auth.create_access_token(data={"sub": str(user.id), "is_admin": True})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/profile", response_model=schemas.UserResponse)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.post("/api/logout")
def logout():
    # Since we use JWT (stateless), logout happens by deleting the token on the frontend.
    return {"message": "Successfully logged out. Please remove the token on the client side."}

# --- CART HELPERS ---

def get_or_create_cart(db: Session, user_id: int) -> models.Cart:
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

def calculate_cart_total(cart: models.Cart) -> float:
    total = 0.0
    for item in cart.items:
        if item.product:
            total += item.product.price * item.quantity
    return total

# --- CUSTOMER ENDPOINTS ---

@app.get("/api/categories", response_model=List[schemas.CategoryResponse])
def get_categories(db: Session = Depends(database.get_db)):
    return db.query(models.Category).all()

@app.get("/api/products", response_model=List[schemas.ProductResponse])
def get_products(search: Optional[str] = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Product)
    if search:
        query = query.filter(models.Product.name.ilike(f"%{search}%"))
    return query.all()

@app.get("/api/products/{product_id}", response_model=schemas.ProductResponse)
def get_product(product_id: int, db: Session = Depends(database.get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# --- ADMIN ENDPOINTS ---

def check_admin(current_user: models.User = Depends(auth.get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

@app.post("/api/admin/categories", response_model=schemas.CategoryResponse)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    existing = db.query(models.Category).filter(models.Category.name == category.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category with this name already exists")
    new_category = models.Category(name=category.name)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category

@app.put("/api/admin/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_category(category_id: int, category: schemas.CategoryCreate, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    db_category.name = category.name
    db.commit()
    db.refresh(db_category)
    return db_category

@app.delete("/api/admin/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(db_category)
    db.commit()
    return {"message": "Category deleted"}

@app.post("/api/admin/products", response_model=schemas.ProductResponse)
def create_product(product: schemas.ProductCreate, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    new_product = models.Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        category_id=product.category_id
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@app.put("/api/admin/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(product_id: int, product: schemas.ProductCreate, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db_product.name = product.name
    db_product.description = product.description
    db_product.price = product.price
    db_product.stock = product.stock
    db_product.category_id = product.category_id
    
    db.commit()
    db.refresh(db_product)
    return db_product

@app.delete("/api/admin/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted"}

# --- CART ENDPOINTS ---

@app.get("/api/cart", response_model=schemas.CartResponse)
def view_cart(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    total = calculate_cart_total(cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": cart.items,
        "total": total
    }

@app.post("/api/cart/items", response_model=schemas.CartResponse)
def add_to_cart(item: schemas.CartItemCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    cart_item = db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id, models.CartItem.product_id == item.product_id).first()
    
    new_quantity = item.quantity
    if cart_item:
        new_quantity += cart_item.quantity
        
    if new_quantity > product.stock:
        raise HTTPException(status_code=400, detail="Not enough stock available")
        
    if cart_item:
        cart_item.quantity = new_quantity
    else:
        cart_item = models.CartItem(cart_id=cart.id, product_id=item.product_id, quantity=item.quantity)
        db.add(cart_item)
        
    db.commit()
    db.refresh(cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": cart.items,
        "total": calculate_cart_total(cart)
    }

@app.put("/api/cart/items/{item_id}", response_model=schemas.CartResponse)
def update_cart_item(item_id: int, quantity: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    cart_item = db.query(models.CartItem).filter(models.CartItem.id == item_id, models.CartItem.cart_id == cart.id).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
        
    if quantity <= 0:
        db.delete(cart_item)
    else:
        if quantity > cart_item.product.stock:
            raise HTTPException(status_code=400, detail="Not enough stock available")
        cart_item.quantity = quantity
        
    db.commit()
    db.refresh(cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": cart.items,
        "total": calculate_cart_total(cart)
    }

@app.delete("/api/cart/items/{item_id}", response_model=schemas.CartResponse)
def remove_cart_item(item_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    cart_item = db.query(models.CartItem).filter(models.CartItem.id == item_id, models.CartItem.cart_id == cart.id).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
        
    db.delete(cart_item)
    db.commit()
    db.refresh(cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": cart.items,
        "total": calculate_cart_total(cart)
    }

# --- ORDER ENDPOINTS (CUSTOMER) ---

@app.post("/api/orders", response_model=schemas.OrderResponse)
def place_order(order_data: schemas.OrderCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
        
    total_price = 0.0
    for item in cart.items:
        if item.quantity > item.product.stock:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {item.product.name}")
        total_price += item.product.price * item.quantity
        
    new_order = models.Order(
        user_id=current_user.id,
        total_price=total_price,
        delivery_address=order_data.delivery_address,
        status="Placed"
    )
    db.add(new_order)
    db.flush() # get new_order.id
    
    for item in cart.items:
        order_item = models.OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_purchase=item.product.price
        )
        db.add(order_item)
        item.product.stock -= item.quantity # decrease stock
        db.delete(item) # clear cart item
        
    db.commit()
    db.refresh(new_order)
    return new_order

@app.get("/api/orders", response_model=List[schemas.OrderResponse])
def get_order_history(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    orders = db.query(models.Order).filter(models.Order.user_id == current_user.id).order_by(models.Order.id.desc()).all()
    return orders

@app.get("/api/orders/{order_id}", response_model=schemas.OrderResponse)
def get_order_details(order_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id, models.Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# --- ORDER ENDPOINTS (ADMIN) ---

@app.get("/api/admin/orders", response_model=List[schemas.OrderResponse])
def admin_get_all_orders(db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    orders = db.query(models.Order).order_by(models.Order.id.desc()).all()
    return orders

@app.get("/api/admin/orders/{order_id}", response_model=schemas.OrderResponse)
def admin_get_order(order_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.put("/api/admin/orders/{order_id}/status", response_model=schemas.OrderResponse)
def admin_update_order_status(order_id: int, status_data: schemas.OrderStatusUpdate, db: Session = Depends(database.get_db), admin: models.User = Depends(check_admin)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status_data.status
    db.commit()
    db.refresh(order)
    return order


# --- AGENTIC RAG SECURITY & RATE LIMITING ---

USER_REQUEST_TIMESTAMPS: Dict[int, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_REQUESTS = 15
MAX_QUESTION_LENGTH = 1000
RAG_EXECUTION_TIMEOUT_SECONDS = 15.0

def enforce_user_rate_limit(user_id: int):
    """
    Sliding window rate limiter per authenticated user.
    Limits repeated burst requests to prevent API flooding and denial of service.
    """
    now = time.time()
    history = USER_REQUEST_TIMESTAMPS[user_id]
    valid = [t for t in history if now - t < RATE_LIMIT_WINDOW_SECONDS]
    USER_REQUEST_TIMESTAMPS[user_id] = valid
    if len(valid) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before sending more questions."
        )
    USER_REQUEST_TIMESTAMPS[user_id].append(now)


# --- AGENTIC RAG ROUTES ---

@app.post("/rag/ask", response_model=schemas.RagAskResponse)
@app.post("/api/rag/ask", response_model=schemas.RagAskResponse)
def ask_rag_assistant(
    request: schemas.RagAskRequest,
    response: Response,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Agentic RAG Assistant endpoint with complete security hardening and end-to-end observability:
    - Trace ID correlation: User -> FastAPI -> Agentic RAG -> FAISS -> Answer -> User.
    - Captures total latency, retrieval latency, answer-generation latency, and chunk counts.
    - Reports outcome status (success, no_data, clarification, security_refusal, error).
    - Preserves privacy: does NOT log bearer tokens, passwords, or sensitive personal data.
    """
    # 0. Generate or extract trace ID & start timer
    trace_id = request.trace_id or f"rag-{uuid.uuid4().hex[:10]}"
    response.headers["X-Trace-ID"] = trace_id
    start_time = time.perf_counter()

    # Step 1: User -> FastAPI (log safely without personal data or tokens)
    logger.info(
        "[TRACE %s] User (id=%s) -> FastAPI: POST /rag/ask | question_len=%d | product_id=%s",
        trace_id, current_user.id, len(request.question or ""), request.product_id
    )

    # 1. Enforce rate limiting
    try:
        enforce_user_rate_limit(current_user.id)
    except HTTPException as e:
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        logger.warning(
            "[TRACE %s] FastAPI -> User (Rate Limited): %s | user_id=%s | total_time_ms=%.2fms",
            trace_id, e.detail, current_user.id, total_time_ms
        )
        e.headers = {"X-Trace-ID": trace_id}
        raise e

    # 2. Input validation & size limits
    if not request.question or not request.question.strip():
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        err_msg = "Question cannot be empty."
        logger.warning(
            "[TRACE %s] FastAPI -> User (Failed): Validation error: %s | user_id=%s | total_time_ms=%.2fms",
            trace_id, err_msg, current_user.id, total_time_ms
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
            headers={"X-Trace-ID": trace_id}
        )
        
    if len(request.question) > MAX_QUESTION_LENGTH:
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        err_msg = f"Question is too long. Maximum allowed length is {MAX_QUESTION_LENGTH} characters."
        logger.warning(
            "[TRACE %s] FastAPI -> User (Failed): Validation error: %s | user_id=%s | total_time_ms=%.2fms",
            trace_id, err_msg, current_user.id, total_time_ms
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
            headers={"X-Trace-ID": trace_id}
        )
        
    if "\0" in request.question:
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        err_msg = "Invalid characters detected in question."
        logger.warning(
            "[TRACE %s] FastAPI -> User (Failed): Validation error: %s | user_id=%s | total_time_ms=%.2fms",
            trace_id, err_msg, current_user.id, total_time_ms
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
            headers={"X-Trace-ID": trace_id}
        )
        
    # 3. Product context resolution
    detected_product_name = None
    if request.product_id:
        product = db.query(models.Product).filter(models.Product.id == request.product_id).first()
        if product:
            detected_product_name = product.name

    # Step 2: FastAPI -> Agentic RAG
    logger.info(
        "[TRACE %s] FastAPI -> Agentic RAG: Starting workflow | detected_product=%s",
        trace_id, detected_product_name
    )

    # 4. Bounded execution with strict timeout protection
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(
            run_agentic_rag_flow,
            question=request.question.strip(),
            product_id=request.product_id,
            detected_product=detected_product_name,
            trace_id=trace_id
        )
        try:
            rag_result = future.result(timeout=RAG_EXECUTION_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            total_time_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = "The assistant request timed out while generating an answer. Please try again."
            logger.error(
                "[TRACE %s] FastAPI -> User (Error): Gateway timeout after %.2fms",
                trace_id, total_time_ms
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=err_msg,
                headers={"X-Trace-ID": trace_id}
            )
        except Exception as e:
            total_time_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = "An internal error occurred while processing your request. Please try again later."
            logger.error(
                "[TRACE %s] FastAPI -> User (Error): Execution exception after %.2fms: %s",
                trace_id, total_time_ms, type(e).__name__
            )
            # Mask internal error traces from client
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=err_msg,
                headers={"X-Trace-ID": trace_id}
            )
        
    total_time_ms = (time.perf_counter() - start_time) * 1000.0
    rag_status = rag_result.get("status", "answered")
    is_success = (rag_status == "answered")
    is_no_data = (rag_status == "no_information_found")

    if is_success:
        outcome_status = "success"
    elif is_no_data:
        outcome_status = "no_data"
    elif rag_status == "clarification_needed":
        outcome_status = "clarification"
    elif rag_status == "security_refusal":
        outcome_status = "security_refusal"
    else:
        outcome_status = rag_status

    obs = schemas.RagObservability(
        trace_id=trace_id,
        total_time_ms=round(total_time_ms, 2),
        retrieval_time_ms=round(rag_result.get("retrieval_time_ms", 0.0), 2),
        answer_time_ms=round(rag_result.get("answer_time_ms", 0.0), 2),
        retrieved_chunks_count=len(rag_result.get("retrieved_chunks", [])),
        retry_happened=bool(rag_result.get("retry_happened", False)),
        outcome_status=outcome_status,
        is_success=is_success,
        is_no_data=is_no_data,
        error_detail=rag_result.get("error_detail")
    )

    # Step 5: Answer -> User
    logger.info(
        "[TRACE %s] FastAPI -> User (Complete): outcome=%s | chunks=%d | retry=%s | retrieval=%.2fms | answer=%.2fms | total=%.2fms",
        trace_id, outcome_status, obs.retrieved_chunks_count, obs.retry_happened,
        obs.retrieval_time_ms, obs.answer_time_ms, obs.total_time_ms
    )

    return schemas.RagAskResponse(
        answer=rag_result.get("answer", ""),
        sources=rag_result.get("sources", []),
        status=rag_status,
        detected_product=rag_result.get("detected_product"),
        observability=obs
    )
