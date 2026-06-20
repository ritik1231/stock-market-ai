"""Centralised structlog configuration and the @log_agent_task decorator."""

import logging
import sys
from functools import wraps
from time import perf_counter
from typing import Any, Callable

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog: JSON renderer in production, coloured console in development."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.dev.ConsoleRenderer()
        if log_level.upper() == "DEBUG"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Redirect stdlib logging through the same handler so third-party libs show up
    handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(format="%(message)s", handlers=[handler], level=level, force=True)


def log_agent_task(fn: Callable) -> Callable:
    """Decorator for Celery agent tasks (bind=True).

    Logs task_start and task_finish/task_error with latency_ms,
    binding agent name, ticker, and query_id to every log line.
    """

    @wraps(fn)
    def wrapper(self: Any, payload: dict) -> Any:
        log = structlog.get_logger().bind(
            agent=fn.__name__,
            ticker=payload.get("ticker", "?"),
            query_id=payload.get("query_id", "?"),
        )
        log.info("task_start")
        t0 = perf_counter()
        try:
            result = fn(self, payload)
            log.info("task_finish", latency_ms=round((perf_counter() - t0) * 1000))
            return result
        except Exception as exc:
            log.error("task_error", error=str(exc), latency_ms=round((perf_counter() - t0) * 1000))
            raise

    return wrapper
