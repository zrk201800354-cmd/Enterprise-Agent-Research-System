from __future__ import annotations

import math


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[float, float, float] | None:
    if period <= 0:
        raise ValueError("Period must be positive")
    if std_dev <= 0:
        raise ValueError("Standard deviation multiplier must be positive")
    if len(closes) < period:
        return None

    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return (upper, middle, lower)


def bollinger_percent_b(
    closes: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> float | None:
    bands = bollinger_bands(closes, period, std_dev)
    if bands is None:
        return None
    upper, _, lower = bands
    width = upper - lower
    if width == 0:
        return 0.5
    return (closes[-1] - lower) / width


def bollinger_bandwidth(
    closes: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> float | None:
    bands = bollinger_bands(closes, period, std_dev)
    if bands is None:
        return None
    upper, middle, lower = bands
    if middle == 0:
        return 0.0
    return (upper - lower) / middle
