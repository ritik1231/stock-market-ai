from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stock_market_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    include=[
        "app.agents.orchestrator",
        "app.agents.research_agent",
        "app.agents.quant_agent",
        "app.agents.risk_agent",
        "app.agents.execution_agent",
        "app.agents.scheduled_tasks",
        "app.workers.dlq_consumer",
    ],
)

_dead_letter_args = {
    "x-dead-letter-exchange": "stock.dead_letter",
}

celery_app.conf.task_queues = (
    Queue("agent.research", Exchange("agent.research"), routing_key="agent.research", queue_arguments=_dead_letter_args),
    Queue("agent.quant", Exchange("agent.quant"), routing_key="agent.quant", queue_arguments=_dead_letter_args),
    Queue("agent.risk", Exchange("agent.risk"), routing_key="agent.risk", queue_arguments=_dead_letter_args),
    Queue("agent.execution", Exchange("agent.execution"), routing_key="agent.execution", queue_arguments=_dead_letter_args),
    Queue("orchestrator.tasks", Exchange("orchestrator.tasks"), routing_key="orchestrator.tasks", queue_arguments=_dead_letter_args),
)

celery_app.conf.task_default_queue = "orchestrator.tasks"
celery_app.conf.task_default_exchange = "orchestrator.tasks"
celery_app.conf.task_default_routing_key = "orchestrator.tasks"

celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.beat_schedule = {
    # NSE/BSE opens 9:15 AM IST — run analysis 5 min after open
    "daily-watchlist-analysis": {
        "task": "scheduled.daily_watchlist_analysis",
        "schedule": crontab(hour=9, minute=20, day_of_week="1-5"),
    },
    # NSE/BSE closes 3:30 PM IST — log P&L 5 min after close
    "end-of-day-pnl-log": {
        "task": "scheduled.end_of_day_pnl_log",
        "schedule": crontab(hour=15, minute=35, day_of_week="1-5"),
    },
    # Watchdog: check for stuck agent tasks every 5 minutes
    "check-orchestrator-health": {
        "task": "workers.check_orchestrator_health",
        "schedule": crontab(minute="*/5"),
    },
}
