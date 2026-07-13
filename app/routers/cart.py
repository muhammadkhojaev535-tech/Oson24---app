from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import CartItem, User
from app.schemas import CartItemCreate

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("")
async def get_cart(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    return result.scalars().all()


@router.post("", status_code=201)
async def add_to_cart(
    data: CartItemCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == data.product_id)
    )
    item = result.scalar_one_or_none()
    if item:
        item.quantity += data.quantity
    else:
        item = CartItem(user_id=user.id, product_id=data.product_id, quantity=data.quantity)
        db.add(item)
    await db.commit()
    return {"message": "Ба сабад илова шуд"}


@router.delete("/{item_id}")
async def remove_from_cart(
    item_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return {"message": "Аз сабад бароварда шуд"}
