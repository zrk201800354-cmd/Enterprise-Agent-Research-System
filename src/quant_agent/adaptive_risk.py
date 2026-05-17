from __future__ import annotations

from dataclasses import dataclass

from quant_agent.indicators import atr as calc_atr
from quant_agent.models import Bar


@dataclass(frozen=True)
class AdaptiveRiskParams:
    """Dynamic risk parameters adjusted by market volatility."""
    stop_loss_pct: float
    take_profit_pct: float
    position_scale: float  # multiplier for target allocation (0.5 = half, 1.5 = 1.5x)
    volatility_regime: str  # "high", "normal", "low"


def compute_atr(bars: list[Bar], period: int = 14) -> float | None:
    """Compute ATR from bar data."""
    if len(bars) < period + 1:
        return None
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    closes = [b.close for b in bars]
    return calc_atr(highs, lows, closes, period)


def adaptive_risk_params(
    bars: list[Bar],
    base_stop_loss: float = 0.08,
    base_take_profit: float = 0.20,
    atr_period: int = 14,
    high_vol_multiplier: float = 1.5,
    low_vol_multiplier: float = 0.7,
) -> AdaptiveRiskParams:
    """
    Compute adaptive risk parameters based on ATR volatility.

    High volatility (ATR > mean * high_vol_multiplier):
        - Tighter stop-loss (5%)
        - Lower position scale (0.6x)

    Low volatility (ATR < mean * low_vol_multiplier):
        - Wider stop-loss (12%)
        - Higher position scale (1.2x)

    Normal volatility:
        - Default parameters
    """
    if len(bars) < atr_period * 2:
        return AdaptiveRiskParams(
            stop_loss_pct=base_stop_loss,
            take_profit_pct=base_take_profit,
            position_scale=1.0,
            volatility_regime="normal",
        )

    # Calculate current ATR
    current_atr = compute_atr(bars, atr_period)
    if current_atr is None:
        return AdaptiveRiskParams(
            stop_loss_pct=base_stop_loss,
            take_profit_pct=base_take_profit,
            position_scale=1.0,
            volatility_regime="normal",
        )

    # Calculate historical average ATR
    closes = [b.close for b in bars]
    current_price = closes[-1]
    if current_price <= 0:
        return AdaptiveRiskParams(
            stop_loss_pct=base_stop_loss,
            take_profit_pct=base_take_profit,
            position_scale=1.0,
            volatility_regime="normal",
        )

    # ATR as percentage of price
    atr_pct = current_atr / current_price

    # Calculate rolling ATR% over historical windows
    atr_pcts: list[float] = []
    for i in range(atr_period * 2, len(bars)):
        window = bars[i - atr_period:i]
        atr_val = compute_atr(window, atr_period)
        if atr_val is not None and window[-1].close > 0:
            atr_pcts.append(atr_val / window[-1].close)

    if not atr_pcts:
        return AdaptiveRiskParams(
            stop_loss_pct=base_stop_loss,
            take_profit_pct=base_take_profit,
            position_scale=1.0,
            volatility_regime="normal",
        )

    avg_atr_pct = sum(atr_pcts) / len(atr_pcts)

    # Determine regime
    if atr_pct > avg_atr_pct * high_vol_multiplier:
        # High volatility: tighter stop, smaller position
        return AdaptiveRiskParams(
            stop_loss_pct=max(base_stop_loss * 0.6, 0.03),
            take_profit_pct=base_take_profit * 0.8,
            position_scale=0.6,
            volatility_regime="high",
        )
    elif atr_pct < avg_atr_pct * low_vol_multiplier:
        # Low volatility: wider stop, larger position
        return AdaptiveRiskParams(
            stop_loss_pct=min(base_stop_loss * 1.5, 0.15),
            take_profit_pct=base_take_profit * 1.2,
            position_scale=1.2,
            volatility_regime="low",
        )
    else:
        # Normal volatility
        return AdaptiveRiskParams(
            stop_loss_pct=base_stop_loss,
            take_profit_pct=base_take_profit,
            position_scale=1.0,
            volatility_regime="normal",
        )
