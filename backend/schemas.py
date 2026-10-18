from pydantic import BaseModel
from typing import List, Optional

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Category Schemas
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True

# Product Schemas
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 10
    category_id: Optional[int] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True

# Cart Schemas
class CartItemBase(BaseModel):
    product_id: int
    quantity: int

class CartItemCreate(CartItemBase):
    pass

class CartItemResponse(CartItemBase):
    id: int
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True

class CartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse] = []
    total: float = 0.0

    class Config:
        from_attributes = True

# Order Schemas
class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_at_purchase: float
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    delivery_address: str

class OrderStatusUpdate(BaseModel):
    status: str

class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_price: float
    status: str
    delivery_address: Optional[str] = None
    items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True

# Agentic RAG Schemas
class RagObservability(BaseModel):
    trace_id: str
    total_time_ms: float
    retrieval_time_ms: float
    answer_time_ms: float
    retrieved_chunks_count: int
    retry_happened: bool
    outcome_status: str  # "success", "no_data", "clarification", "security_refusal", "error"
    is_success: bool
    is_no_data: bool
    error_detail: Optional[str] = None

class RagAskRequest(BaseModel):
    question: str
    product_id: Optional[int] = None
    trace_id: Optional[str] = None

class RagAskResponse(BaseModel):
    answer: str
    sources: List[str] = []
    status: str
    detected_product: Optional[str] = None
    observability: Optional[RagObservability] = None
