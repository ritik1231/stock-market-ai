from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.audit import router as audit_router
from app.api.routes.health_apis import router as health_apis_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.signals import router as signals_router
from app.api.routes.trades import router as trades_router

router = APIRouter()
router.include_router(analysis_router)
router.include_router(signals_router)
router.include_router(portfolio_router)
router.include_router(trades_router)
router.include_router(audit_router)
router.include_router(health_apis_router)
