from __future__ import annotations

import math


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
    n = len(closes)
    if n < period + 1:
        return None

    tr_values: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    if len(tr_values) < period:
        return None

    atr_val = sum(tr_values[:period]) / period
    for tr in tr_values[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def supertrend(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[float, int] | None:
    if period <= 0:
        raise ValueError("Period must be positive")
    if multiplier <= 0:
        raise ValueError("Multiplier must be positive")
    n = len(closes)
    if n < period + 1:
        return None
    if n != len(highs) or n != len(lows):
        raise ValueError("Highs, lows, and closes must have the same length")

    atr_val = _atr(highs, lows, closes, period)
    if atr_val is None:
        return None

    hl2 = (highs[-1] + lows[-1]) / 2.0
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    if closes[-1] <= upper_band:
        direction = -1
        return (upper_band, direction)
    else:
        direction = 1
        return (lower_band, direction)
