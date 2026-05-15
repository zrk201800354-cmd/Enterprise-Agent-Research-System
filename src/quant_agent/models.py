from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        prices = (self.open, self.high, self.low, self.close)
        if any(price <= 0 for price in prices):
            raise ValueError("Bar prices must be positive")
        if self.low > self.high:
            raise ValueError("Bar low cannot exceed high")
        if not self.low <= self.open <= self.high:
            raise ValueError("Bar open must be within low and high")
        if not self.low <= self.close <= self.high:
            raise ValueError("Bar close must be within low and high")
        if self.volume < 0:
            raise ValueError("Bar volume cannot be negative")


@dataclass(frozen=True)
class Signal:
    symbol: str
    target_allocation: float
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Signal symbol is required")
        if self.target_allocation < 0:
            raise ValueError("This MVP is long-only and rejects short targets")
        if self.target_allocation > 1:
            raise ValueError("Signal target allocation cannot exceed 100%")


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: int
    average_price: float

    @property
    def is_open(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True)
class Trade:
    date: str
    symbol: str
    side: str
    quantity: int
    price: float
    reason: str

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    exposure: float
