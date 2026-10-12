"""Portfolio state tracking, cash management, and mark-to-market accounting engine."""

from typing import Any

from multi_agent_market_intelligence.risk.models import PortfolioMetrics, TradeExecution
from multi_agent_market_intelligence.state.models import (
    PortfolioSnapshot,
    Position,
    SignalAction,
)


class PortfolioTracker:
    """Autonomous portfolio accounting engine managing cash, positions, and risk metrics."""

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        starting_equity: float | None = None,
        positions: dict[str, Position] | None = None,
        sector_mappings: dict[str, str] | None = None,
    ) -> None:
        """Initialize portfolio state tracker.

        Args:
            initial_cash: Starting liquid cash capital.
            starting_equity: Baseline starting equity for daily PnL calculation.
            positions: Optional pre-existing active asset positions.
            sector_mappings: Mapping from asset symbols to market sectors.

        Raises:
            ValueError: If initial cash or starting equity is negative.
        """
        if initial_cash < 0:
            raise ValueError(f"Initial cash cannot be negative, got {initial_cash}")
        if starting_equity is not None and starting_equity < 0:
            raise ValueError(f"Starting equity cannot be negative, got {starting_equity}")

        self._cash = float(initial_cash)
        self._positions: dict[str, Position] = {}
        if positions:
            for symbol, pos in positions.items():
                if isinstance(pos, Position):
                    p = pos.model_copy()
                elif isinstance(pos, dict):
                    p = Position(**pos)
                else:
                    raise TypeError(f"Invalid position object type for {symbol}: {type(pos)}")
                p.unrealized_pnl = (p.current_price - p.entry_price) * p.quantity
                self._positions[symbol] = p

        self._sector_mappings: dict[str, str] = dict(sector_mappings or {})
        self._trade_history: list[TradeExecution] = []
        self._realized_pnl: float = 0.0

        current_equity = self.total_equity
        if starting_equity is None:
            self._starting_equity = current_equity
        else:
            self._starting_equity = float(starting_equity)

        self._peak_equity: float = max(self._starting_equity, current_equity)

    @property
    def cash(self) -> float:
        """Available liquid cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """Dictionary of currently open asset positions."""
        return dict(self._positions)

    @property
    def trade_history(self) -> list[TradeExecution]:
        """Chronological audit history of executed trades."""
        return list(self._trade_history)

    @property
    def sector_mappings(self) -> dict[str, str]:
        """Mapping of asset symbols to market sector names."""
        return dict(self._sector_mappings)

    @property
    def starting_equity(self) -> float:
        """Baseline equity at beginning of active period."""
        return self._starting_equity

    @property
    def peak_equity(self) -> float:
        """High-water mark portfolio equity recorded to date."""
        return self._peak_equity

    @property
    def realized_pnl(self) -> float:
        """Cumulative net realized profit and loss from closed or reduced positions."""
        return self._realized_pnl

    @property
    def unrealized_pnl(self) -> float:
        """Aggregate unrealized mark-to-market profit and loss across open positions."""
        return sum(
            (pos.current_price - pos.entry_price) * pos.quantity for pos in self._positions.values()
        )

    @property
    def total_equity(self) -> float:
        """Total portfolio net liquidation value (cash + mark-to-market position value)."""
        market_val = sum(pos.quantity * pos.current_price for pos in self._positions.values())
        return self._cash + market_val

    @property
    def gross_exposure(self) -> float:
        """Total absolute market value of all active positions."""
        return sum(abs(pos.quantity * pos.current_price) for pos in self._positions.values())

    @property
    def net_exposure(self) -> float:
        """Signed net market value of all active positions."""
        return sum(pos.quantity * pos.current_price for pos in self._positions.values())

    @property
    def leverage(self) -> float:
        """Ratio of gross exposure to total portfolio equity."""
        eq = self.total_equity
        if eq <= 0:
            return 0.0
        return self.gross_exposure / eq

    @property
    def current_drawdown_pct(self) -> float:
        """Peak-to-current drawdown percentage as a fraction (0.0 to 1.0)."""
        if self._peak_equity <= 0:
            return 0.0
        drawdown = (self._peak_equity - self.total_equity) / self._peak_equity
        return max(0.0, drawdown)

    @property
    def daily_pnl(self) -> float:
        """Net absolute profit and loss change relative to session starting equity."""
        return self.total_equity - self._starting_equity

    @property
    def daily_pnl_pct(self) -> float:
        """Percentage return change relative to session starting equity."""
        if self._starting_equity <= 0:
            return 0.0
        return self.daily_pnl / self._starting_equity

    def deposit_cash(self, amount: float) -> float:
        """Deposit liquid cash into portfolio.

        Args:
            amount: Cash amount to deposit.

        Returns:
            Updated cash balance.

        Raises:
            ValueError: If amount is less than or equal to zero.
        """
        if amount <= 0:
            raise ValueError(f"Deposit amount must be positive, got {amount}")
        self._cash += amount
        if self.total_equity > self._peak_equity:
            self._peak_equity = self.total_equity
        return self._cash

    def withdraw_cash(self, amount: float) -> float:
        """Withdraw cash from portfolio balance with overdraft prevention.

        Args:
            amount: Cash amount to withdraw.

        Returns:
            Updated cash balance.

        Raises:
            ValueError: If amount is non-positive or exceeds available cash.
        """
        if amount <= 0:
            raise ValueError(f"Withdrawal amount must be positive, got {amount}")
        if amount > self._cash:
            raise ValueError(
                f"Insufficient cash for withdrawal: requested {amount:.2f}, "
                f"available {self._cash:.2f}"
            )
        self._cash -= amount
        return self._cash

    def update_market_price(self, symbol: str, price: float) -> None:
        """Update current mark-to-market valuation for an asset.

        Args:
            symbol: Ticker symbol.
            price: New market price.

        Raises:
            ValueError: If price is less than or equal to zero.
        """
        if price <= 0:
            raise ValueError(f"Market price must be positive, got {price}")
        if symbol in self._positions:
            pos = self._positions[symbol]
            pos.current_price = price
            pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity

        if self.total_equity > self._peak_equity:
            self._peak_equity = self.total_equity

    def update_market_prices(self, prices: dict[str, float]) -> None:
        """Batch update market prices for multiple assets.

        Args:
            prices: Dictionary of symbol to market price.
        """
        for sym, price in prices.items():
            self.update_market_price(sym, price)

    def apply_trade(
        self,
        symbol: str,
        action: SignalAction | str,
        quantity: float,
        price: float,
        commission: float = 0.0,
    ) -> TradeExecution:
        """Execute a trade transaction, updating cash, positions, and realized PnL.

        Args:
            symbol: Asset ticker symbol.
            action: Trading signal action (BUY or SELL).
            quantity: Number of units to buy or sell.
            price: Execution fill price.
            commission: Transaction fee or commission.

        Returns:
            TradeExecution record detailing the completed transaction.

        Raises:
            ValueError: If quantity or price is non-positive, commission is negative,
                action is unsupported, cash is insufficient, or selling more units
                than currently held.
        """
        if isinstance(action, str):
            act_str = action.strip().upper()
            try:
                sig_action = SignalAction(act_str)
            except ValueError:
                raise ValueError(f"Unsupported trade action: '{action}'")
        else:
            sig_action = action

        if quantity <= 0:
            raise ValueError(f"Trade quantity must be positive, got {quantity}")
        if price <= 0:
            raise ValueError(f"Trade price must be positive, got {price}")
        if commission < 0:
            raise ValueError(f"Commission cannot be negative, got {commission}")

        trade_cost = quantity * price

        if sig_action == SignalAction.BUY:
            total_cash_required = trade_cost + commission
            if total_cash_required > self._cash:
                raise ValueError(
                    f"Insufficient cash ({self._cash:.2f}) for trade cost "
                    f"({total_cash_required:.2f})"
                )

            self._cash -= total_cash_required
            trade_realized_pnl = 0.0

            if symbol in self._positions:
                pos = self._positions[symbol]
                total_qty = pos.quantity + quantity
                # Weighted average entry price
                new_entry_price = ((pos.quantity * pos.entry_price) + trade_cost) / total_qty
                pos.quantity = total_qty
                pos.entry_price = new_entry_price
                pos.current_price = price
                pos.unrealized_pnl = (price - new_entry_price) * total_qty
            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    current_price=price,
                    unrealized_pnl=0.0,
                )

        elif sig_action == SignalAction.SELL:
            if symbol not in self._positions:
                raise ValueError(f"No existing position for symbol '{symbol}' to sell")

            pos = self._positions[symbol]
            if quantity > pos.quantity + 1e-9:
                raise ValueError(
                    f"Cannot sell more quantity ({quantity}) than held ({pos.quantity})"
                )

            trade_realized_pnl = ((price - pos.entry_price) * quantity) - commission
            self._realized_pnl += trade_realized_pnl
            net_proceeds = trade_cost - commission
            self._cash += net_proceeds

            remaining_qty = pos.quantity - quantity
            if remaining_qty <= 1e-9:
                del self._positions[symbol]
            else:
                pos.quantity = remaining_qty
                pos.current_price = price
                pos.unrealized_pnl = (price - pos.entry_price) * remaining_qty

        else:
            raise ValueError(f"Cannot execute trade with action '{sig_action.value}'")

        execution = TradeExecution(
            symbol=symbol,
            action=sig_action,
            quantity=quantity,
            price=price,
            cost=trade_cost,
            realized_pnl=trade_realized_pnl,
            commission=commission,
        )
        self._trade_history.append(execution)

        if self.total_equity > self._peak_equity:
            self._peak_equity = self.total_equity

        return execution

    def get_position(self, symbol: str) -> Position | None:
        """Retrieve active position for given symbol.

        Args:
            symbol: Ticker symbol.

        Returns:
            Position model if open, None otherwise.
        """
        return self._positions.get(symbol)

    def set_sector_mappings(self, mappings: dict[str, str]) -> None:
        """Register or update symbol-to-sector mappings.

        Args:
            mappings: Dictionary mapping symbol to sector name.
        """
        self._sector_mappings.update(mappings)

    def get_sector_exposure(self, sector: str) -> float:
        """Calculate aggregate capital allocation exposure in a specific market sector.

        Args:
            sector: Sector category name.

        Returns:
            Total valuation of active positions belonging to sector.
        """
        sector_target = sector.strip().lower()
        return sum(
            pos.quantity * pos.current_price
            for sym, pos in self._positions.items()
            if self._sector_mappings.get(sym, "").strip().lower() == sector_target
        )

    def get_metrics(self) -> PortfolioMetrics:
        """Generate comprehensive portfolio risk and performance metrics.

        Returns:
            PortfolioMetrics domain model.
        """
        eq = self.total_equity
        weights: dict[str, float] = {}
        if eq > 0:
            for sym, pos in self._positions.items():
                weights[sym] = (pos.quantity * pos.current_price) / eq

        return PortfolioMetrics(
            total_equity=eq,
            cash=self.cash,
            gross_exposure=self.gross_exposure,
            net_exposure=self.net_exposure,
            leverage=self.leverage,
            drawdown_pct=self.current_drawdown_pct,
            peak_equity=self.peak_equity,
            daily_pnl=self.daily_pnl,
            daily_pnl_pct=self.daily_pnl_pct,
            positions_count=len(self._positions),
            position_weights=weights,
        )

    def create_snapshot(self) -> PortfolioSnapshot:
        """Export current portfolio state into a typed PortfolioSnapshot.

        Returns:
            PortfolioSnapshot compatible with MarketIntelligenceState["portfolio"].
        """
        margin_used = max(0.0, self.gross_exposure - self._cash)
        return PortfolioSnapshot(
            cash=self._cash,
            positions={k: v.model_copy() for k, v in self._positions.items()},
            total_equity=self.total_equity,
            margin_used=margin_used,
        )

    def load_snapshot(self, snapshot: PortfolioSnapshot | dict[str, Any]) -> None:
        """Hydrate tracker state from an existing PortfolioSnapshot or dictionary.

        Args:
            snapshot: PortfolioSnapshot or dictionary representation.

        Raises:
            TypeError: If snapshot is not PortfolioSnapshot or dict.
        """
        if isinstance(snapshot, PortfolioSnapshot):
            self._cash = float(snapshot.cash)
            self._positions = {k: v.model_copy() for k, v in snapshot.positions.items()}
        elif isinstance(snapshot, dict):
            self._cash = float(snapshot.get("cash", 0.0))
            pos_dict = snapshot.get("positions", {})
            self._positions = {}
            for k, v in pos_dict.items():
                if isinstance(v, Position):
                    self._positions[k] = v.model_copy()
                elif isinstance(v, dict):
                    self._positions[k] = Position(**v)
                else:
                    raise TypeError(f"Invalid position data in snapshot: {type(v)}")
        else:
            raise TypeError(f"Unsupported snapshot type: {type(snapshot)}")

        for pos in self._positions.values():
            pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity

        current_eq = self.total_equity
        if current_eq > self._peak_equity:
            self._peak_equity = current_eq

    def reset_daily_baseline(self) -> None:
        """Reset starting equity baseline for the current session to current total equity."""
        self._starting_equity = self.total_equity
