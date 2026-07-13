"""
Танзимоти марказии барнома.
Ҳама қиматҳои ҳассос (паролҳо, калидҳо) бояд аз .env хонда шаванд, на дар код навишта шаванд.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Marketplace API"
    ENV: str = "development"

    # Пойгоҳи додаҳо
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"

    # Redis (барои кэш ва rate limiting)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # 2FA
    TWO_FA_ISSUER: str = "Marketplace"

    # CDN / файлҳо
    CDN_BASE_URL: str = "https://cdn.example.com"
    S3_BUCKET: str = "marketplace-media"

    # Rate limiting
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # OTP (коди якдафъаина)
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5

    # Боти шахсии Telegram (админ) — барои огоҳинома ва фиристодани OTP
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""  # chat_id-и шумо, танҳо шумо метавонед бо бот кор кунед
    API_BASE_URL: str = "http://localhost:8000"  # барои боти Telegram то ба API занг занад

    # SMS провайдер (барои фиристодани OTP ба телефон) — калидҳоро дар .env гузоред
    SMS_PROVIDER_API_KEY: str = ""

    # Забонҳои дастгиришаванда
    SUPPORTED_LANGUAGES: list[str] = ["tg", "ru", "en"]


settings = Settings()
