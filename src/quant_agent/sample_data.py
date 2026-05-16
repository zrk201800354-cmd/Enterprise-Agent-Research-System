from __future__ import annotations

from datetime import date, timedelta

from quant_agent.models import Bar


def load_sample_bars(symbols: list[str] | tuple[str, ...]) -> dict[str, list[Bar]]:
    return {symbol: _make_symbol_bars(offset=index * 2.0) for index, symbol in enumerate(symbols)}


def _make_symbol_bars(offset: float) -> list[Bar]:
    bars: list[Bar] = []
    price = 100.0 + offset
    current_date = date(2025, 1, 2)

    for index in range(160):
        if index < 40:
            price += 0.15
        elif index < 95:
            price += 0.45
        elif index < 112:
            price -= 0.20
        else:
            price += 0.30

        rounded = round(price, 2)
        bars.append(
            Bar(
                date=current_date.isoformat(),
                open=rounded,
                high=round(rounded + 1.0, 2),
                low=round(rounded - 1.0, 2),
                close=rounded,
                volume=1_000_000 + index,
            )
        )
        current_date += timedelta(days=1)

    return bars
