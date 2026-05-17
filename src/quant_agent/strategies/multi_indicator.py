from __future__ import annotations

from dataclasses import dataclass

from quant_agent.indicators import (
    bollinger_bands,
    macd,
    relative_strength_index,
    supertrend,
)
from quant_agent.models import Bar, Position, Signal
from quant_agent.strategies.base import register_strategy


@dataclass(frozen=True)
class MultiIndicatorConfig:
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    st_period: int = 10
    st_multiplier: float = 3.0
    buy_threshold: int = 3
    sell_threshold: int = 3


@register_strategy
class MultiIndicatorStrategy:
    name = "multi_indicator"
    allows_live_trading = True

    def __init__(
        self,
        config: MultiIndicatorConfig | None = None,
        target_allocation: float = 0.15,
    ) -> None:
        self.config = config or MultiIndicatorConfig()
        self.target_allocation = target_allocation

    def _count_votes(
        self, closes: list[float], highs: list[float], lows: list[float]
    ) -> tuple[int, int, list[str]]:
        """Count buy/sell votes from all indicators. Returns (buy_votes, sell_votes, reasons)."""
        buy_votes = 0
        sell_votes = 0
        reasons: list[str] = []
        cfg = self.config

        # 1. RSI
        rsi = relative_strength_index(closes, cfg.rsi_period)
        if rsi is not None:
            if rsi < cfg.rsi_oversold:
                buy_votes += 1
                reasons.append(f"RSI超卖({rsi:.1f})")
            elif rsi > cfg.rsi_overbought:
                sell_votes += 1
                reasons.append(f"RSI超买({rsi:.1f})")

        # 2. MACD
        macd_val = macd(closes, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
        if macd_val is not None:
            macd_line, signal_line, histogram = macd_val
            if macd_line > signal_line:
                buy_votes += 1
                reasons.append("MACD金叉")
            elif macd_line < signal_line:
                sell_votes += 1
                reasons.append("MACD死叉")

        # 3. Bollinger Bands
        bb = bollinger_bands(closes, cfg.bb_period, cfg.bb_std)
        if bb is not None:
            upper, middle, lower = bb
            price = closes[-1]
            if price <= lower:
                buy_votes += 1
                reasons.append(f"触及布林下轨({lower:.2f})")
            elif price >= upper:
                sell_votes += 1
                reasons.append(f"触及布林上轨({upper:.2f})")

        # 4. SuperTrend
        st = supertrend(highs, lows, closes, cfg.st_period, cfg.st_multiplier)
        if st is not None:
            st_value, direction = st
            if direction == 1:
                buy_votes += 1
                reasons.append("超级趋势看涨")
            elif direction == -1:
                sell_votes += 1
                reasons.append("超级趋势看跌")

        return buy_votes, sell_votes, reasons

    def generate_signal(
        self, symbol: str, bars: list[Bar], existing_position: Position | None
    ) -> Signal:
        min_bars = max(
            self.config.macd_slow + self.config.macd_signal,
            self.config.bb_period,
            self.config.st_period + 1,
            self.config.rsi_period + 1,
        )
        if len(bars) < min_bars:
            return Signal(
                symbol=symbol,
                target_allocation=0.0,
                reason=f"数据不足(需要{min_bars}根K线)",
            )

        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]

        buy_votes, sell_votes, reasons = self._count_votes(closes, highs, lows)
        cfg = self.config
        has_position = existing_position is not None and existing_position.is_open

        reason_str = " | ".join(reasons) if reasons else "无明确信号"

        # Sell signal (check first to allow buy_threshold=0)
        if sell_votes >= cfg.sell_threshold:
            if has_position:
                return Signal(
                    symbol=symbol,
                    target_allocation=0.0,
                    reason=f"卖出信号({sell_votes}票): {reason_str}",
                )
            return Signal(
                symbol=symbol,
                target_allocation=0.0,
                reason=f"空仓观望({sell_votes}票卖出): {reason_str}",
            )

        # Buy signal
        if buy_votes >= cfg.buy_threshold:
            if has_position:
                return Signal(
                    symbol=symbol,
                    target_allocation=self.target_allocation,
                    reason=f"维持仓位({buy_votes}票买入): {reason_str}",
                )
            return Signal(
                symbol=symbol,
                target_allocation=self.target_allocation,
                reason=f"买入信号({buy_votes}票): {reason_str}",
            )

        # No clear signal
        if has_position:
            return Signal(
                symbol=symbol,
                target_allocation=self.target_allocation,
                reason=f"持有(信号不明确): {reason_str}",
            )
        return Signal(
            symbol=symbol,
            target_allocation=0.0,
            reason=f"观望(信号不明确): {reason_str}",
        )
