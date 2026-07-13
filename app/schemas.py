from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models import UserRole, OrderStatus


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.BUYER

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Парол бояд ҳарф ва рақам дошта бошад")
        return v


class LoginRequest(BaseModel):
    identifier: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False


class ProductCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str
    price: float = Field(gt=0)
    stock_qty: int = Field(ge=0)
    category_id: str | None = None
    images: list[str] = []


class ProductOut(BaseModel):
    id: str
    title: str
    description: str
    price: float
    stock_qty: int
    images: list[str]
    avg_rating: float
    ratings_count: int

    class Config:
        from_attributes = True


class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, default=1)


class OrderCreate(BaseModel):
    delivery_address: str = Field(min_length=5, max_length=500)
    coupon_code: str | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class CourierLocationUpdate(BaseModel):
    lat: float
    lng: float


class ChatMessageCreate(BaseModel):
    receiver_id: str
    order_id: str | None = None
    text: str | None = None
    attachment_url: str | None = None


class RatingCreate(BaseModel):
    product_id: str
    order_id: str
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
