from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.audit import router as audit_router
from app.api.routes.fii_dii_route import router as fii_dii_router
from app.api.routes.health_apis import router as health_apis_router
from app.api.routes.market_overview import router as market_overview_router
from app.api.routes.news import router as news_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.runs import router as runs_router
from app.api.routes.search import router as search_router
from app.api.routes.signals import router as signals_router
from app.api.routes.tax import router as tax_router
from app.api.routes.trades import router as trades_router
from app.api.routes.watchlist import router as watchlist_router

router = APIRouter()
router.include_router(analysis_router)
router.include_router(signals_router)
router.include_router(portfolio_router)
router.include_router(trades_router)
router.include_router(audit_router)
router.include_router(health_apis_router)
router.include_router(watchlist_router)
router.include_router(runs_router)
router.include_router(search_router)
router.include_router(tax_router)
router.include_router(news_router)
router.include_router(market_overview_router)
router.include_router(fii_dii_router)
