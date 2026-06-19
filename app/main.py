import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.agents.execution_agent import LiveTradingNotPermittedError
from app.api.routes import router as api_router
from app.config import get_settings
from app.db import engine
from app.exceptions import RateLimitError
from app.tools.alpaca_client import AlpacaAPIError

settings = get_settings()
logger = structlog.get_logger()

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.logging_config import configure_logging
    configure_logging(settings.LOG_LEVEL)

    masked = {
        "DATABASE_URL": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "***",
        "REDIS_URL": settings.REDIS_URL,
        "RABBITMQ_URL": settings.RABBITMQ_URL.split("@")[-1] if "@" in settings.RABBITMQ_URL else "***",
        "PAPER_MODE": settings.PAPER_MODE,
        "LOG_LEVEL": settings.LOG_LEVEL,
    }
    logger.info("startup", version=APP_VERSION, config=masked)
    yield
    logger.info("shutdown", version=APP_VERSION)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request ID to each request and logs method/path/status/latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

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
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(AlpacaAPIError)
async def alpaca_error_handler(request: Request, exc: AlpacaAPIError):
    logger.warning("alpaca_error", detail=str(exc), path=request.url.path)
    return JSONResponse(status_code=502, content={"error": "alpaca_error", "detail": str(exc)})


@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    logger.warning("rate_limit_exceeded", detail=str(exc), path=request.url.path)
    return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded", "detail": str(exc)})


@app.exception_handler(LiveTradingNotPermittedError)
async def live_trading_handler(request: Request, exc: LiveTradingNotPermittedError):
    return JSONResponse(status_code=403, content={"error": "live_trading_not_permitted"})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    result = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("db_health_failed", error=str(exc))
        result["db"] = "error"
        result["status"] = "degraded"

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        logger.warning("redis_health_failed", error=str(exc))
        result["redis"] = "error"
        result["status"] = "degraded"

    return result
