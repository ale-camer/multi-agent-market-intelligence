"""Portfolio management, balances, positions, and trade execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from multi_agent_market_intelligence.api.dependencies import get_portfolio_tracker
from multi_agent_market_intelligence.api.schemas import (
    CashTransactionRequest,
    CashTransactionResponse,
    PortfolioResetRequest,
    PortfolioStateResponse,
    PositionsListResponse,
    TradeExecutionRequest,
    TradeExecutionResponse,
    TradeHistoryResponse,
)
from multi_agent_market_intelligence.risk.models import PortfolioMetrics
from multi_agent_market_intelligence.risk.portfolio import PortfolioTracker
from multi_agent_market_intelligence.state.models import PortfolioSnapshot, Position

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get(
    "",
    response_model=PortfolioStateResponse,
    summary="Get portfolio state",
    description="Retrieve full portfolio balances, exposures, risk metrics, and open positions.",
)
def get_portfolio_state(
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> PortfolioStateResponse:
    """Retrieve active portfolio balance sheet and open positions."""
    return PortfolioStateResponse(
        cash=tracker.cash,
        total_equity=tracker.total_equity,
        gross_exposure=tracker.gross_exposure,
        net_exposure=tracker.net_exposure,
        leverage=tracker.leverage,
        drawdown_pct=tracker.current_drawdown_pct,
        daily_pnl=tracker.daily_pnl,
        daily_pnl_pct=tracker.daily_pnl_pct,
        realized_pnl=tracker.realized_pnl,
        unrealized_pnl=tracker.unrealized_pnl,
        positions_count=len(tracker.positions),
        positions=tracker.positions,
    )


@router.get(
    "/positions",
    response_model=PositionsListResponse,
    summary="List active positions",
    description="Retrieve all currently open positions in the portfolio.",
)
def get_positions(
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> PositionsListResponse:
    """Retrieve list of all active open asset positions."""
    pos_list = list(tracker.positions.values())
    return PositionsListResponse(
        positions=pos_list,
        total_positions=len(pos_list),
    )


@router.get(
    "/positions/{symbol}",
    response_model=Position,
    summary="Get single position",
    description="Retrieve position details for a specific ticker symbol.",
)
def get_position(
    symbol: str,
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> Position:
    """Retrieve position details for a specific ticker symbol."""
    sym = symbol.strip().upper()
    pos = tracker.get_position(sym)
    if pos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Position for symbol '{sym}' not found in active portfolio.",
        )
    return pos


@router.get(
    "/metrics",
    response_model=PortfolioMetrics,
    summary="Get portfolio risk metrics",
    description="Retrieve comprehensive risk and performance metrics.",
)
def get_portfolio_metrics(
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> PortfolioMetrics:
    """Retrieve quantitative performance and risk metrics."""
    return tracker.get_metrics()


@router.get(
    "/history",
    response_model=TradeHistoryResponse,
    summary="Get trade history",
    description="Retrieve chronological audit log of all executed trade transactions.",
)
def get_trade_history(
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> TradeHistoryResponse:
    """Retrieve chronological audit trail of executed trade transactions."""
    hist = tracker.trade_history
    return TradeHistoryResponse(
        history=hist,
        total_trades=len(hist),
    )


@router.post(
    "/deposit",
    response_model=CashTransactionResponse,
    summary="Deposit cash into portfolio",
    description="Deposit liquid cash capital into portfolio balance.",
)
def deposit_cash(
    request: CashTransactionRequest,
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> CashTransactionResponse:
    """Deposit cash funds into portfolio balance."""
    try:
        new_cash = tracker.deposit_cash(request.amount)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CashTransactionResponse(
        transaction_type="DEPOSIT",
        amount=request.amount,
        new_cash=new_cash,
        total_equity=tracker.total_equity,
    )


@router.post(
    "/withdraw",
    response_model=CashTransactionResponse,
    summary="Withdraw cash from portfolio",
    description="Withdraw liquid cash from portfolio with overdraft protection.",
)
def withdraw_cash(
    request: CashTransactionRequest,
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> CashTransactionResponse:
    """Withdraw cash funds from portfolio balance with overdraft guard."""
    try:
        new_cash = tracker.withdraw_cash(request.amount)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CashTransactionResponse(
        transaction_type="WITHDRAWAL",
        amount=request.amount,
        new_cash=new_cash,
        total_equity=tracker.total_equity,
    )


@router.post(
    "/trade",
    response_model=TradeExecutionResponse,
    summary="Execute manual trade",
    description="Execute manual BUY or SELL transaction against active portfolio.",
)
def execute_trade(
    request: TradeExecutionRequest,
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> TradeExecutionResponse:
    """Execute manual trade transaction against active portfolio positions."""
    try:
        execution = tracker.apply_trade(
            symbol=request.symbol,
            action=request.action,
            quantity=request.quantity,
            price=request.price,
            commission=request.commission,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return TradeExecutionResponse(
        symbol=execution.symbol,
        action=execution.action,
        quantity=execution.quantity,
        price=execution.price,
        cost=execution.cost,
        realized_pnl=execution.realized_pnl,
        commission=execution.commission,
        timestamp=execution.timestamp,
    )


@router.post(
    "/reset",
    response_model=PortfolioStateResponse,
    summary="Reset portfolio state",
    description="Re-initialize portfolio state and cash balance to starting baseline.",
)
def reset_portfolio(
    request: PortfolioResetRequest = PortfolioResetRequest(),
    tracker: PortfolioTracker = Depends(get_portfolio_tracker),
) -> PortfolioStateResponse:
    """Reset portfolio state and balance sheet back to clean baseline."""
    tracker.load_snapshot(
        PortfolioSnapshot(
            cash=request.initial_cash,
            positions={},
            total_equity=request.initial_cash,
        )
    )
    tracker._trade_history = []
    tracker._realized_pnl = 0.0
    tracker._starting_equity = request.initial_cash
    tracker._peak_equity = request.initial_cash

    return PortfolioStateResponse(
        cash=tracker.cash,
        total_equity=tracker.total_equity,
        gross_exposure=tracker.gross_exposure,
        net_exposure=tracker.net_exposure,
        leverage=tracker.leverage,
        drawdown_pct=tracker.current_drawdown_pct,
        daily_pnl=tracker.daily_pnl,
        daily_pnl_pct=tracker.daily_pnl_pct,
        realized_pnl=tracker.realized_pnl,
        unrealized_pnl=tracker.unrealized_pnl,
        positions_count=len(tracker.positions),
        positions=tracker.positions,
    )
