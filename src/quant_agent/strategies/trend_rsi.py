from __future__ import annotations

from quant_agent.config import StrategyConfig
from quant_agent.indicators import relative_strength_index, simple_moving_average
from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy


@register_strategy
class TrendRsiStrategy:
    name = "trend_rsi"
    allows_live_trading = True

    def __init__(self, config: StrategyConfig | None = None, target_allocation: float = 0.20) -> None:
        self.config = config or StrategyConfig()
        self.target_allocation = target_allocation

    def generate_signal(self, symbol: str, bars: list[Bar], existing_position: Position | None) -> Signal:
        closes = [bar.close for bar in bars]
        short_ma = simple_moving_average(closes, self.config.short_window)
        long_ma = simple_moving_average(closes, self.config.long_window)
        rsi = relative_strength_index(closes, self.config.rsi_period)

        if short_ma is None or long_ma is None or rsi is None:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Not enough history for indicators")

        if short_ma <= long_ma:
            if existing_position and existing_position.is_open:
                return Signal(symbol=symbol, target_allocation=0.0, reason="Exit because trend turned negative")
            return Signal(symbol=symbol, target_allocation=0.0, reason="No entry because trend is not positive")

        if existing_position and existing_position.is_open:
            return Signal(symbol=symbol, target_allocation=self.target_allocation, reason="Hold while trend remains positive")

        if rsi >= self.config.rsi_entry_ceiling:
            return Signal(symbol=symbol, target_allocation=0.0, reason=f"No entry because RSI {rsi:.2f} is too high")

        return Signal(
            symbol=symbol,
            target_allocation=self.target_allocation,
            reason="Enter because positive trend and RSI allowed",
        )
