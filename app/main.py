import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router as api_router
from app.config import get_settings
from app.db import engine

settings = get_settings()
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(level=log_level)

    masked = {
        "DATABASE_URL": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "***",
        "REDIS_URL": settings.REDIS_URL,
        "RABBITMQ_URL": settings.RABBITMQ_URL.split("@")[-1] if "@" in settings.RABBITMQ_URL else "***",
        "PAPER_MODE": settings.PAPER_MODE,
        "LOG_LEVEL": settings.LOG_LEVEL,
    }
    logger.info("Starting Stock Market AI v%s — config: %s", APP_VERSION, masked)
    yield
    logger.info("Shutting down Stock Market AI")


app = FastAPI(
    title="Stock Market AI",
    version=APP_VERSION,
    description="Agentic stock market signal pipeline",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    result = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        result["db"] = "error"
        result["status"] = "degraded"

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        result["redis"] = "error"
        result["status"] = "degraded"

    return result
