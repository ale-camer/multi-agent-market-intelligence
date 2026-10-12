"""Signal risk validation engine, position sizing calculator, and decision generator."""

from typing import Any

from multi_agent_market_intelligence.risk.config import RiskLimitsConfig
from multi_agent_market_intelligence.risk.models import RiskViolationType
from multi_agent_market_intelligence.risk.portfolio import PortfolioTracker
from multi_agent_market_intelligence.state.models import (
    DecisionStatus,
    PortfolioSnapshot,
    Position,
    RiskDecision,
    SignalAction,
    TradingSignal,
)


class _PortfolioView:
    """Internal normalized view over various portfolio state representations."""

    def __init__(
        self,
        portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any],
        sectors: dict[str, str] | None = None,
    ) -> None:
        self.sector_mappings: dict[str, str] = dict(sectors or {})

        if isinstance(portfolio, PortfolioTracker):
            self.cash: float = portfolio.cash
            self.total_equity: float = portfolio.total_equity
            self.positions: dict[str, Position] = {
                k: v.model_copy() for k, v in portfolio.positions.items()
            }
            self.gross_exposure: float = portfolio.gross_exposure
            self.current_drawdown_pct: float = portfolio.current_drawdown_pct
            self.daily_pnl_pct: float = portfolio.daily_pnl_pct
            tracker_sectors = portfolio.sector_mappings
            for k, v in tracker_sectors.items():
                if k not in self.sector_mappings:
                    self.sector_mappings[k] = v

        elif isinstance(portfolio, PortfolioSnapshot):
            self.cash = float(portfolio.cash)
            self.total_equity = float(portfolio.total_equity)
            self.positions = {k: v.model_copy() for k, v in portfolio.positions.items()}
            self.gross_exposure = sum(
                abs(p.quantity * p.current_price) for p in self.positions.values()
            )
            self.current_drawdown_pct = float(getattr(portfolio, "current_drawdown_pct", 0.0))
            self.daily_pnl_pct = float(getattr(portfolio, "daily_pnl_pct", 0.0))

        elif isinstance(portfolio, dict):
            self.cash = float(portfolio.get("cash", 0.0))
            raw_positions = portfolio.get("positions", {})
            self.positions = {}
            for sym, pos in raw_positions.items():
                if isinstance(pos, Position):
                    self.positions[sym] = pos.model_copy()
                elif isinstance(pos, dict):
                    self.positions[sym] = Position(**pos)
                else:
                    raise TypeError(f"Invalid position entry in portfolio dict: {type(pos)}")

            eq = portfolio.get("total_equity")
            if eq is not None and float(eq) > 0.0:
                self.total_equity = float(eq)
            else:
                self.total_equity = self.cash + sum(
                    p.quantity * p.current_price for p in self.positions.values()
                )

            self.gross_exposure = sum(
                abs(p.quantity * p.current_price) for p in self.positions.values()
            )
            self.current_drawdown_pct = float(portfolio.get("current_drawdown_pct", 0.0))
            self.daily_pnl_pct = float(portfolio.get("daily_pnl_pct", 0.0))
            dict_sectors = portfolio.get("sector_mappings", {})
            if isinstance(dict_sectors, dict):
                for k, v in dict_sectors.items():
                    if k not in self.sector_mappings:
                        self.sector_mappings[k] = str(v)
        else:
            raise TypeError(f"Unsupported portfolio container type: {type(portfolio)}")

    def get_sector_exposure(self, sector: str) -> float:
        """Calculate active valuation in a given sector."""
        target = sector.strip().lower()
        return sum(
            pos.quantity * pos.current_price
            for sym, pos in self.positions.items()
            if self.sector_mappings.get(sym, "").strip().lower() == target
        )

    def allocate_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        sector: str | None = None,
    ) -> None:
        """Simulate trade execution to update capacity for sequential batch evaluations."""
        cost = quantity * price
        self.cash -= cost
        self.gross_exposure += cost
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.quantity += quantity
            pos.current_price = price
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                current_price=price,
                unrealized_pnl=0.0,
            )
        if sector and symbol not in self.sector_mappings:
            self.sector_mappings[symbol] = sector


