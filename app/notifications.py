import httpx
from app.config import settings


async def send_telegram_message(chat_id: str, text: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={"chat_id": chat_id, "text": text})
        return r.status_code == 200


async def send_sms(phone: str, text: str) -> bool:
    if not settings.SMS_PROVIDER_API_KEY:
        print(f"[SMS-DEV] ба {phone}: {text}")
        return True
    return True


async def send_otp_code(identifier: str, code: str, telegram_chat_id: str | None = None) -> bool:
    text = f"Коди шумо барои вуруд ба Осон24: {code}\nЭътибор: 5 дақиқа. Ба ҳеҷ кас нагӯед."
    if telegram_chat_id:
        return await send_telegram_message(telegram_chat_id, text)
    return await send_sms(identifier, text)


async def notify_admin(text: str) -> bool:
    if not settings.TELEGRAM_ADMIN_CHAT_ID:
        return False
    return await send_telegram_message(settings.TELEGRAM_ADMIN_CHAT_ID, text)
