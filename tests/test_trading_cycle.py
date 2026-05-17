import os
import subprocess
import sys
from pathlib import Path

import pytest

from quant_agent.config import AppConfig, RiskConfig
from quant_agent.models import Bar, Signal
from quant_agent.trading_cycle import PaperTradingCycle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


class FakeStrategy:
    def __init__(self, targets):
        self.targets = targets

    def generate_signal(self, symbol, bars, existing_position):
        return Signal(symbol=symbol, target_allocation=self.targets.get(symbol, 0.0), reason=f"target {symbol}")


class FakeBroker:
    def __init__(self, positions=None, account=None):
        self.positions = positions or []
        self.account = account or {"equity": "10000", "buying_power": "10000", "status": "ACTIVE"}
        self.submitted = []

    def get_account(self):
        return self.account

    def list_positions(self):
        return self.positions

    def submit_order_if_no_duplicate(self, order):
        self.submitted.append(order)
        return {"id": f"{order.symbol}-paper", "status": "accepted"}


class FakeMarketData:
    def __init__(self):
        self.calls = []

    def fetch_bars(self, symbols, start, end, timeframe):
        self.calls.append({"symbols": symbols, "start": start, "end": end, "timeframe": timeframe})
        return {symbol: [_bar(100.0)] for symbol in symbols}


def test_paper_trading_cycle_builds_buy_plan_without_submitting():
    broker = FakeBroker()
    market_data = FakeMarketData()
    cycle = PaperTradingCycle(
        AppConfig(mode="paper", symbols=("SPY",)),
        broker,
        market_data,
        strategy=FakeStrategy({"SPY": 0.20}),
    )

    result = cycle.run("2025-01-01T14:30:00Z", "2025-01-01T15:30:00Z", timeframe="1Min")

    assert result.submitted is False
    assert result.actions[0].side == "buy"
    assert result.actions[0].qty == 20
    assert result.actions[0].status == "planned"
    assert broker.submitted == []
    assert market_data.calls[0]["timeframe"] == "1Min"


def test_paper_trading_cycle_submits_when_explicitly_requested():
    broker = FakeBroker()
    cycle = PaperTradingCycle(
        AppConfig(mode="paper", symbols=("SPY",)),
        broker,
        FakeMarketData(),
        strategy=FakeStrategy({"SPY": 0.20}),
    )

    result = cycle.run("2025-01-01", "2025-01-02", submit_orders=True)

    assert result.actions[0].status == "submitted"
    assert result.actions[0].broker_response == {"id": "SPY-paper", "status": "accepted"}
    assert broker.submitted[0].symbol == "SPY"


def test_paper_trading_cycle_builds_exit_order_from_current_position():
    positions = [{"symbol": "SPY", "qty": "7", "market_value": "700", "avg_entry_price": "90"}]
    cycle = PaperTradingCycle(
        AppConfig(mode="paper", symbols=("SPY",)),
        FakeBroker(positions),
        FakeMarketData(),
        strategy=FakeStrategy({"SPY": 0.0}),
    )

    result = cycle.run("2025-01-01", "2025-01-02")

    assert result.actions[0].side == "sell"
    assert result.actions[0].qty == 7
    assert result.actions[0].current_allocation == 0.07
    assert result.actions[0].target_allocation == 0.0


def test_paper_trading_cycle_skips_when_market_data_is_missing():
    class EmptyMarketData:
        def fetch_bars(self, symbols, start, end, timeframe):
            return {symbol: [] for symbol in symbols}

    cycle = PaperTradingCycle(
        AppConfig(mode="paper", symbols=("SPY",)),
        FakeBroker(),
        EmptyMarketData(),
        strategy=FakeStrategy({"SPY": 0.20}),
    )

    result = cycle.run("2025-01-01", "2025-01-02")

    assert result.actions[0].status == "skipped"
    assert result.actions[0].reason == "No market data returned"


def test_paper_trading_cycle_rejects_order_above_notional_limit():
    cycle = PaperTradingCycle(
        AppConfig(
            mode="paper",
            symbols=("SPY",),
            risk=RiskConfig(max_order_notional=1_000.0),
        ),
        FakeBroker(),
        FakeMarketData(),
        strategy=FakeStrategy({"SPY": 0.20}),
    )

    result = cycle.run("2025-01-01", "2025-01-02")

    assert result.actions[0].status == "skipped"
    assert result.actions[0].qty == 0
    assert "notional above limit" in result.actions[0].reason


def test_paper_trading_cycle_rejects_buy_above_available_buying_power():
    broker = FakeBroker(account={"equity": "10000", "buying_power": "500", "status": "ACTIVE"})
    cycle = PaperTradingCycle(
        AppConfig(mode="paper", symbols=("SPY",)),
        broker,
        FakeMarketData(),
        strategy=FakeStrategy({"SPY": 0.20}),
    )

    result = cycle.run("2025-01-01", "2025-01-02", submit_orders=True)

    assert result.actions[0].status == "skipped"
    assert "insufficient buying power" in result.actions[0].reason
    assert broker.submitted == []


def test_paper_trading_cycle_limits_order_count_per_cycle():
    cycle = PaperTradingCycle(
        AppConfig(
            mode="paper",
            symbols=("SPY", "QQQ"),
            risk=RiskConfig(max_orders_per_cycle=1),
        ),
        FakeBroker(),
        FakeMarketData(),
        strategy=FakeStrategy({"SPY": 0.20, "QQQ": 0.20}),
    )

    result = cycle.run("2025-01-01", "2025-01-02")

    assert result.actions[0].status == "planned"
    assert result.actions[1].status == "skipped"
    assert "max orders per cycle" in result.actions[1].reason


def test_cli_paper_cycle_fails_without_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr("quant_agent.broker._load_env_if_needed", lambda: None)
    monkeypatch.setattr("quant_agent.market_data._load_env_if_needed", lambda: None)

    from quant_agent.broker import PaperBrokerSettings
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        PaperBrokerSettings.from_environment()


def _bar(close):
    return Bar(date="2025-01-01", open=close, high=close, low=close, close=close, volume=1000)
