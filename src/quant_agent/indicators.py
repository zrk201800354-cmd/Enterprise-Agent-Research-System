from __future__ import annotations


def simple_moving_average(values: list[float], window: int) -> float | None:
    if window <= 0:
        raise ValueError("Window must be positive")
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def relative_strength_index(values: list[float], period: int) -> float | None:
    if period <= 0:
        raise ValueError("Period must be positive")
    if len(values) <= period:
        return None

    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = deltas[-period:]
    gains = [max(delta, 0.0) for delta in recent]
    losses = [abs(min(delta, 0.0)) for delta in recent]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0 and average_gain == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))
