import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agents.orchestrator import run_orchestrator
from app.schemas.analysis import AnalysisResult, AnalyzeRequest, AnalyzeResponse
from app.tools.cache import get_cache, set_cache

router = APIRouter(tags=["analysis"])

_STATUS_TTL = 7200  # 2 hours — covers long-running orchestrator jobs


@router.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(request: Request, body: AnalyzeRequest):
    query_id = str(uuid.uuid4())

    await set_cache(f"analysis:{query_id}:status", "queued", ttl=_STATUS_TTL)

    payload = {
        "query_id": query_id,
        "ticker": body.ticker,
        "mode": body.mode,
        "lookback_days": body.lookback_days,
        "query_text": f"Analyze {body.ticker}",
    }
    run_orchestrator.apply_async(args=[payload], queue="orchestrator.tasks")

    base_url = str(request.base_url).rstrip("/")
    return AnalyzeResponse(
        query_id=query_id,
        ticker=body.ticker,
        status="queued",
        poll_url=f"{base_url}/analysis/{query_id}",
    )


@router.get("/analysis/{query_id}", response_model=AnalysisResult)
async def get_analysis(query_id: str):
    result = await get_cache(f"result:{query_id}")
    if result is not None:
        return AnalysisResult(status="completed", **result)

    status = await get_cache(f"analysis:{query_id}:status")
    if status is not None:
        return JSONResponse(
            status_code=202,
            content={"query_id": query_id, "status": status},
        )

    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "detail": f"No analysis found for query_id={query_id}"},
    )
