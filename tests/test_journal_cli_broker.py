import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from quant_agent.backtest import BacktestResult
from quant_agent.broker import PaperBrokerSettings, reject_live_mode
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
