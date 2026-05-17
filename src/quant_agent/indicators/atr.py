from __future__ import annotations


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> float | None:
    """Average True Range (ATR)."""
    if period <= 0:
        raise ValueError("Period must be positive")
    n = len(closes)
    if n < period + 1:
        return None
    if n != len(highs) or n != len(lows):
        raise ValueError("Highs, lows, and closes must have the same length")

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
