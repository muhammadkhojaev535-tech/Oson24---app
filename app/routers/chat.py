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
MAX_FILE_SIZE_MB
