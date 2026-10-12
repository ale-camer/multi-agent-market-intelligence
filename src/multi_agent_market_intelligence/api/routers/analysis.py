"""Market intelligence analysis and orchestrator execution endpoints."""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from multi_agent_market_intelligence.api.dependencies import get_orchestrator
from multi_agent_market_intelligence.api.schemas import AnalysisRequest, AnalysisResponse
from multi_agent_market_intelligence.orchestrator.graph import MarketIntelligenceOrchestrator
from multi_agent_market_intelligence.state.models import PortfolioSnapshot
from multi_agent_market_intelligence.state.schema import create_market_state

router = APIRouter(prefix="/analyze", tags=["Analysis"])


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute multi-agent intelligence analysis",
    description=(
        "Triggers the full autonomous 3-agent intelligence DAG "
        "(Research -> Trading Analyst -> Risk & Portfolio Manager) "
        "over the specified list of ticker symbols."
    ),
)
def run_analysis(
    request: AnalysisRequest,
    orchestrator: MarketIntelligenceOrchestrator = Depends(get_orchestrator),
) -> AnalysisResponse:
    """Execute end-to-end multi-agent analysis workflow."""
    start_time = time.perf_counter()
    corr_id = request.correlation_id or f"corr-{uuid.uuid4().hex[:12]}"

    initial_state = create_market_state(
        context={
            "target_symbols": request.symbols,
            "correlation_id": corr_id,
        },
        portfolio=PortfolioSnapshot(
            cash=request.initial_cash,
            total_equity=request.initial_cash,
        ),
    )

    try:
        final_state = orchestrator.run(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failure: {exc}",
        ) from exc

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    portfolio = final_state.get("portfolio")
    if not isinstance(portfolio, PortfolioSnapshot):
        portfolio = PortfolioSnapshot(
            cash=request.initial_cash,
            total_equity=request.initial_cash,
        )

    return AnalysisResponse(
        status="SUCCESS",
        correlation_id=corr_id,
        symbols=request.symbols,
        signals=list(final_state.get("signals", [])),
        decisions=list(final_state.get("decisions", [])),
        portfolio=portfolio,
        records=list(final_state.get("records", [])),
        execution_time_ms=elapsed_ms,
    )
