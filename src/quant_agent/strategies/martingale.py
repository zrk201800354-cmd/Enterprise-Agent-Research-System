from __future__ import annotations

from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy


@register_strategy
class MartingaleStrategy:
    name = "martingale"
    allows_live_trading = False

    def __init__(
        self,
        base_allocation: float = 0.05,
        max_doubles: int = 3,
    ) -> None:
        if base_allocation <= 0 or base_allocation > 0.5:
            raise ValueError("base_allocation must be between 0 and 0.5")
        if max_doubles < 1:
            raise ValueError("max_doubles must be at least 1")
        self.base_allocation = base_allocation
        self.max_doubles = max_doubles

    def generate_signal(self, symbol: str, bars: list[Bar], existing_position: Position | None) -> Signal:
        if len(bars) < 5:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Not enough data for Martingale")

        recent_closes = [b.close for b in bars[-5:]]
        is_declining = all(recent_closes[i] < recent_closes[i - 1] for i in range(1, len(recent_closes)))

        if existing_position and existing_position.is_open:
            entry_price = existing_position.average_price
            current_price = bars[-1].close
            pnl_pct = (current_price - entry_price) / entry_price

            if pnl_pct > 0.05:
                return Signal(symbol=symbol, target_allocation=0.0, reason="Martingale: take profit on winning position")

            if pnl_pct < -0.08 and is_declining:
                doubles = min(int(abs(pnl_pct) / 0.08), self.max_doubles)
                alloc = min(self.base_allocation * (2 ** doubles), self.base_allocation * (2 ** self.max_doubles))
                return Signal(symbol=symbol, target_allocation=alloc, reason=f"Martingale: double down ({doubles}x) after {pnl_pct:.1%} loss")

            return Signal(symbol=symbol, target_allocation=self.base_allocation, reason="Martingale: hold position")

        if is_declining:
            return Signal(symbol=symbol, target_allocation=self.base_allocation, reason="Martingale: enter on declining price")

        return Signal(symbol=symbol, target_allocation=0.0, reason="Martingale: no entry (price not declining)")
