from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role, require_approved_seller
from app.models import Product, User, UserRole
from app.schemas import ProductCreate, ProductOut

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search", response_model=list[ProductOut])
async def search_products(
    q: str = Query(min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Product)
        .where(Product.is_active == True)  # noqa: E712
        .where(or_(Product.title.ilike(f"%{q}%"), Product.description.ilike(f"%{q}%")))
        .limit(30)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("", response_model=list[ProductOut])
async def list_products(
    category_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.is_active == True)  # noqa: E712
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_approved_seller),
):
    if user.role not in (UserRole.SELLER, UserRole.ADMIN):
        raise HTTPException(403, "Танҳо фурӯшанда метавонад маҳсулот гузорад")
    product = Product(seller_id=user.id, **data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Маҳсулот ёфт нашуд")
    return product
