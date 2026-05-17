from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ticker:
    inst_id: str
    last: float
    bid: float
    ask: float
    vol24h: float
    high24h: float
    low24h: float
    ts: int  # unix ms


@dataclass(frozen=True)
class BookLevel:
    price: float
    qty: float


@dataclass(frozen=True)
class OrderBook:
    inst_id: str
    bids: list[BookLevel]
    asks: list[BookLevel]
    ts: int  # unix ms


@dataclass(frozen=True)
class Trade:
    inst_id: str
    trade_id: str
    price: float
    qty: float
    side: str  # "buy" or "sell"
    ts: int  # unix ms


@dataclass(frozen=True)
class Candle:
    inst_id: str
    ts: int  # unix ms, candle open time
    open: float
    high: float
    low: float
    close: float
    vol: float
    complete: bool  # True if candle is closed


class CryptoDataStore:
    """Thread-safe in-memory store for real-time crypto data."""

    def __init__(self, max_trades: int = 1000, max_candles: int = 3600) -> None:
        self._lock = threading.Lock()
        self._tickers: dict[str, Ticker] = {}
        self._trades: dict[str, list[Trade]] = {}
        self._candles: dict[str, list[Candle]] = {}
        self._books: dict[str, OrderBook] = {}
        self._max_trades = max_trades
        self._max_candles = max_candles

    def update_ticker(self, ticker: Ticker) -> None:
        with self._lock:
            self._tickers[ticker.inst_id] = ticker

    def get_ticker(self, inst_id: str) -> Ticker | None:
        with self._lock:
            return self._tickers.get(inst_id)

    def get_all_tickers(self) -> dict[str, Ticker]:
        with self._lock:
            return dict(self._tickers)

    def append_trade(self, trade: Trade) -> None:
        with self._lock:
            buf = self._trades.setdefault(trade.inst_id, [])
            buf.append(trade)
            if len(buf) > self._max_trades:
                self._trades[trade.inst_id] = buf[-self._max_trades:]

    def get_trades(self, inst_id: str, limit: int = 50) -> list[Trade]:
        with self._lock:
            buf = self._trades.get(inst_id, [])
            return list(buf[-limit:])

    def append_candle(self, candle: Candle) -> None:
        with self._lock:
            buf = self._candles.setdefault(candle.inst_id, [])
            # replace last candle if same ts (update in-progress candle)
            if buf and buf[-1].ts == candle.ts:
                buf[-1] = candle
            else:
                buf.append(candle)
            if len(buf) > self._max_candles:
                self._candles[candle.inst_id] = buf[-self._max_candles:]

    def get_candles(self, inst_id: str, limit: int = 60) -> list[Candle]:
        with self._lock:
            buf = self._candles.get(inst_id, [])
            return list(buf[-limit:])

    def update_book(self, book: OrderBook) -> None:
        with self._lock:
            self._books[book.inst_id] = book

    def get_book(self, inst_id: str) -> OrderBook | None:
        with self._lock:
            return self._books.get(inst_id)


class CryptoAdapter(ABC):
    """Abstract base class for crypto exchange WebSocket adapters."""

    def __init__(self) -> None:
        self._store = CryptoDataStore()
        self._connected = False
        self._subscribed: set[str] = set()

    @property
    def store(self) -> CryptoDataStore:
        return self._store

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def subscribed_symbols(self) -> list[str]:
        return sorted(self._subscribed)

    @abstractmethod
    def start(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        """Start WebSocket connection and subscribe to channels."""

    @abstractmethod
    def stop(self) -> None:
        """Stop WebSocket connection."""

    @abstractmethod
    def subscribe(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        """Subscribe to additional symbols."""

    @abstractmethod
    def unsubscribe(self, inst_ids: list[str]) -> None:
        """Unsubscribe from symbols."""

    def status(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "subscribed": self.subscribed_symbols,
            "exchange": self.__class__.__name__,
        }
