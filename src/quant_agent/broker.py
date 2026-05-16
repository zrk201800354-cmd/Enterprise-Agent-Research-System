from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib import parse, request


@dataclass(frozen=True)
class PaperBrokerSettings:
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"

    @classmethod
    def from_environment(cls) -> "PaperBrokerSettings":
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError(
                "Paper trading requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables"
            )
        return cls(api_key=api_key, secret_key=secret_key)


@dataclass(frozen=True)
class BrokerOrder:
    symbol: str
    qty: float
    side: str
    order_type: str = "market"
    time_in_force: str = "day"

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("order symbol is required")
        if self.qty <= 0:
            raise ValueError("order qty must be positive")
        if self.side not in {"buy", "sell"}:
            raise ValueError("order side must be buy or sell")
        if self.order_type != "market":
            raise ValueError("only market orders are supported in this milestone")
        if self.time_in_force != "day":
            raise ValueError("only day time_in_force is supported in this milestone")

    def to_payload(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "qty": _format_quantity(self.qty),
            "side": self.side,
            "type": self.order_type,
            "time_in_force": self.time_in_force,
        }


Transport = Callable[[dict[str, Any]], dict[str, Any] | list[dict[str, Any]]]


class DuplicateOrderError(RuntimeError):
    pass


class AlpacaPaperBroker:
    def __init__(self, settings: PaperBrokerSettings, transport: Transport | None = None) -> None:
        self.settings = settings
        self.transport = transport or _urllib_transport

    @property
    def orders_url(self) -> str:
        return f"{self.settings.base_url}/v2/orders"

    def preview_order(self, order: BrokerOrder) -> dict[str, Any]:
        return {
            "endpoint": self.orders_url,
            "payload": order.to_payload(),
            "paper": True,
        }

    def submit_order(self, order: BrokerOrder) -> dict[str, Any]:
        return self.transport(
            {
                "method": "POST",
                "url": self.orders_url,
                "headers": self._headers(),
                "json": order.to_payload(),
            }
        )

    def submit_order_if_no_duplicate(self, order: BrokerOrder) -> dict[str, Any]:
        for open_order in self.list_open_orders():
            if _same_order_intent(open_order, order):
                raise DuplicateOrderError(f"Blocked duplicate open order for {order.symbol} {order.side}")
        return self.submit_order(order)

    def get_account(self) -> dict[str, Any]:
        return self.transport(
            {
                "method": "GET",
                "url": f"{self.settings.base_url}/v2/account",
                "headers": self._headers(),
            }
        )

    def list_positions(self) -> list[dict[str, Any]]:
        response = self.transport(
            {
                "method": "GET",
                "url": f"{self.settings.base_url}/v2/positions",
                "headers": self._headers(),
            }
        )
        if not isinstance(response, list):
            raise RuntimeError("Positions response must be a list")
        return response

    def list_open_orders(self) -> list[dict[str, Any]]:
        response = self.transport(
            {
                "method": "GET",
                "url": self.orders_url,
                "headers": self._headers(),
                "params": {"status": "open"},
            }
        )
        if not isinstance(response, list):
            raise RuntimeError("Orders response must be a list")
        return response

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.settings.api_key,
            "APCA-API-SECRET-KEY": self.settings.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


def reject_live_mode() -> None:
    raise RuntimeError("Live trading is not implemented in this first version")


def _format_quantity(qty: float) -> str:
    if float(qty).is_integer():
        return str(int(qty))
    return str(qty)


def _same_order_intent(open_order: dict[str, Any], order: BrokerOrder) -> bool:
    return (
        str(open_order.get("symbol", "")).upper() == order.symbol.upper()
        and str(open_order.get("side", "")).lower() == order.side
        and str(open_order.get("status", "")).lower() in {"new", "accepted", "pending_new", "partially_filled"}
    )


def _urllib_transport(request_data: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    url = request_data["url"]
    params = request_data.get("params") or {}
    if params:
        url = f"{url}?{parse.urlencode(params)}"
    body = None
    if "json" in request_data:
        body = json.dumps(request_data["json"]).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers=request_data["headers"],
        method=request_data["method"],
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
