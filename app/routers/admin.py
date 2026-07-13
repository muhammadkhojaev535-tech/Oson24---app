import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_role
from app.models import User, Product, Order, AuditLog, UserRole, OrderStatus, CmsContent, AppUpdate
from app.notifications import send_telegram_message

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role(UserRole.ADMIN))])

ALLOWED_SECTIONS = {"delivery", "announce", "ads", "review"}


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    users_count = (await db.execute(select(func.count(User.id)))).scalar()
    products_count = (await db.execute(select(func.count(Product.id)))).scalar()
    orders_count = (await db.execute(select(func.count(Order.id)))).scalar()
    revenue = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.status != OrderStatus.CANCELLED)
        )
    ).scalar()

    return {
        "users_count": users_count,
        "products_count": products_count,
        "orders_count": orders_count,
        "total_revenue": revenue,
    }


@router.get("/audit-logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db), limit: int = 100):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = False
        await db.commit()
    return {"message": "Корбар ғайрифаъол шуд"}


@router.get("/sellers/pending")
async def pending_sellers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.role == UserRole.SELLER, User.approval_status == "pending")
    )
    return result.scalars().all()


@router.patch("/sellers/{user_id}/approve")
async def approve_seller(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Корбар ёфт нашуд")
    user.approval_status = "approved"
    await db.commit()
    if user.telegram_chat_id:
        await send_telegram_message(user.telegram_chat_id, "✅ Ҳисоби фурӯшандагии шумо тасдиқ шуд! Акнун метавонед маҳсулот гузоред.")
    return {"message": "Фурӯшанда тасдиқ шуд"}


@router.patch("/sellers/{user_id}/reject")
async def reject_seller(user_id: str, reason: str = "", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Корбар ёфт нашуд")
    user.approval_status = "rejected"
    user.is_active = False
    await db.commit()
    return {"message": "Фурӯшанда рад карда шуд"}


@router.post("/content")
async def upload_content(
    section: str = Form(...),
    title: str = Form(...),
    link_url: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    if section not in ALLOWED_SECTIONS:
        raise HTTPException(400, f"Бахш бояд яке аз инҳо бошад: {', '.join(ALLOWED_SECTIONS)}")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".jpg"
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Файл набояд аз 10MB зиёд бошад")

    filename = f"{uuid.uuid4()}{ext}"
    image_url = f"{settings.CDN_BASE_URL}/cms/{section}/{filename}"

    item = CmsContent(section=section, title=title, image_url=image_url, link_url=link_url, created_by=user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/content/{section}")
async def list_content(section: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CmsContent).where(CmsContent.section == section, CmsContent.is_active == True)  # noqa: E712
        .order_by(CmsContent.sort_order)
    )
    return result.scalars().all()


@router.delete("/content/{content_id}")
async def delete_content(content_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CmsContent).where(CmsContent.id == content_id))
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return {"message": "Нест карда шуд"}


@router.post("/deploy-log")
async def log_deploy(version: str, description: str = "", deployed_by: str = "ci", db: AsyncSession = Depends(get_db)):
    entry = AppUpdate(version=version, description=description, deployed_by=deployed_by)
    db.add(entry)
    await db.commit()
    return {"message": "Обновление сабт шуд", "version": version}


@router.get("/deploy-log")
async def get_deploy_log(db: AsyncSession = Depends(get_db), limit: int = 20):
    result = await db.execute(select(AppUpdate).order_by(AppUpdate.deployed_at.desc()).limit(limit))
    return result.scalars().all()
