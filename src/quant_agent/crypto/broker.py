from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request


def _load_okx_env() -> None:
    if os.getenv("OKX_API_KEY"):
        return
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


@dataclass(frozen=True)
class OKXBrokerSettings:
    api_key: str
    secret_key: str
    passphrase: str
    base_url: str = "https://www.okx.com"
    demo: bool = True

    @classmethod
    def from_environment(cls) -> OKXBrokerSettings:
        _load_okx_env()
        api_key = os.getenv("OKX_API_KEY")
        secret_key = os.getenv("OKX_SECRET_KEY")
        passphrase = os.getenv("OKX_PASSPHRASE")
        if not api_key or not secret_key or not passphrase:
            raise RuntimeError(
                "OKX trading requires OKX_API_KEY, OKX_SECRET_KEY, and OKX_PASSPHRASE "
                "environment variables. Get demo keys from OKX > Trade > Demo Trading > API."
            )
        return cls(api_key=api_key, secret_key=secret_key, passphrase=passphrase)


class OKXBroker:
    """OKX REST API broker for demo/paper trading (spot).

    Mirrors AlpacaPaperBroker interface where possible.
    """

    def __init__(self, settings: OKXBrokerSettings) -> None:
        self.settings = settings

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        sign_string = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.settings.secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        sign = self._sign(timestamp, method, path, body)
        headers = {
            "OK-ACCESS-KEY": self.settings.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.settings.passphrase,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        if self.settings.demo:
            headers["x-simulated-trading"] = "1"
        return headers

    def _request(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        body_str = json.dumps(body) if body else ""
        url = f"{self.settings.base_url}{path}"
        headers = self._headers(method, path, body_str)
        data = body_str.encode("utf-8") if body_str else None
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        with request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("code") != "0":
            raise RuntimeError(f"OKX API error: {result.get('msg', '')} (code={result.get('code')})")
        return result

    # --- Account ---

    def get_account(self) -> dict[str, Any]:
        """Get account balance. Returns dict with 'equity', 'details' etc."""
        result = self._request("GET", "/api/v5/account/balance")
        data = result["data"][0] if result.get("data") else {}
        return data

    def get_usdt_balance(self) -> dict[str, float]:
        """Get USDT available and total balance."""
        acct = self.get_account()
        for detail in acct.get("details", []):
            if detail.get("ccy") == "USDT":
                return {
                    "available": float(detail.get("availBal", 0)),
                    "equity": float(detail.get("eq", 0)),
                    "frozen": float(detail.get("frozenBal", 0)),
                }
        return {"available": 0.0, "equity": 0.0, "frozen": 0.0}

    # --- Positions ---

    def list_positions(self) -> list[dict[str, Any]]:
        """List spot holdings (non-zero balances excluding USDT).

        Returns list of dicts compatible with Alpaca format:
        {'symbol', 'qty', 'avg_entry_price', 'market_value', 'unrealized_pl'}
        """
        acct = self.get_account()
        positions = []
        for detail in acct.get("details", []):
            ccy = detail.get("ccy", "")
            eq = float(detail.get("eq", 0))
            if ccy == "USDT" or eq <= 0:
                continue
            frozen = float(detail.get("frozenBal", 0))
            avail = float(detail.get("availBal", 0))
            cash = float(detail.get("cashBal", 0))
            eq_usd = float(detail.get("eqUsd", 0))
            # avg entry price approximation: cash balance / quantity
            avg_px = cash / eq if eq > 0 else 0
            positions.append({
                "symbol": f"{ccy}-USDT",
                "qty": str(eq),
                "available": str(avail),
                "frozen": str(frozen),
                "avg_entry_price": str(avg_px),
                "market_value": str(eq_usd),
                "unrealized_pl": "0",  # OKX spot balance doesn't provide PnL directly
            })
        return positions

    # --- Orders ---

    def list_open_orders(self) -> list[dict[str, Any]]:
        """List pending orders."""
        result = self._request("GET", "/api/v5/trade/orders-pending?instType=SPOT")
        orders = []
        for o in result.get("data", []):
            orders.append({
                "order_id": o.get("ordId", ""),
                "symbol": o.get("instId", ""),
                "side": o.get("side", ""),
                "order_type": o.get("ordType", ""),
                "qty": o.get("sz", ""),
                "price": o.get("px", ""),
                "status": o.get("state", ""),
                "created_at": o.get("cTime", ""),
            })
        return orders

    def submit_order(
        self,
        symbol: str,
        side: str,
        qty: str,
        order_type: str = "market",
        price: str | None = None,
    ) -> dict[str, Any]:
        """Place a spot order.

        Args:
            symbol: e.g. "BTC-USDT"
            side: "buy" or "sell"
            qty: order size in base currency (e.g. "0.001" BTC)
            order_type: "market" or "limit"
            price: required for limit orders
        """
        body: dict[str, Any] = {
            "instId": symbol,
            "tdMode": "cash",
            "side": side,
            "ordType": order_type,
            "sz": qty,
        }
        if order_type == "limit" and price:
            body["px"] = price
        result = self._request("POST", "/api/v5/trade/order", body)
        data = result["data"][0] if result.get("data") else {}
        return {
            "order_id": data.get("ordId", ""),
            "status": "submitted" if data.get("sCode") == "0" else "rejected",
            "message": data.get("sMsg", ""),
        }

    def cancel_order(self, inst_id: str, ord_id: str) -> dict[str, Any]:
        """Cancel a pending order."""
        body = {"instId": inst_id, "ordId": ord_id}
        result = self._request("POST", "/api/v5/trade/cancel-order", body)
        data = result["data"][0] if result.get("data") else {}
        return {
            "order_id": data.get("ordId", ""),
            "status": "cancelled" if data.get("sCode") == "0" else "error",
            "message": data.get("sMsg", ""),
        }
