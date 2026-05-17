from __future__ import annotations

from quant_agent.crypto.base import CryptoAdapter

# Bybit WebSocket public endpoints (for future implementation):
#   Mainnet: wss://stream.bybit.com/v5/public/spot
#   Testnet: wss://stream-testnet.bybit.com/v5/public/spot
#
# Channels (v5):
#   tickers   — real-time ticker: {symbol, lastPrice, bid1Price, ask1Price, volume24h, highPrice24h, lowPrice24h}
#   publicTrade — recent trades: {symbol, price, size, side, time}
#   kline.{interval} — candles: {start, open, high, low, close, volume, confirm}
#     intervals: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
#   orderbook.{depth} — order book: {b: [[price, qty]], a: [[price, qty]], seq, ts}
#     depths: 1, 25, 50, 200, 500
#
# Subscribe message format:
#   {"op": "subscribe", "args": ["tickers.BTCUSDT", "publicTrade.BTCUSDT"]}


class BybitAdapter(CryptoAdapter):
    """Bybit WebSocket v5 adapter — placeholder for future implementation.

    Intended to support:
    - tickers: real-time price data
    - publicTrade: trade feed
    - kline.1: 1-second candles
    - orderbook.5: top-5 order book
    """

    def start(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        raise NotImplementedError("Bybit adapter not yet implemented")

    def stop(self) -> None:
        raise NotImplementedError("Bybit adapter not yet implemented")

    def subscribe(self, inst_ids: list[str], channels: list[str] | None = None) -> None:
        raise NotImplementedError("Bybit adapter not yet implemented")

    def unsubscribe(self, inst_ids: list[str]) -> None:
        raise NotImplementedError("Bybit adapter not yet implemented")
