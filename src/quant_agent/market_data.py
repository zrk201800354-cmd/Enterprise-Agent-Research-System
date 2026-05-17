from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib import parse, request

from quant_agent.broker import _load_env_if_needed
from quant_agent.models import Bar


MarketDataTransport = Callable[[dict[str, Any]], dict[str, Any]]
SUPPORTED_TIMEFRAMES = {"1Min", "5Min", "15Min", "30Min", "1Hour", "1Day"}


@dataclass(frozen=True)
class MarketDataSettings:
    api_key: str
    secret_key: str
    base_url: str = "https://data.alpaca.markets"

    @classmethod
    def from_environment(cls) -> "MarketDataSettings":
        _load_env_if_needed()
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("Market data requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        return cls(api_key=api_key, secret_key=secret_key)


SCREEN_BATCH_SIZE = 200


class AlpacaMarketDataClient:
    def __init__(self, settings: MarketDataSettings, transport: MarketDataTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport or _urllib_get_json

    def list_tradable_symbols(self, exchanges: tuple[str, ...] | None = None) -> list[str]:
        broker_url = "https://paper-api.alpaca.markets"
        all_assets: list[dict[str, Any]] = []
        params: dict[str, Any] = {"status": "active", "asset_class": "us_equity"}
        while True:
            response = self.transport(
                {
                    "method": "GET",
                    "url": f"{broker_url}/v2/assets",
                    "headers": self._headers(),
                    "params": dict(params),
                }
            )
            if not isinstance(response, list):
                break
            all_assets.extend(response)
            if len(response) < 100:
                break
            params["offset"] = len(all_assets)

        symbols = sorted(
            a["symbol"]
            for a in all_assets
            if a.get("tradable")
            and not a["symbol"].endswith("/USD")
            and "/" not in a["symbol"]
            and len(a["symbol"]) <= 5
        )
        return symbols

    def fetch_bars_for_symbols(
        self,
        symbols: list[str],
        start: str,
        end: str,
        timeframe: str = "1Day",
        feed: str = "iex",
    ) -> dict[str, list[Bar]]:
        bars_by_symbol: dict[str, list[Bar]] = {}
        for i in range(0, len(symbols), SCREEN_BATCH_SIZE):
            batch = symbols[i : i + SCREEN_BATCH_SIZE]
            try:
                batch_bars = self.fetch_bars(batch, start=start, end=end, timeframe=timeframe, feed=feed)
                bars_by_symbol.update(batch_bars)
            except Exception:
                continue
        return bars_by_symbol

    def fetch_daily_bars(
        self,
        symbols: list[str] | tuple[str, ...],
        start: str,
        end: str,
        feed: str = "iex",
    ) -> dict[str, list[Bar]]:
        return self.fetch_bars(symbols=symbols, start=start, end=end, timeframe="1Day", feed=feed)

    def fetch_bars(
        self,
        symbols: list[str] | tuple[str, ...],
        start: str,
        end: str,
        timeframe: str = "1Day",
        feed: str = "iex",
    ) -> dict[str, list[Bar]]:
        if not symbols:
            raise ValueError("symbols are required")
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        bars_by_symbol = {symbol: [] for symbol in symbols}
        params = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "feed": feed,
        }

        while True:
            response = self.transport(
                {
                    "method": "GET",
                    "url": f"{self.settings.base_url}/v2/stocks/bars",
                    "headers": self._headers(),
                    "params": dict(params),
                }
            )
            for symbol, raw_bars in response.get("bars", {}).items():
                bars_by_symbol.setdefault(symbol, [])
                bars_by_symbol[symbol].extend(_parse_bar(raw_bar) for raw_bar in raw_bars)

            next_page_token = response.get("next_page_token")
            if not next_page_token:
                break
            params["page_token"] = next_page_token

        return bars_by_symbol

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.settings.api_key,
            "APCA-API-SECRET-KEY": self.settings.secret_key,
            "Accept": "application/json",
        }


def _parse_bar(raw: dict[str, Any]) -> Bar:
    return Bar(
        date=str(raw["t"])[:10],
        open=float(raw["o"]),
        high=float(raw["h"]),
        low=float(raw["l"]),
        close=float(raw["c"]),
        volume=int(raw["v"]),
    )


def _urllib_get_json(request_data: dict[str, Any]) -> dict[str, Any]:
    url = request_data["url"]
    params = request_data.get("params") or {}
    if params:
        url = f"{url}?{parse.urlencode(params)}"
    req = request.Request(url, headers=request_data["headers"], method=request_data["method"])
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
