import os
import subprocess
import sys
from pathlib import Path

import pytest

from quant_agent.broker import PaperBrokerSettings
from quant_agent.market_clock import MarketClock, TradingPreflight, parse_clock
from quant_agent.market_data import AlpacaMarketDataClient, MarketDataSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


def test_market_data_settings_use_alpaca_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")

    settings = MarketDataSettings.from_environment()

    assert settings.api_key == "key"
    assert settings.secret_key == "secret"
    assert settings.base_url == "https://data.alpaca.markets"


def test_market_data_client_requests_daily_bars_and_parses_response():
    calls = []

    def fake_transport(request):
        calls.append(request)
        return {
            "bars": {
                "SPY": [
                    {"t": "2025-01-02T05:00:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 12345}
                ]
            }
        }

    client = AlpacaMarketDataClient(MarketDataSettings("key", "secret"), transport=fake_transport)

    bars = client.fetch_daily_bars(["SPY"], start="2025-01-01", end="2025-01-03")

    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == "https://data.alpaca.markets/v2/stocks/bars"
    assert calls[0]["headers"]["APCA-API-KEY-ID"] == "key"
    assert calls[0]["params"]["symbols"] == "SPY"
    assert calls[0]["params"]["timeframe"] == "1Day"
    assert calls[0]["params"]["feed"] == "iex"
    assert bars["SPY"][0].date == "2025-01-02"
    assert bars["SPY"][0].close == 101


def test_market_data_client_follows_next_page_token():
    tokens = []

    def fake_transport(request):
        tokens.append(request["params"].get("page_token"))
        if "page_token" not in request["params"]:
            return {"bars": {"SPY": []}, "next_page_token": "next"}
        return {
            "bars": {
                "SPY": [
                    {"t": "2025-01-03T05:00:00Z", "o": 101, "h": 103, "l": 100, "c": 102, "v": 10}
                ]
            }
        }

    client = AlpacaMarketDataClient(MarketDataSettings("key", "secret"), transport=fake_transport)

    bars = client.fetch_daily_bars(["SPY"], start="2025-01-01", end="2025-01-04")

    assert tokens == [None, "next"]
    assert bars["SPY"][0].date == "2025-01-03"


def test_parse_clock_maps_alpaca_payload():
    clock = parse_clock(
        {
            "timestamp": "2026-05-16T14:00:00Z",
            "is_open": True,
            "next_open": "2026-05-18T13:30:00Z",
            "next_close": "2026-05-16T20:00:00Z",
        }
    )

    assert clock.is_open is True
    assert clock.timestamp == "2026-05-16T14:00:00Z"


def test_preflight_blocks_orders_when_market_closed():
    preflight = TradingPreflight(clock_provider=lambda: MarketClock("now", False, "open", "close"))

    with pytest.raises(RuntimeError, match="market is closed"):
        preflight.assert_can_submit_order()


def test_preflight_allows_orders_when_market_open():
    preflight = TradingPreflight(clock_provider=lambda: MarketClock("now", True, "open", "close"))

    assert preflight.assert_can_submit_order().is_open is True


def test_cli_paper_clock_fails_without_credentials():
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_PATH
    env.pop("ALPACA_API_KEY", None)
    env.pop("ALPACA_SECRET_KEY", None)

    completed = subprocess.run(
        [sys.executable, "-m", "quant_agent", "paper-clock"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 2
    assert "ALPACA_API_KEY" in completed.stderr
