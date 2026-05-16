from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib import request

from quant_agent.broker import PaperBrokerSettings


ClockTransport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MarketClock:
    timestamp: str
    is_open: bool
    next_open: str
    next_close: str


class AlpacaClockClient:
    def __init__(self, settings: PaperBrokerSettings, transport: ClockTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport or _urllib_get_json

    def get_clock(self) -> MarketClock:
        return parse_clock(
            self.transport(
                {
                    "method": "GET",
                    "url": f"{self.settings.base_url}/v2/clock",
                    "headers": {
                        "APCA-API-KEY-ID": self.settings.api_key,
                        "APCA-API-SECRET-KEY": self.settings.secret_key,
                        "Accept": "application/json",
                    },
                }
            )
        )


class TradingPreflight:
    def __init__(self, clock_provider: Callable[[], MarketClock]) -> None:
        self.clock_provider = clock_provider

    def assert_can_submit_order(self) -> MarketClock:
        clock = self.clock_provider()
        if not clock.is_open:
            raise RuntimeError(f"Regular market is closed. Next open: {clock.next_open}")
        return clock


def parse_clock(payload: dict[str, Any]) -> MarketClock:
    return MarketClock(
        timestamp=str(payload["timestamp"]),
        is_open=bool(payload["is_open"]),
        next_open=str(payload["next_open"]),
        next_close=str(payload["next_close"]),
    )


def _urllib_get_json(request_data: dict[str, Any]) -> dict[str, Any]:
    req = request.Request(request_data["url"], headers=request_data["headers"], method=request_data["method"])
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
