from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quant_agent.config import AppConfig
from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies import TrendRsiStrategy


@dataclass(frozen=True)
class ScreenResult:
    symbol: str
    signal: Signal
    latest_price: float
    avg_volume: float
    bars_count: int


@dataclass(frozen=True)
class ScreenSummary:
    total_scanned: int
    passed_filters: int
    buy_signals: list[ScreenResult]
    sell_signals: list[ScreenResult]
    hold_signals: list[ScreenResult]


DEFAULT_MIN_PRICE = 5.0
DEFAULT_MIN_AVG_VOLUME = 500_000
DEFAULT_TOP_N = 20


class StockScreener:
    def __init__(
        self,
        config: AppConfig,
        strategy: TrendRsiStrategy | None = None,
        min_price: float = DEFAULT_MIN_PRICE,
        min_avg_volume: float = DEFAULT_MIN_AVG_VOLUME,
        top_n: int = DEFAULT_TOP_N,
    ) -> None:
        self.config = config
        self.strategy = strategy or TrendRsiStrategy(config.strategy)
        self.min_price = min_price
        self.min_avg_volume = min_avg_volume
        self.top_n = top_n

    def screen(self, bars_by_symbol: dict[str, list[Bar]]) -> ScreenSummary:
        passed: list[tuple[str, list[Bar]]] = []
        for symbol, bars in bars_by_symbol.items():
            if len(bars) < self.config.strategy.long_window + 5:
                continue
            latest_price = bars[-1].close
            if latest_price < self.min_price:
                continue
            avg_volume = sum(b.volume for b in bars[-20:]) / min(20, len(bars))
            if avg_volume < self.min_avg_volume:
                continue
            passed.append((symbol, bars))

        buy_signals: list[ScreenResult] = []
        sell_signals: list[ScreenResult] = []
        hold_signals: list[ScreenResult] = []

        for symbol, bars in passed:
            signal = self.strategy.generate_signal(symbol, bars, None)
            latest_price = bars[-1].close
            avg_volume = sum(b.volume for b in bars[-20:]) / min(20, len(bars))
            result = ScreenResult(
                symbol=symbol,
                signal=signal,
                latest_price=latest_price,
                avg_volume=avg_volume,
                bars_count=len(bars),
            )

            if signal.target_allocation > 0:
                if "Enter" in signal.reason:
                    buy_signals.append(result)
                else:
                    hold_signals.append(result)
            elif "Exit" in signal.reason:
                sell_signals.append(result)
            else:
                hold_signals.append(result)

        buy_signals.sort(key=lambda r: r.signal.target_allocation, reverse=True)
        sell_signals.sort(key=lambda r: r.signal.target_allocation)

        return ScreenSummary(
            total_scanned=len(bars_by_symbol),
            passed_filters=len(passed),
            buy_signals=buy_signals[: self.top_n],
            sell_signals=sell_signals[: self.top_n],
            hold_signals=hold_signals[: self.top_n],
        )
