from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/stockdb"

    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"

    # Message broker
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # AI providers
    GROQ_API_KEY: str = ""

    # Angel One SmartAPI
    ANGEL_API_KEY: str = ""
    ANGEL_CLIENT_ID: str = ""
    ANGEL_PASSWORD: str = ""
    ANGEL_TOTP_SECRET: str = ""

    # News
    NEWSAPI_KEY: str = ""

    # Upstox broker (optional — needed only when BROKER=upstox)
    UPSTOX_ACCESS_TOKEN: str = ""
    UPSTOX_SANDBOX: bool = True

    # App behaviour
    PAPER_MODE: bool = True
    BROKER: str = "paper"           # paper | upstox | angel
    PAPER_STARTING_CASH: float = 1_000_000.0   # ₹10 lakh default
    LOG_LEVEL: str = "INFO"
    DEFAULT_EXCHANGE: str = "NSE"
    CURRENCY: str = "INR"

    # Celery
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672/"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
