from __future__ import annotations

from dataclasses import dataclass

from quant_agent.indicators import adx as calc_adx
from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy
from quant_agent.strategies.grid import GridStrategy
from quant_agent.strategies.multi_indicator import MultiIndicatorStrategy


@dataclass(frozen=True)
class RegimeSwitchConfig:
    adx_period: int = 14
    trend_threshold: float = 25.0  # ADX above this = trending
    range_threshold: float = 20.0  # ADX below this = ranging
    # Between range_threshold and trend_threshold: keep current regime


@register_strategy
class RegimeSwitchStrategy:
    """
    Automatically switches between trending and ranging strategies
    based on ADX (Average Directional Index).

    - ADX > trend_threshold: use MultiIndicator (trend-following)
    - ADX < range_threshold: use Grid (mean-reversion)
    - Between: maintain current strategy
    """

    name = "regime_switch"
    allows_live_trading = True

    def __init__(
        self,
        config: RegimeSwitchConfig | None = None,
        target_allocation: float = 0.15,
    ) -> None:
        self.config = config or RegimeSwitchConfig()
        self.target_allocation = target_allocation
        self._trend_strategy = MultiIndicatorStrategy(target_allocation=target_allocation)
        self._range_strategy = GridStrategy(target_allocation=target_allocation)
        self._current_regime: str = "unknown"

    def _detect_regime(self, bars: list[Bar]) -> str:
        """Detect market regime using ADX."""
        if len(bars) < self.config.adx_period * 2 + 1:
            return "unknown"

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]

        adx_val = calc_adx(highs, lows, closes, self.config.adx_period)
        if adx_val is None:
            return "unknown"

        if adx_val >= self.config.trend_threshold:
            return "trending"
        elif adx_val <= self.config.range_threshold:
            return "ranging"
        else:
            # Transition zone - keep current regime
            return self._current_regime if self._current_regime != "unknown" else "trending"

    def generate_signal(
        self, symbol: str, bars: list[Bar], existing_position: Position | None
    ) -> Signal:
        regime = self._detect_regime(bars)
        if regime != "unknown":
            self._current_regime = regime

        if regime == "ranging":
            signal = self._range_strategy.generate_signal(symbol, bars, existing_position)
            reason = f"[震荡行情] {signal.reason}"
        else:
            signal = self._trend_strategy.generate_signal(symbol, bars, existing_position)
            reason = f"[趋势行情] {signal.reason}"

        return Signal(
            symbol=symbol,
            target_allocation=signal.target_allocation,
            reason=reason,
        )
