from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Any

from quant_agent.broker import BrokerOrder
from quant_agent.config import AppConfig
from quant_agent.models import Bar, Position, Signal
from quant_agent.risk import RiskManager
from quant_agent.strategy import TrendRsiStrategy


@dataclass(frozen=True)
class PaperTradeAction:
    symbol: str
    side: str
    qty: int
    status: str
    current_allocation: float
    target_allocation: float
    estimated_price: float
    reason: str
    broker_response: dict[str, Any] | None = None


@dataclass(frozen=True)
class PaperCycleResult:
    timeframe: str
    submitted: bool
    account: dict[str, Any]
    actions: list[PaperTradeAction] = field(default_factory=list)


class PaperTradingCycle:
    def __init__(
        self,
        config: AppConfig,
        broker: Any,
        market_data: Any,
        strategy: Any | None = None,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self.config = config
        self.broker = broker
        self.market_data = market_data
        self.strategy = strategy or TrendRsiStrategy(config.strategy)
        self.risk_manager = risk_manager or RiskManager(config.risk, list(config.symbols))

    def run(self, start: str, end: str, timeframe: str = "1Min", submit_orders: bool = False) -> PaperCycleResult:
        account = self.broker.get_account()
        equity = _parse_positive_float(account.get("equity"), "account equity")
        raw_positions = self.broker.list_positions()
        positions = _positions_by_symbol(raw_positions)
        current_allocations = _allocations_by_symbol(raw_positions, equity)
        bars_by_symbol = self.market_data.fetch_bars(
            list(self.config.symbols),
            start=start,
            end=end,
            timeframe=timeframe,
        )

        actions: list[PaperTradeAction] = []
        for symbol in self.config.symbols:
            bars = bars_by_symbol.get(symbol, [])
            if not bars:
                actions.append(
                    PaperTradeAction(
                        symbol=symbol,
                        side="hold",
                        qty=0,
                        status="skipped",
                        current_allocation=current_allocations.get(symbol, 0.0),
                        target_allocation=0.0,
                        estimated_price=0.0,
                        reason="No market data returned",
                    )
                )
                continue

            signal = self.strategy.generate_signal(symbol, bars, positions.get(symbol))
            decision = self.risk_manager.approve(signal, current_allocations, positions)
            action = _build_action(symbol, bars[-1], positions.get(symbol), current_allocations, equity, signal, decision)

            if submit_orders and action.status == "planned":
                response = self.broker.submit_order_if_no_duplicate(BrokerOrder(action.symbol, action.qty, action.side))
                action = PaperTradeAction(
                    symbol=action.symbol,
                    side=action.side,
                    qty=action.qty,
                    status="submitted",
                    current_allocation=action.current_allocation,
                    target_allocation=action.target_allocation,
                    estimated_price=action.estimated_price,
                    reason=action.reason,
                    broker_response=response,
                )
            actions.append(action)

        return PaperCycleResult(timeframe=timeframe, submitted=submit_orders, account=account, actions=actions)


def _build_action(
    symbol: str,
    latest_bar: Bar,
    position: Position | None,
    current_allocations: dict[str, float],
    equity: float,
    signal: Signal,
    decision: Any,
) -> PaperTradeAction:
    current_qty = position.quantity if position else 0
    current_allocation = current_allocations.get(symbol, 0.0)
    if not decision.approved:
        return PaperTradeAction(
            symbol=symbol,
            side="hold",
            qty=0,
            status="skipped",
            current_allocation=current_allocation,
            target_allocation=0.0,
            estimated_price=latest_bar.close,
            reason=decision.reason,
        )

    target_qty = floor((equity * decision.target_allocation) / latest_bar.close)
    delta_qty = target_qty - current_qty
    if delta_qty == 0:
        return PaperTradeAction(
            symbol=symbol,
            side="hold",
            qty=0,
            status="skipped",
            current_allocation=current_allocation,
            target_allocation=decision.target_allocation,
            estimated_price=latest_bar.close,
            reason=f"Already near target allocation: {signal.reason}",
        )

    return PaperTradeAction(
        symbol=symbol,
        side="buy" if delta_qty > 0 else "sell",
        qty=abs(delta_qty),
        status="planned",
        current_allocation=current_allocation,
        target_allocation=decision.target_allocation,
        estimated_price=latest_bar.close,
        reason=decision.reason,
    )


def _positions_by_symbol(raw_positions: list[dict[str, Any]]) -> dict[str, Position]:
    positions: dict[str, Position] = {}
    for raw in raw_positions:
        symbol = str(raw.get("symbol", "")).upper()
        qty = floor(float(raw.get("qty", 0)))
        if symbol and qty > 0:
            positions[symbol] = Position(
                symbol=symbol,
                quantity=qty,
                average_price=float(raw.get("avg_entry_price") or raw.get("average_price") or 0.0),
            )
    return positions


def _allocations_by_symbol(raw_positions: list[dict[str, Any]], equity: float) -> dict[str, float]:
    allocations: dict[str, float] = {}
    for raw in raw_positions:
        symbol = str(raw.get("symbol", "")).upper()
        if symbol:
            allocations[symbol] = max(0.0, float(raw.get("market_value") or 0.0) / equity)
    return allocations


def _parse_positive_float(value: Any, label: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise RuntimeError(f"{label} must be positive")
    return parsed
