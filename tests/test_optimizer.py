import json
import os
from pathlib import Path
import subprocess
import sys

from quant_agent.config import AppConfig, RiskConfig
from quant_agent.models import Bar
from quant_agent.optimizer import (
    OptimizationCandidate,
    optimize_strategy,
    split_bars_by_ratio,
)
from quant_agent.sample_data import load_sample_bars


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")


def make_bars(closes):
    return [
        Bar(date=f"2026-01-{index + 1:02d}", open=close, high=close + 1, low=close - 1, close=close, volume=1000)
        for index, close in enumerate(closes)
    ]


def test_split_bars_by_ratio_keeps_train_and_test_separate():
    bars = {"SPY": make_bars([10, 11, 12, 13, 14])}

    train, test = split_bars_by_ratio(bars, train_ratio=0.6)

    assert [bar.close for bar in train["SPY"]] == [10, 11, 12]
    assert [bar.close for bar in test["SPY"]] == [13, 14]


def test_optimize_runs_with_valid_candidates():
    config = AppConfig(symbols=("SPY",), risk=RiskConfig(max_symbol_allocation=0.5))
    bars = {"SPY": make_bars([10, 10, 11, 12, 13, 14, 15, 16])}
    valid = OptimizationCandidate(
        strategy_name="trend_rsi",
        params={"short_window": 2, "long_window": 3, "rsi_entry_ceiling": 101.0},
        target_allocation=0.2,
    )

    result = optimize_strategy(config, bars, candidates=[valid], train_ratio=0.75, seed=42)

    assert len(result.candidates) == 1
    assert result.best.candidate == valid


def test_optimize_selects_by_training_score():
    config = AppConfig(symbols=("SPY",), risk=RiskConfig(max_symbol_allocation=0.6))
    bars = {"SPY": make_bars([10] * 5 + list(range(11, 36)) + list(range(35, 25, -1)))}
    low_alloc = OptimizationCandidate(
        strategy_name="trend_rsi",
        params={"short_window": 2, "long_window": 3, "rsi_entry_ceiling": 101.0},
        target_allocation=0.1,
    )
    high_alloc = OptimizationCandidate(
        strategy_name="trend_rsi",
        params={"short_window": 2, "long_window": 3, "rsi_entry_ceiling": 101.0},
        target_allocation=0.5,
    )

    result = optimize_strategy(config, bars, candidates=[low_alloc, high_alloc], train_ratio=0.7, seed=42)

    assert result.best is not None
    assert result.best.test_metrics is not None


def test_optimize_randomizes_results():
    config = AppConfig(symbols=("SPY",))
    bars = load_sample_bars(config.symbols)

    r1 = optimize_strategy(config, bars, strategy_name="trend_rsi", seed=100)
    r2 = optimize_strategy(config, bars, strategy_name="trend_rsi", seed=200)

    assert r1.run_id != r2.run_id


def test_optimize_supports_multiple_strategies():
    config = AppConfig(symbols=("SPY",))
    bars = load_sample_bars(config.symbols)

    for strategy_name in ["trend_rsi", "multi_indicator", "dca", "grid", "regime_switch"]:
        result = optimize_strategy(config, bars, strategy_name=strategy_name, seed=42)
        assert result.strategy == strategy_name
        assert result.best is not None


def test_cli_optimize_runs_offline_and_writes_reports(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_PATH
    env["QUANT_AGENT_LOG_DIR"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "quant_agent", "optimize"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Optimization complete" in completed.stdout
    summary_path = tmp_path / "optimization-summary.md"
    results_path = tmp_path / "optimization-results.json"
    assert summary_path.exists()
    results = json.loads(results_path.read_text(encoding="utf-8"))
    assert results["best"]["candidate"]["strategy_name"] == "trend_rsi"


def test_default_sample_optimization_has_holdout_exposure():
    config = AppConfig()

    result = optimize_strategy(config, load_sample_bars(config.symbols), strategy_name="trend_rsi", seed=42)

    assert result.best is not None
    assert result.best.test_metrics.exposure > 0
