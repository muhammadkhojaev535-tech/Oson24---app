from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role, write_audit_log
from app.models import Order, OrderItem, CartItem, Product, Coupon, OrderStatus, User, UserRole
from app.schemas import OrderCreate, OrderStatusUpdate, CourierLocationUpdate

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", status_code=201)
async def create_order(
    request: Request,
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cart_result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = cart_result.scalars().all()
    if not cart_items:
        raise HTTPException(400, "Сабади шумо холӣ аст")

    total = 0.0
    order_items = []
    for ci in cart_items:
        product_result = await db.execute(select(Product).where(Product.id == ci.product_id))
        product = product_result.scalar_one_or_none()
        if not product or product.stock_qty < ci.quantity:
            raise HTTPException(400, f"Маҳсулот дастрас нест: {ci.product_id}")
        total += product.price * ci.quantity
        product.stock_qty -= ci.quantity
        order_items.append(OrderItem(product_id=product.id, quantity=ci.quantity, unit_price=product.price))

    coupon_id = None
    if data.coupon_code:
        coupon_result = await db.execute(
            select(Coupon).where(Coupon.code == data.coupon_code, Coupon.is_active == True)  # noqa: E712
        )
        coupon = coupon_result.scalar_one_or_none()
        if coupon and coupon.valid_until > datetime.utcnow() and coupon.used_count < coupon.max_uses:
            total *= 1 - coupon.discount_percent / 100
            coupon.used_count += 1
            coupon_id = coupon.id

    order = Order(
        buyer_id=user.id,
        total_amount=round(total, 2),
        delivery_address=data.delivery_address,
        coupon_id=coupon_id,
        items=order_items,
    )
    db.add(order)

    for ci in cart_items:
        await db.delete(ci)

    await db.commit()
    await db.refresh(order)

    await write_audit_log(db, request, user.id, "order_created", "order", order.id, {"total": total})

    return {"order_id": order.id, "total_amount": order.total_amount, "status": order.status}


@router.get("/{order_id}/track")
async def track_order(order_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.buyer_id != user.id:
        raise HTTPException(404, "Фармоиш ёфт нашуд")
    return {
        "status": order.status,
        "courier_lat": order.courier_lat,
        "courier_lng": order.courier_lng,
    }


@router.patch("/{order_id}/courier-location")
async def update_courier_location(
    order_id: str,
    data: CourierLocationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.COURIER)),
):
    res
