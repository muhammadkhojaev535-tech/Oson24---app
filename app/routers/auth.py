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
limiter = Limiter(key_func=get_remote_address)


class OtpRequestIn(BaseModel):
    identifier: str
    full_name: str | None = None


class OtpVerifyIn(BaseModel):
    identifier: str
    code: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not data.email and not data.phone:
        raise HTTPException(400, "Email ё рақами телефон лозим аст")

    existing = await db.execute(
        select(User).where(or_(User.email == data.email, User.phone == data.phone))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Ин корбар аллакай сабти ном шудааст")

    approval = "pending" if data.role == UserRole.SELLER else "approved"

    user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=data.role,
        approval_status=approval,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await write_audit_log(db, request, user.id, "register", "user", user.id)

    if data.role == UserRole.SELLER:
        await notify_admin(
            f"🔔 Фурӯшандаи нав дархости сабти ном дод:\n{user.full_name}\n{user.email or user.phone}\n"
            f"Барои тасдиқ: панели админ → Фурӯшандагон"
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.email == data.identifier, User.phone == data.identifier))
    )
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        await write_audit_log(db, request, None, "login_failed", "user", data.identifier)
        raise HTTPException(401, "Маълумоти воридшуда нодуруст аст")

    if user.is_2fa_enabled:
        if not data.totp_code:return TokenResponse(access_token="", refresh_token="", requires_2fa=True)
        if not verify_totp_code(user.totp_secret, data.totp_code):
            await write_audit_log(db, request, user.id, "login_2fa_failed")
            raise HTTPException(401, "Коди 2FA нодуруст аст")

    await write_audit_log(db, request, user.id, "login_success")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/2fa/setup")
async def setup_2fa(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    secret = generate_totp_secret()
    user.totp_secret = secret
    await db.commit()
    return {"secret": secret, "qr_uri": get_totp_uri(secret, user.email or user.phone)}


@router.post("/2fa/confirm")
async def confirm_2fa(code: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.totp_secret or not verify_totp_code(user.totp_secret, code):
        raise HTTPException(400, "Коди тасдиқ нодуруст аст")
    user.is_2fa_enabled = True
    await db.commit()
    return {"message": "2FA фаъол шуд"}


@router.post("/otp/request")
@limiter.limit("3/minute")
async def request_otp(request: Request, data: OtpRequestIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == data.identifier))
    user = result.scalar_one_or_none()

    code = generate_otp_code(settings.OTP_LENGTH)
    otp = OtpCode(
        identifier=data.identifier,
        code_hash=hash_otp(code),
        purpose="login" if user else "register",
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    await db.commit()

    sent = await send_otp_code(data.identifier, code, user.telegram_chat_id if user else None)
    if not sent:
        raise HTTPException(500, "Ирсоли код ноком шуд, дубора кӯшиш кунед")

    return {"message": "Код фиристода шуд", "is_new_user": user is None}


@router.post("/otp/verify", response_model=TokenResponse)
@limiter.limit("10/minute")
async def verify_otp_login(request: Request, data: OtpVerifyIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OtpCode)
        .where(OtpCode.identifier == data.identifier, OtpCode.is_used == False)  # noqa: E712
        .order_by(OtpCode.created_at.desc())
    )
    otp = result.scalars().first()

    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(401, "Коди эътибор надорад, дубора дархост кунед")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Кӯшишҳои зиёд — дубора дархост кунед")

    otp.attempts += 1
    if not verify_otp(data.code, otp.code_hash):
        await db.commit()
        raise HTTPException(401, "Коди нодуруст")

    otp.is_used = True

    result = await db.execute(select(User).where(User.phone == data.identifier))
    user = result.scalar_one_or_none()
    if not user:
        user = User(full_name="Корбари нав", phone=data.identifier, role=UserRole.BUYER)
        db.add(user)

    await db.commit()
    await db.refresh(user)
    await write_audit_log(db, request, user.id, "otp_login")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/telegram/link")
async def link_telegram(
    chat_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    user.telegram_chat_id = chat_id
    await db.commit()
    return {"message": "Telegram пайваст шуд"}
