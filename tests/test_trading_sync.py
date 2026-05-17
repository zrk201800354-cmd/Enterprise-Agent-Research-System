import os
import pytest
import subprocess
import sys
from pathlib import Path

from quant_agent import broker as broker_module
from quant_agent.broker import (
    AlpacaPaperBroker,
    BrokerOrder,
    DuplicateOrderError,
    PaperBrokerSettings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


def test_paper_broker_fetches_account_positions_and_open_orders():
    calls = []

    def fake_transport(request):
        calls.append(request)
        if request["url"].endswith("/v2/account"):
            return {"status": "ACTIVE", "buying_power": "100000", "equity": "100000"}
        if request["url"].endswith("/v2/positions"):
            return [{"symbol": "SPY", "qty": "2", "market_value": "1000"}]
        if request["url"].endswith("/v2/orders"):
            return [{"symbol": "SPY", "side": "buy", "status": "new", "qty": "1"}]
        raise AssertionError(f"Unexpected URL {request['url']}")

    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"), transport=fake_transport)

    assert broker.get_account()["status"] == "ACTIVE"
    assert broker.list_positions()[0]["symbol"] == "SPY"
    assert broker.list_open_orders()[0]["status"] == "new"
    assert calls[2]["params"]["status"] == "open"


def test_default_broker_transport_supports_get_params_without_body(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'[{"symbol":"SPY","side":"buy","status":"new"}]'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(broker_module.request, "urlopen", fake_urlopen)
    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"))

    orders = broker.list_open_orders()

    assert orders[0]["symbol"] == "SPY"
    assert captured["method"] == "GET"
    assert captured["body"] is None
    assert captured["url"] == "https://paper-api.alpaca.markets/v2/orders?status=open"


def test_duplicate_order_guard_blocks_same_symbol_side_open_order():
    def fake_transport(request):
        if request["method"] == "GET" and request["url"].endswith("/v2/orders"):
            return [{"symbol": "SPY", "side": "buy", "status": "new", "qty": "1"}]
        if request["method"] == "POST":
            raise AssertionError("submit should not be called when duplicate order exists")
        return {}

    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"), transport=fake_transport)

    with pytest.raises(DuplicateOrderError, match="duplicate open order"):
        broker.submit_order_if_no_duplicate(BrokerOrder("SPY", 1, "buy"))


def test_duplicate_order_guard_allows_different_side_or_symbol():
    calls = []

    def fake_transport(request):
        calls.append(request)
        if request["method"] == "GET" and request["url"].endswith("/v2/orders"):
            return [{"symbol": "QQQ", "side": "buy", "status": "new", "qty": "1"}]
        if request["method"] == "POST":
            return {"id": "ok", "status": "accepted"}
        return {}

    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"), transport=fake_transport)

    assert broker.submit_order_if_no_duplicate(BrokerOrder("SPY", 1, "buy"))["status"] == "accepted"
    assert [call["method"] for call in calls] == ["GET", "POST"]


def test_cli_paper_submit_fails_without_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr("quant_agent.broker._load_env_if_needed", lambda: None)
    monkeypatch.setattr("quant_agent.market_data._load_env_if_needed", lambda: None)

    from quant_agent.broker import PaperBrokerSettings
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        PaperBrokerSettings.from_environment()
