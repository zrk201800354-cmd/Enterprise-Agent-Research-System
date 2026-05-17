from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from quant_agent.crypto.base import Candle
from quant_agent.models import Bar


def candle_to_bar(candle: Candle) -> Bar:
    dt = datetime.fromtimestamp(candle.ts / 1000, tz=timezone.utc)
    return Bar(
        date=dt.strftime("%Y-%m-%d %H:%M"),
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=int(candle.vol),
    )


@dataclass
class CryptoPosition:
    symbol: str
    quantity: float
    average_price: float
    highest_price: float = 0.0

    def __post_init__(self) -> None:
        if self.highest_price == 0.0:
            self.highest_price = self.average_price

    @property
    def is_open(self) -> bool:
        return self.quantity > 0

    @property
    def market_value(self) -> float:
        return self.quantity * self.average_price

    @property
    def pnl_pct(self) -> float:
        if self.average_price <= 0:
            return 0.0
        return (self.highest_price - self.average_price) / self.average_price


@dataclass(frozen=True)
class CryptoTrade:
    date: str
    symbol: str
    side: str
    quantity: float
    price: float
    reason: str

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass
class BotStatus:
    running: bool
    uptime_seconds: float
    symbols: list[str]
    strategy: str
    timeframe: str
    equity: float
    cash: float
    positions: list[dict]
    trades_today: int
    total_trades: int
    pnl_total: float
    pnl_today: float
    win_rate: float
    max_drawdown: float
    trailing_stops: dict[str, float]
    last_optimization: str
    optimization_result: dict | None
    errors: list[str]
