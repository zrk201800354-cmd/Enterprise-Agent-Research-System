from __future__ import annotations

from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy


@register_strategy
class GridStrategy:
    name = "grid"
    allows_live_trading = False

    def __init__(
        self,
        grid_count: int = 10,
        lower_price: float | None = None,
        upper_price: float | None = None,
        target_allocation: float = 0.10,
    ) -> None:
        if grid_count < 2:
            raise ValueError("grid_count must be at least 2")
        self.grid_count = grid_count
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.target_allocation = target_allocation

    def _get_price_range(self, bars: list[Bar]) -> tuple[float, float]:
        if self.lower_price is not None and self.upper_price is not None:
            return self.lower_price, self.upper_price
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        return min(lows), max(highs)

    def _grid_levels(self, lower: float, upper: float) -> list[float]:
        step = (upper - lower) / (self.grid_count - 1)
        return [lower + i * step for i in range(self.grid_count)]

    def generate_signal(self, symbol: str, bars: list[Bar], existing_position: Position | None) -> Signal:
        if len(bars) < 20:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Not enough history for grid calculation")

        lower, upper = self._get_price_range(bars)
        if upper <= lower:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Invalid price range for grid")

        levels = self._grid_levels(lower, upper)
        current_price = bars[-1].close
        step = (upper - lower) / (self.grid_count - 1)

        nearest_below = None
        nearest_above = None
        for level in levels:
            if level <= current_price:
                nearest_below = level
            if level >= current_price and nearest_above is None:
                nearest_above = level

        if nearest_below is not None and current_price - nearest_below < step * 0.3:
            alloc = self.target_allocation if existing_position is None or not existing_position.is_open else self.target_allocation * 0.5
            return Signal(symbol=symbol, target_allocation=alloc, reason=f"Grid buy near level {nearest_below:.2f}")

        if nearest_above is not None and nearest_above - current_price < step * 0.3:
            if existing_position and existing_position.is_open:
                return Signal(symbol=symbol, target_allocation=0.0, reason=f"Grid sell near level {nearest_above:.2f}")
            return Signal(symbol=symbol, target_allocation=0.0, reason=f"Grid skip sell at level {nearest_above:.2f} (no position)")

        return Signal(symbol=symbol, target_allocation=0.0, reason="Price between grid levels, no action")
