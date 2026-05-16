from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib import parse, request

from quant_agent.models import Bar


MarketDataTransport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MarketDataSettings:
    api_key: str
    secret_key: str
    base_url: str = "https://data.alpaca.markets"

    @classmethod
    def from_environment(cls) -> "MarketDataSettings":
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("Market data requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        return cls(api_key=api_key, secret_key=secret_key)


class AlpacaMarketDataClient:
    def __init__(self, settings: MarketDataSettings, transport: MarketDataTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport or _urllib_get_json

    def fetch_daily_bars(
        self,
        symbols: list[str] | tuple[str, ...],
        start: str,
        end: str,
        feed: str = "iex",
    ) -> dict[str, list[Bar]]:
        if not symbols:
            raise ValueError("symbols are required")
        bars_by_symbol = {symbol: [] for symbol in symbols}
        params = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
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
