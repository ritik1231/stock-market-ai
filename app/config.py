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

    # Alpaca
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_BASE_URL: str = "https://paper-api.alpaca.markets"

    # News
    NEWSAPI_KEY: str = ""

    # App behaviour
    PAPER_MODE: bool = True
    LOG_LEVEL: str = "INFO"

    # Celery
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672/"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
