from __future__ import annotations


def adx(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> float | None:
    """
    Average Directional Index (ADX).

    Returns the ADX value (0-100).
    ADX > 25 indicates a trending market.
    ADX < 20 indicates a ranging market.
    """
    if period <= 0:
        raise ValueError("Period must be positive")
    n = len(closes)
    if n < period * 2 + 1:
        return None
    if n != len(highs) or n != len(lows):
        raise ValueError("Highs, lows, and closes must have the same length")

    # Calculate +DM, -DM, and TR
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_values: list[float] = []

    for i in range(1, n):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]

        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    if len(tr_values) < period:
        return None

    # Smooth with Wilder's method
    atr_val = sum(tr_values[:period]) / period
    plus_di_smooth = sum(plus_dm[:period]) / period
    minus_di_smooth = sum(minus_dm[:period]) / period

    dx_values: list[float] = []

    for i in range(period, len(tr_values)):
        atr_val = (atr_val * (period - 1) + tr_values[i]) / period
        plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm[i]) / period
        minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm[i]) / period

        if atr_val > 0:
            plus_di = 100 * plus_di_smooth / atr_val
            minus_di = 100 * minus_di_smooth / atr_val
        else:
            plus_di = 0.0
            minus_di = 0.0

        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx = 100 * abs(plus_di - minus_di) / di_sum
        else:
            dx = 0.0
        dx_values.append(dx)

    if len(dx_values) < period:
        return None

    # ADX is the smoothed DX
    adx_val = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        adx_val = (adx_val * (period - 1) + dx) / period

    return adx_val
