from __future__ import annotations

from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy


@register_strategy
class DCAStrategy:
    name = "dca"
    allows_live_trading = True

    def __init__(
        self,
        interval_days: int = 7,
        amount_per_buy: float = 1000.0,
        portfolio_value: float = 100_000.0,
    ) -> None:
        if interval_days <= 0:
            raise ValueError("interval_days must be positive")
        if amount_per_buy <= 0:
            raise ValueError("amount_per_buy must be positive")
        self.interval_days = interval_days
        self.amount_per_buy = amount_per_buy
        self.portfolio_value = portfolio_value

    def generate_signal(self, symbol: str, bars: list[Bar], existing_position: Position | None) -> Signal:
        if len(bars) < 2:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Not enough data for DCA")

        target_allocation = min(self.amount_per_buy / self.portfolio_value, 0.20)

        if existing_position and existing_position.is_open:
            current_value = existing_position.quantity * bars[-1].close
            current_alloc = current_value / self.portfolio_value
            if current_alloc >= target_allocation * 3:
                return Signal(symbol=symbol, target_allocation=0.0, reason="DCA: sufficient position accumulated")
            return Signal(symbol=symbol, target_allocation=target_allocation, reason="DCA: continue accumulation")

        return Signal(symbol=symbol, target_allocation=target_allocation, reason="DCA: start accumulation")
