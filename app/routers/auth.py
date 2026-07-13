from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, write_audit_log
from app.models import User, UserRole, OtpCode
from app.notifications import send_otp_code, notify_admin
from app.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    generate_totp_secret, get_totp_uri, verify_totp_code,
    generate_otp_code, hash_otp, verify_otp,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_r
