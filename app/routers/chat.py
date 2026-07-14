import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import ChatMessage, User
from app.schemas import ChatMessageCreate

router = APIRouter(prefix="/api/chat", tags=["chat"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".doc", ".docx"}
MAX_FILE_SIZE_MB = 15


@router.post("/upload")
async def upload_attachment(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Навъи файл иҷозат дода нашудааст")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"Файл набояд аз {MAX_FILE_SIZE_MB}MB зиёд бошад")

    filename = f"{uuid.uuid4()}{ext}"
    file_url = f"{settings.CDN_BASE_URL}/chat/{filename}"

    return {"url": file_url}


@router.post("", status_code=201)
async def send_message(
    data: ChatMessageCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    if not data.text and not data.attachment_url:
        raise HTTPException(400, "Паём наметавонад холӣ бошад")
    msg = ChatMessage(
        sender_id=user.id,
        receiver_id=data.receiver_id,
        order_id=data.order_id,
        text=data.text,
        attachment_url=data.attachment_url,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.get("/{other_user_id}")
async def get_conversation(
    other_user_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    stmt = (
        select(ChatMessage)
        .where(
            or_(
                and_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == other_user_id),
                and_(ChatMessage.sender_id == other_user_id, ChatMessage.receiver_id == user.id),
            )
        )
        .order_by(ChatMessage.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