class SignalRiskValidator:
    """Quantitative risk validation engine evaluating trading signals against portfolio limits."""

    def __init__(
        self,
        limits: RiskLimitsConfig | None = None,
        risk_per_trade_pct: float = 0.02,
        allow_position_scaling: bool = True,
    ) -> None:
        """Initialize signal risk validator.

        Args:
            limits: RiskLimitsConfig specifying global portfolio boundaries.
            risk_per_trade_pct: Default fraction of equity risked per trade based on stop loss.
            allow_position_scaling: If True, scales down oversized trades into MODIFIED status;
                if False, rejects trades that exceed capacity limits.

        Raises:
            ValueError: If risk_per_trade_pct is non-positive or exceeds 1.0.
        """
        if risk_per_trade_pct <= 0.0 or risk_per_trade_pct > 1.0:
            raise ValueError(f"risk_per_trade_pct must be in (0.0, 1.0], got {risk_per_trade_pct}")
        self.limits: RiskLimitsConfig = limits or RiskLimitsConfig()
        self.risk_per_trade_pct: float = risk_per_trade_pct
        self.allow_position_scaling: bool = allow_position_scaling

    def validate_signal(
        self,
        signal: TradingSignal,
        portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any],
        current_price: float | None = None,
        proposed_size: float | None = None,
        sector: str | None = None,
    ) -> RiskDecision:
        """Validate a single trading signal against portfolio risk limits.

        Args:
            signal: Generated trading signal to validate.
            portfolio: Active portfolio state (tracker, snapshot, or dict).
            current_price: Market entry price. If None, derived from signal indicators.
            proposed_size: Desired unit trade size. If None, dynamically calculated.
            sector: Market sector classification for the asset.

        Returns:
            RiskDecision indicating APPROVED, MODIFIED, or REJECTED status with telemetry.
        """
        view = _PortfolioView(portfolio, sectors={signal.symbol: sector} if sector else None)
        return self._evaluate_signal_on_view(signal, view, current_price, proposed_size, sector)

    def validate_signals_batch(
        self,
        signals: list[TradingSignal],
        portfolio: PortfolioTracker | PortfolioSnapshot | dict[str, Any],
        prices: dict[str, float] | None = None,
        proposed_sizes: dict[str, float] | None = None,
        sectors: dict[str, str] | None = None,
        track_cumulative_capacity: bool = True,
    ) -> list[RiskDecision]:
        """Validate multiple trading signals with optional cumulative portfolio tracking.

        Args:
            signals: Sequence of TradingSignal instances.
            portfolio: Active portfolio state.
            prices: Optional mapping of symbol to current price.
            proposed_sizes: Optional mapping of symbol to requested trade size.
            sectors: Optional mapping of symbol to sector name.
            track_cumulative_capacity: If True, each approved trade reduces available
                cash and leverage capacity for subsequent signals in the batch.

        Returns:
            List of RiskDecision objects in corresponding order.
        """
        view = _PortfolioView(portfolio, sectors=sectors)
        prices_map = prices or {}
        sizes_map = proposed_sizes or {}
        sectors_map = sectors or {}

        decisions: list[RiskDecision] = []
        for sig in signals:
            sym = sig.symbol
            price = prices_map.get(sym)
            p_size = sizes_map.get(sym)
            sec = sectors_map.get(sym)

            decision = self._evaluate_signal_on_view(sig, view, price, p_size, sec)
            decisions.append(decision)

            if track_cumulative_capacity and decision.status in (
                DecisionStatus.APPROVED,
                DecisionStatus.MODIFIED,
            ):
                if sig.action == SignalAction.BUY and decision.approved_size > 0.0:
                    fill_price = price
                    if fill_price is None or fill_price <= 0.0:
                        fill_price = float(sig.indicators.get("close", 100.0))
                    view.allocate_trade(sym, decision.approved_size, fill_price, sec)

        return decisions

    def _evaluate_signal_on_view(
        self,
        signal: TradingSignal,
        view: _PortfolioView,
        current_price: float | None = None,
        proposed_size: float | None = None,
        sector: str | None = None,
    ) -> RiskDecision:
        """Internal worker executing all risk checks against normalized portfolio view."""
        # Pre-check 1: Circuit breaker active
        if self.limits.circuit_breaker_active:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason="Trading halted: Circuit breaker is active.",
                metrics={"violations": [RiskViolationType.CIRCUIT_BREAKER_ACTIVE.value]},
            )

        # Pre-check 2: Max portfolio drawdown (restricts new risk accumulation)
        if (
            signal.action == SignalAction.BUY
            and view.current_drawdown_pct > self.limits.max_portfolio_drawdown_pct
        ):
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=(
                    f"Portfolio drawdown ({view.current_drawdown_pct:.2%}) exceeds limit "
                    f"({self.limits.max_portfolio_drawdown_pct:.2%})."
                ),
                metrics={
                    "drawdown_pct": view.current_drawdown_pct,
                    "violations": [RiskViolationType.MAX_PORTFOLIO_DRAWDOWN_EXCEEDED.value],
                },
            )

        # Pre-check 3: Max daily loss limit (restricts new risk accumulation)
        if (
            signal.action == SignalAction.BUY
            and view.daily_pnl_pct < -self.limits.max_daily_loss_pct
        ):
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=(
                    f"Daily loss ({view.daily_pnl_pct:.2%}) exceeds limit "
                    f"({self.limits.max_daily_loss_pct:.2%})."
                ),
                metrics={
                    "daily_pnl_pct": view.daily_pnl_pct,
                    "violations": [RiskViolationType.MAX_DAILY_LOSS_EXCEEDED.value],
                },
            )

        # Action: HOLD
        if signal.action == SignalAction.HOLD:
            return RiskDecision(
                status=DecisionStatus.APPROVED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason="Signal action is HOLD; no portfolio execution required.",
                metrics={"action": "HOLD", "status": "APPROVED"},
            )

        # Action: SELL
        if signal.action == SignalAction.SELL:
            return self._evaluate_sell(signal, view, proposed_size)

        # Resolve market price
        price = self._resolve_price(signal, view, current_price)

        # Action: BUY
        if signal.action == SignalAction.BUY:
            return self._evaluate_buy(signal, view, price, proposed_size, sector)

        # Unsupported action fallback
        return RiskDecision(
            status=DecisionStatus.REJECTED,
            original_signal=signal,
            approved_size=0.0,
            max_loss_limit=0.0,
            reason=f"Unsupported signal action '{signal.action}'.",
            metrics={"violations": ["UNSUPPORTED_ACTION"]},
        )

    def _resolve_price(
        self,
        signal: TradingSignal,
        view: _PortfolioView,
        current_price: float | None,
    ) -> float:
        """Resolve current market price for trade evaluation."""
        if current_price is not None and current_price > 0.0:
            return current_price
        if signal.symbol in view.positions:
            pos_price = view.positions[signal.symbol].current_price
            if pos_price > 0.0:
                return pos_price
        if isinstance(signal.indicators, dict) and "close" in signal.indicators:
            close_val = float(signal.indicators["close"])
            if close_val > 0.0:
                return close_val
        raise ValueError(
            f"Current market price for symbol '{signal.symbol}' must be provided or "
            f"available in signal indicators."
        )

    def _evaluate_sell(
        self,
        signal: TradingSignal,
        view: _PortfolioView,
        proposed_size: float | None,
    ) -> RiskDecision:
        """Evaluate SELL order against existing position holdings."""
        if signal.symbol not in view.positions:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=f"Cannot SELL symbol '{signal.symbol}': no open position held in portfolio.",
                metrics={"violations": ["NO_POSITION_HELD"]},
            )

        pos = view.positions[signal.symbol]
        held_qty = pos.quantity
        if held_qty <= 0.0:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=f"Position quantity for '{signal.symbol}' is zero.",
                metrics={"violations": ["ZERO_POSITION_QUANTITY"]},
            )

        if proposed_size is None or proposed_size <= 0.0:
            sell_size = held_qty
            status = DecisionStatus.APPROVED
            reason = f"SELL approved: full liquidation of {held_qty:.2f} units of {signal.symbol}."
        elif proposed_size > held_qty:
            if self.allow_position_scaling:
                sell_size = held_qty
                status = DecisionStatus.MODIFIED
                reason = (
                    f"SELL modified: requested {proposed_size:.2f} units scaled down to "
                    f"held quantity {held_qty:.2f}."
                )
            else:
                return RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=signal,
                    approved_size=0.0,
                    max_loss_limit=0.0,
                    reason=(
                        f"Cannot sell {proposed_size:.2f} units; only {held_qty:.2f} units held."
                    ),
                    metrics={"violations": ["EXCESSIVE_SELL_QUANTITY"]},
                )
        else:
            sell_size = proposed_size
            status = DecisionStatus.APPROVED
            reason = f"SELL approved for {sell_size:.2f} units of {signal.symbol}."

        return RiskDecision(
            status=status,
            original_signal=signal,
            approved_size=sell_size,
            max_loss_limit=0.0,
            reason=reason,
            metrics={"action": "SELL", "held_quantity": held_qty, "approved_size": sell_size},
        )

    def _evaluate_buy(
        self,
        signal: TradingSignal,
        view: _PortfolioView,
        price: float,
        proposed_size: float | None,
        sector: str | None,
    ) -> RiskDecision:
        """Evaluate BUY order against risk policy, geometry, and capacity constraints."""
        # 1. Concurrent open positions cap
        is_new_sym = signal.symbol not in view.positions or (
            view.positions[signal.symbol].quantity <= 1e-9
        )
        if is_new_sym and len(view.positions) >= self.limits.max_open_positions:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=(
                    f"Concurrent open positions count ({len(view.positions)}) reached "
                    f"limit of {self.limits.max_open_positions}."
                ),
                metrics={
                    "positions_count": len(view.positions),
                    "violations": [RiskViolationType.MAX_CONCURRENT_POSITIONS_EXCEEDED.value],
                },
            )

        # 2. Stop-loss requirement
        if self.limits.stop_loss_required and (signal.stop_loss is None or signal.stop_loss <= 0.0):
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason="Stop loss is required but not provided or non-positive.",
                metrics={"violations": [RiskViolationType.MISSING_STOP_LOSS.value]},
            )

        # 3. Stop-loss geometry
        if signal.stop_loss is not None and signal.stop_loss >= price:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=(
                    f"BUY stop loss ({signal.stop_loss:.2f}) must be strictly below "
                    f"entry price ({price:.2f})."
                ),
                metrics={"violations": [RiskViolationType.MISSING_STOP_LOSS.value]},
            )

        # 4. Risk-to-reward ratio check
        rr_ratio: float | None = None
        if signal.target_price is not None and signal.stop_loss is not None:
            risk = price - signal.stop_loss
            reward = signal.target_price - price
            if reward <= 0.0:
                return RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=signal,
                    approved_size=0.0,
                    max_loss_limit=0.0,
                    reason=(
                        f"BUY target price ({signal.target_price:.2f}) must be strictly above "
                        f"entry price ({price:.2f})."
                    ),
                    metrics={"violations": [RiskViolationType.INSUFFICIENT_RISK_REWARD.value]},
                )
            rr_ratio = reward / risk
            if rr_ratio < self.limits.min_risk_reward_ratio:
                return RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=signal,
                    approved_size=0.0,
                    max_loss_limit=0.0,
                    reason=(
                        f"Risk-reward ratio ({rr_ratio:.2f}) is below minimum required "
                        f"{self.limits.min_risk_reward_ratio:.2f}."
                    ),
                    metrics={
                        "risk_reward_ratio": rr_ratio,
                        "violations": [RiskViolationType.INSUFFICIENT_RISK_REWARD.value],
                    },
                )

        # 5. Position Sizing
        total_equity = view.total_equity
        if total_equity <= 0.0:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason="Portfolio total equity is non-positive.",
                metrics={"violations": ["NON_POSITIVE_EQUITY"]},
            )

        # Determine target desired size
        if proposed_size is not None and proposed_size > 0.0:
            desired_size = proposed_size
        elif signal.stop_loss is not None and (price - signal.stop_loss) > 0.0:
            # Sizing based on risk per trade fraction and stop distance
            risk_budget = total_equity * self.risk_per_trade_pct
            risk_per_unit = price - signal.stop_loss
            desired_size = risk_budget / risk_per_unit
        else:
            desired_size = (total_equity * self.limits.max_position_size_pct) / price

        # 6. Capacity Ceilings
        # Ceiling A: Single-position concentration
        current_pos_val = 0.0
        if signal.symbol in view.positions:
            current_pos_val = view.positions[signal.symbol].quantity * price
        cap_single = (self.limits.max_position_size_pct * total_equity) - current_pos_val

        # Ceiling B: Sector concentration
        sec_name = sector or view.sector_mappings.get(signal.symbol)
        if sec_name:
            curr_sec_val = view.get_sector_exposure(sec_name)
            cap_sector = (self.limits.max_sector_exposure_pct * total_equity) - curr_sec_val
        else:
            curr_sec_val = 0.0
            cap_sector = float("inf")

        # Ceiling C: Cash buffer constraint
        req_cash_buffer = self.limits.min_cash_buffer_pct * total_equity
        cap_cash = view.cash - req_cash_buffer

        # Ceiling D: Gross leverage cap
        max_allowed_gross = self.limits.max_leverage * total_equity
        cap_leverage = max_allowed_gross - view.gross_exposure

        # Evaluate binding constraint
        constraint_caps: dict[RiskViolationType, float] = {
            RiskViolationType.EXCESSIVE_POSITION_SIZE: cap_single,
            RiskViolationType.MAX_SECTOR_EXPOSURE_EXCEEDED: cap_sector,
            RiskViolationType.INSUFFICIENT_CASH_BUFFER: cap_cash,
            RiskViolationType.EXCESSIVE_LEVERAGE: cap_leverage,
        }

        binding_violation = min(constraint_caps, key=lambda k: constraint_caps[k])
        binding_cap = constraint_caps[binding_violation]

        if binding_cap <= 0.0:
            return RiskDecision(
                status=DecisionStatus.REJECTED,
                original_signal=signal,
                approved_size=0.0,
                max_loss_limit=0.0,
                reason=(
                    f"Capital constraint reached ({binding_violation.value}): "
                    f"available capacity is {binding_cap:.2f}."
                ),
                metrics={
                    "binding_constraint": binding_violation.value,
                    "available_capital": binding_cap,
                    "violations": [binding_violation.value],
                },
            )

        max_allowed_units = binding_cap / price

        # 7. Decision Determination
        violations: list[str] = []
        if desired_size > max_allowed_units:
            if self.allow_position_scaling:
                approved_size = round(max_allowed_units, 4)
                status = DecisionStatus.MODIFIED
                reason = (
                    f"BUY modified: desired size ({desired_size:.2f}) scaled down to "
                    f"{approved_size:.2f} units due to {binding_violation.value} cap."
                )
                violations.append(binding_violation.value)
            else:
                return RiskDecision(
                    status=DecisionStatus.REJECTED,
                    original_signal=signal,
                    approved_size=0.0,
                    max_loss_limit=0.0,
                    reason=(
                        f"BUY rejected: desired size ({desired_size:.2f}) exceeds capacity cap "
                        f"({max_allowed_units:.2f}) under {binding_violation.value}."
                    ),
                    metrics={
                        "desired_size": desired_size,
                        "max_allowed_units": max_allowed_units,
                        "violations": [binding_violation.value],
                    },
                )
        else:
            approved_size = round(desired_size, 4)
            status = DecisionStatus.APPROVED
            reason = f"BUY approved for {approved_size:.2f} units of {signal.symbol}."

        max_loss = (
            approved_size * abs(price - signal.stop_loss) if signal.stop_loss is not None else 0.0
        )

        position_value = approved_size * price
        metrics = {
            "proposed_size": desired_size,
            "approved_size": approved_size,
            "max_allowed_units": max_allowed_units,
            "binding_constraint": binding_violation.value,
            "entry_price": price,
            "target_price": signal.target_price,
            "stop_loss": signal.stop_loss,
            "risk_reward_ratio": rr_ratio,
            "position_value": position_value,
            "position_weight_pct": position_value / total_equity,
            "sector": sec_name,
            "sector_exposure_pct": (curr_sec_val + position_value) / total_equity
            if sec_name
            else 0.0,
            "cash_buffer_pct": (view.cash - position_value) / total_equity,
            "leverage": (view.gross_exposure + position_value) / total_equity,
            "drawdown_pct": view.current_drawdown_pct,
            "daily_pnl_pct": view.daily_pnl_pct,
            "violations": violations,
        }

        return RiskDecision(
            status=status,
            original_signal=signal,
            approved_size=approved_size,
            max_loss_limit=max_loss,
            reason=reason,
            metrics=metrics,
        )


# Public alias
SignalValidator = SignalRiskValidator
