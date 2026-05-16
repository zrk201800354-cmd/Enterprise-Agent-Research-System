import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from quant_agent.backtest import BacktestResult
from quant_agent.broker import (
    AlpacaPaperBroker,
    BrokerOrder,
    PaperBrokerSettings,
    reject_live_mode,
)
from quant_agent.journal import write_backtest_summary
from quant_agent.models import BacktestMetrics
from quant_agent.sample_data import load_sample_bars


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


def test_sample_data_contains_default_symbols_with_enough_bars():
    data = load_sample_bars(["SPY", "QQQ"])

    assert set(data) == {"SPY", "QQQ"}
    assert len(data["SPY"]) >= 60
    assert len(data["SPY"]) == len(data["QQQ"])
    assert [bar.date for bar in data["SPY"]] == [bar.date for bar in data["QQQ"]]
    assert data["SPY"][0].close > 0


def test_journal_writes_markdown_summary_and_json_metrics(tmp_path):
    result = BacktestResult(
        initial_cash=1000.0,
        final_equity=1100.0,
        trades=[],
        equity_curve=[1000.0, 1100.0],
        metrics=BacktestMetrics(
            total_return=0.10,
            annualized_return=0.20,
            max_drawdown=-0.05,
            win_rate=0.0,
            trade_count=0,
            exposure=0.5,
        ),
    )

    summary_path, metrics_path = write_backtest_summary(result, output_dir=tmp_path)

    assert summary_path.read_text(encoding="utf-8").startswith("# Backtest Summary")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["total_return"] == 0.10


def test_paper_broker_settings_require_env_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        PaperBrokerSettings.from_environment()


def test_paper_broker_settings_read_env_keys(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")

    settings = PaperBrokerSettings.from_environment()

    assert settings.api_key == "key"
    assert settings.secret_key == "secret"
    assert settings.base_url == "https://paper-api.alpaca.markets"


def test_broker_order_rejects_unsafe_values():
    with pytest.raises(ValueError, match="symbol"):
        BrokerOrder(symbol="", qty=1, side="buy")
    with pytest.raises(ValueError, match="qty"):
        BrokerOrder(symbol="SPY", qty=0, side="buy")
    with pytest.raises(ValueError, match="side"):
        BrokerOrder(symbol="SPY", qty=1, side="short")


def test_broker_order_payload_uses_alpaca_market_day_shape():
    order = BrokerOrder(symbol="SPY", qty=2, side="buy")

    assert order.to_payload() == {
        "symbol": "SPY",
        "qty": "2",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
    }


def test_alpaca_paper_broker_preview_does_not_call_transport():
    calls = []
    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"), transport=lambda request: calls.append(request))

    preview = broker.preview_order(BrokerOrder(symbol="SPY", qty=1, side="buy"))

    assert preview["endpoint"] == "https://paper-api.alpaca.markets/v2/orders"
    assert preview["payload"]["symbol"] == "SPY"
    assert calls == []


def test_alpaca_paper_broker_submit_order_posts_expected_request():
    calls = []

    def fake_transport(request):
        calls.append(request)
        return {"id": "paper-order-1", "status": "accepted"}

    broker = AlpacaPaperBroker(PaperBrokerSettings("key", "secret"), transport=fake_transport)

    response = broker.submit_order(BrokerOrder(symbol="SPY", qty=1, side="buy"))

    assert response == {"id": "paper-order-1", "status": "accepted"}
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://paper-api.alpaca.markets/v2/orders"
    assert calls[0]["headers"]["APCA-API-KEY-ID"] == "key"
    assert calls[0]["headers"]["APCA-API-SECRET-KEY"] == "secret"
    assert calls[0]["json"]["time_in_force"] == "day"


def test_live_mode_is_explicitly_rejected():
    with pytest.raises(RuntimeError, match="Live trading is not implemented"):
        reject_live_mode()


def test_cli_backtest_runs_without_network(tmp_path):
    env = os.environ.copy()
    env["QUANT_AGENT_LOG_DIR"] = str(tmp_path)
    env["PYTHONPATH"] = SRC_PATH

    completed = subprocess.run(
        [sys.executable, "-m", "quant_agent", "backtest"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Backtest complete" in completed.stdout
    assert (tmp_path / "backtest-summary.md").exists()
    assert (tmp_path / "backtest-metrics.json").exists()


def test_cli_paper_fails_without_credentials():
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_PATH

    completed = subprocess.run(
        [sys.executable, "-m", "quant_agent", "paper"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 2
    assert "ALPACA_API_KEY" in completed.stderr


def test_cli_paper_preview_builds_order_without_credentials():
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_PATH

    completed = subprocess.run(
        [sys.executable, "-m", "quant_agent", "paper-preview", "--symbol", "SPY", "--qty", "1", "--side", "buy"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Paper order preview" in completed.stdout
    assert '"symbol": "SPY"' in completed.stdout
