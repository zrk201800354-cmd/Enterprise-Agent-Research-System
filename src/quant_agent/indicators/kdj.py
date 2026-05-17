from __future__ import annotations


def kdj(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 9,
    d_period: int = 3,
    j_period: int = 3,
) -> tuple[float, float, float] | None:
    if k_period <= 0 or d_period <= 0 or j_period <= 0:
        raise ValueError("All periods must be positive")
    n = len(closes)
    if n < k_period or len(highs) < k_period or len(lows) < k_period:
        return None
    if n != len(highs) or n != len(lows):
        raise ValueError("Highs, lows, and closes must have the same length")

    rsv_values: list[float] = []
    for i in range(k_period - 1, n):
        period_high = max(highs[i - k_period + 1 : i + 1])
        period_low = min(lows[i - k_period + 1 : i + 1])
        if period_high == period_low:
            rsv_values.append(50.0)
        else:
            rsv_values.append((closes[i] - period_low) / (period_high - period_low) * 100.0)

    k = 50.0
    for rsv in rsv_values:
        k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv

    k_history = [50.0]
    current_k = 50.0
    for rsv in rsv_values:
        current_k = (2.0 / 3.0) * current_k + (1.0 / 3.0) * rsv
        k_history.append(current_k)
    k = k_history[-1]

    d = 50.0
    for k_val in k_history[-d_period:]:
        d = (2.0 / 3.0) * d + (1.0 / 3.0) * k_val

    j = 3.0 * k - 2.0 * d
    return (k, d, j)
