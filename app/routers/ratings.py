from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Rating, Product, Order, User
from app.schemas import RatingCreate

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


@router.post("", status_code=201)
async def create_rating(
    data: RatingCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    order_result = await db.execute(select(Order).where(Order.id == data.order_id, Order.buyer_id == user.id))
    if not order_result.scalar_one_or_none():
        raise HTTPException(403, "Шумо ин маҳсулотро харидорӣ накардаед")

    rating = Rating(user_id=user.id, **data.model_dump())
    db.add(rating)

    product_result = await db.execute(select(Product).where(Product.id == data.product_id))
    product = product_result.scalar_one_or_none()
    if product:
        total_stars = product.avg_rating * product.ratings_count + data.stars
        product.ratings_count += 1
        product.avg_rating = round(total_stars / product.ratings_count, 2)

    await db.commit()
    return {"message": "Ташаккур барои баҳогузорӣ"}
