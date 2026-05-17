from __future__ import annotations


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    multiplier = 2.0 / (period + 1)
    result: list[float | None] = [None] * (period - 1)
    ema = sum(values[:period]) / period
    result.append(ema)
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
        result.append(ema)
    return result


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float] | None:
    if fast <= 0 or slow <= 0 or signal_period <= 0:
        raise ValueError("All periods must be positive")
    if fast >= slow:
        raise ValueError("Fast period must be less than slow period")
    if len(closes) < slow + signal_period:
        return None

    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)

    macd_line = [
        (f - s) if f is not None and s is not None else None
        for f, s in zip(fast_ema, slow_ema)
    ]

    macd_values = [v for v in macd_line if v is not None]
    if len(macd_values) < signal_period:
        return None

    signal_ema = _ema(macd_values, signal_period)
    if signal_ema is None:
        return None

    macd_val = macd_values[-1]
    histogram = macd_val - signal_ema
    return (macd_val, signal_ema, histogram)
