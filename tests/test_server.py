from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from quant_agent.server import create_app
from quant_agent.models import Bar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


# -- Fakes (same pattern as test_trading_sync.py) --


class FakeBroker:
    def __init__(self) -> None:
        self._account = {"status": "ACTIVE", "equity": "100000", "buying_power": "100000", "cash": "100000", "portfolio_value": "100000"}
        self._positions: list[dict[str, Any]] = []
        self._orders: list[dict[str, Any]] = []

    def get_account(self) -> dict[str, Any]:
        return self._account

    def list_positions(self) -> list[dict[str, Any]]:
        return self._positions

    def list_open_orders(self) -> list[dict[str, Any]]:
        return self._orders


class FakeMarketData:
    def __init__(self, bars: dict[str, list[Bar]] | None = None) -> None:
        self._bars = bars or {}

    def fetch_bars(self, symbols: list[str], start: str, end: str, timeframe: str = "1Day") -> dict[str, list[Bar]]:
        return {s: self._bars.get(s, []) for s in symbols}


def _make_bars(symbol: str, count: int = 30, base_price: float = 100.0) -> list[Bar]:
    bars = []
    for i in range(count):
        price = base_price + i * 0.5
        bars.append(Bar(date=f"2025-01-{i+1:02d}", open=price, high=price + 1, low=price - 1, close=price + 0.25, volume=1000000))
    return bars


# -- Tests --


def test_dashboard_html_is_served_at_root():
    app = create_app(broker_factory=FakeBroker, market_data_factory=FakeMarketData)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"quant" in resp.data.lower()


def test_get_backtest_returns_200_with_metrics():
    app = create_app(broker_factory=FakeBroker, market_data_factory=FakeMarketData)
    client = app.test_client()
    resp = client.get("/api/backtest")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "metrics" in data
    assert "equity_curve" in data
    assert "trades" in data
    assert isinstance(data["metrics"]["total_return"], float)
    assert len(data["equity_curve"]) > 0


def test_get_optimize_returns_200_with_candidates():
    app = create_app(broker_factory=FakeBroker, market_data_factory=FakeMarketData)
    client = app.test_client()
    resp = client.get("/api/optimize")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "best" in data
    assert "candidates" in data
    assert len(data["candidates"]) > 0


def test_post_paper_cycle_returns_plan_without_submitting():
    bars = {s: _make_bars(s) for s in ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")}
    fake_broker = FakeBroker()
    fake_market_data = FakeMarketData(bars)

    app = create_app(
        broker_factory=lambda: fake_broker,
        market_data_factory=lambda: fake_market_data,
    )
    client = app.test_client()
    resp = client.post("/api/paper-cycle", json={"start": "2025-01-01", "end": "2025-01-30", "timeframe": "1Day"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["submitted"] is False
    assert "actions" in data
    assert len(data["actions"]) > 0


def test_post_paper_cycle_returns_400_without_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr("quant_agent.broker._load_env_if_needed", lambda: None)
    app = create_app()
    client = app.test_client()
    resp = client.post("/api/paper-cycle", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "ALPACA_API_KEY" in data["error"]


def test_get_account_returns_200():
    app = create_app(broker_factory=FakeBroker)
    client = app.test_client()
    resp = client.get("/api/account")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["equity"] == "100000"


def test_get_account_returns_400_without_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr("quant_agent.broker._load_env_if_needed", lambda: None)
    app = create_app()
    client = app.test_client()
    resp = client.get("/api/account")
    assert resp.status_code == 400
    assert "ALPACA_API_KEY" in resp.get_json()["error"]


def test_get_positions_returns_list():
    broker = FakeBroker()
    broker._positions = [{"symbol": "SPY", "qty": "10", "avg_entry_price": "500", "market_value": "5000", "unrealized_pl": "100"}]
    app = create_app(broker_factory=lambda: broker)
    client = app.test_client()
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "SPY"


def test_get_orders_returns_list():
    broker = FakeBroker()
    broker._orders = [{"symbol": "SPY", "side": "buy", "qty": "5", "type": "market", "status": "new", "submitted_at": "2025-01-15"}]
    app = create_app(broker_factory=lambda: broker)
    client = app.test_client()
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "SPY"


def test_serve_command_requires_flask(monkeypatch):
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_PATH
    completed = subprocess.run(
        [sys.executable, "-c", "import quant_agent.server"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    # Flask is installed in the test env, so this should succeed
    # This test just verifies the import path works
    assert completed.returncode == 0
