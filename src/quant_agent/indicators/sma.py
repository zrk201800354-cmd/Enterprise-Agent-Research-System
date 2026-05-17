from __future__ import annotations


def simple_moving_average(values: list[float], window: int) -> float | None:
    if window <= 0:
        raise ValueError("Window must be positive")
    if len(values) < window:
        return None
    return sum(values[-window:]) / window
