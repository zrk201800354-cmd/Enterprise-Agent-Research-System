from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from quant_agent.crypto.base import (
    BookLevel,
    Candle,
    CryptoAdapter,
    OrderBook,
    Ticker,
    Trade,
)

logger = logging.getLogger(__name__)

OKX_PUBLIC_WS = "wss://ws.okx.com:8443/ws/v5/public"
OKX_BUSINESS_WS = "wss://ws.okx.com:8443/ws/v5/business"
# tickers/trades/books go to public; candle* goes to business
PUBLIC_CHANNELS = ("tickers", "trades", "books5")
CANDLE_CHANNELS = ("candle1m",)
DEFAULT_CHANNELS = PUBLIC_CHANNELS + CANDLE_CHANNELS
PING_INTERVAL = 25
RECONNECT_BASE = 2
RECONNECT_MAX = 60


class OKXAdapter(CryptoAdapter):
    """OKX WebSocket v5 market data adapter.

    Uses two connections:
    - public: tickers, trades, books5
    - business: candle1m (1-minute candles)

    Note: candle1s only works for SWAP instruments on business WS.
    """

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._channels: list[str] = list(DEFAULT_CHANNELS)

    def start(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        if self._thread and self._thread.is_alive():
            if inst_ids:
                self.subscribe(inst_ids, channels)
            return
        if channels:
            self._channels = list(channels)
        self._subscribed = set(inst_ids)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._connected = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    def subscribe(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        new_ids = [i for i in inst_ids if i not in self._subscribed]
        if not new_ids:
            return
        self._subscribed.update(new_ids)

    def unsubscribe(self, inst_ids: list[str]) -> None:
        for i in inst_ids:
            self._subscribed.discard(i)

    def _run_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ws_loop())
        except Exception as exc:
            logger.error("OKX WS thread error: %s", exc)
        finally:
            self._connected = False
            self._loop.close()

    async def _ws_loop(self) -> None:
        backoff = RECONNECT_BASE
        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
                backoff = RECONNECT_BASE
            except Exception as exc:
                logger.warning("OKX WS disconnected: %s, reconnecting in %ds", exc, backoff)
                self._connected = False
                if self._stop_event.wait(backoff):
                    return
                backoff = min(backoff * 2, RECONNECT_MAX)

    async def _connect_and_listen(self) -> None:
        import websockets

        public_chs = [ch for ch in self._channels if ch in PUBLIC_CHANNELS]
        candle_chs = [ch for ch in self._channels if ch.startswith("candle")]

        async with websockets.connect(OKX_PUBLIC_WS, ping_interval=None) as ws_pub:
            self._connected = True
            logger.info("OKX public WS connected")

            if self._subscribed and public_chs:
                args = [{"channel": ch, "instId": iid}
                        for ch in public_chs for iid in self._subscribed]
                await ws_pub.send(json.dumps({"op": "subscribe", "args": args}))

            tasks = [self._listen(ws_pub, "public"), self._ping(ws_pub)]

            if candle_chs:
                ws_biz = await websockets.connect(OKX_BUSINESS_WS, ping_interval=None)
                logger.info("OKX business WS connected")
                if self._subscribed:
                    args = [{"channel": ch, "instId": iid}
                            for ch in candle_chs for iid in self._subscribed]
                    await ws_biz.send(json.dumps({"op": "subscribe", "args": args}))
                tasks.append(self._listen(ws_biz, "business"))
                tasks.append(self._ping(ws_biz))

            await asyncio.gather(*tasks)

    async def _listen(self, ws: Any, label: str) -> None:
        try:
            async for raw in ws:
                if self._stop_event.is_set():
                    break
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                if raw in ("pong", "ping"):
                    if raw == "ping":
                        await ws.send("pong")
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if "event" in msg:
                    if msg["event"] == "error":
                        logger.warning("OKX %s error: %s", label, msg.get("msg", ""))
                    continue

                arg = msg.get("arg", {})
                channel = arg.get("channel", "")
                data = msg.get("data")
                if not data:
                    continue

                try:
                    if channel == "tickers":
                        self._handle_tickers(data)
                    elif channel == "trades":
                        self._handle_trades(data)
                    elif channel.startswith("candle"):
                        self._handle_candles(data, arg.get("instId", ""))
                    elif channel.startswith("books"):
                        self._handle_books(data, arg.get("instId", ""))
                except Exception as exc:
                    logger.debug("Error parsing %s: %s", channel, exc)
        except Exception as exc:
            logger.warning("OKX %s listener error: %s", label, exc)

    async def _ping(self, ws: Any) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(PING_INTERVAL)
            try:
                await ws.send("ping")
            except Exception:
                break

    def _handle_tickers(self, data: list[dict[str, Any]]) -> None:
        for d in data:
            try:
                ticker = Ticker(
                    inst_id=d["instId"],
                    last=float(d["last"]),
                    bid=float(d.get("bidPx", 0)),
                    ask=float(d.get("askPx", 0)),
                    vol24h=float(d.get("vol24h", 0)),
                    high24h=float(d.get("high24h", 0)),
                    low24h=float(d.get("low24h", 0)),
                    ts=int(d.get("ts", 0)),
                )
                self._store.update_ticker(ticker)
            except (KeyError, ValueError):
                pass

    def _handle_trades(self, data: list[dict[str, Any]]) -> None:
        for d in data:
            try:
                trade = Trade(
                    inst_id=d["instId"],
                    trade_id=d.get("tradeId", ""),
                    price=float(d["px"]),
                    qty=float(d["sz"]),
                    side=d.get("side", "buy"),
                    ts=int(d.get("ts", 0)),
                )
                self._store.append_trade(trade)
            except (KeyError, ValueError):
                pass

    def _handle_candles(self, data: list[list[str]], inst_id: str) -> None:
        for arr in data:
            try:
                candle = Candle(
                    inst_id=inst_id,
                    ts=int(arr[0]),
                    open=float(arr[1]),
                    high=float(arr[2]),
                    low=float(arr[3]),
                    close=float(arr[4]),
                    vol=float(arr[5]),
                    complete=arr[8] == "1",
                )
                self._store.append_candle(candle)
            except (IndexError, ValueError):
                pass

    def _handle_books(self, data: list[dict[str, Any]], inst_id: str) -> None:
        for d in data:
            try:
                bids = [BookLevel(price=float(b[0]), qty=float(b[1])) for b in d.get("bids", [])]
                asks = [BookLevel(price=float(a[0]), qty=float(a[1])) for a in d.get("asks", [])]
                book = OrderBook(
                    inst_id=inst_id,
                    bids=bids,
                    asks=asks,
                    ts=int(d.get("ts", 0)),
                )
                self._store.update_book(book)
            except (IndexError, ValueError):
                pass
