import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

from quant_agent.config import AppConfig, RiskConfig, StrategyConfig
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


def test_optimize_skips_invalid_candidates():
    config = AppConfig(symbols=("SPY",), risk=RiskConfig(max_symbol_allocation=0.5))
    bars = {"SPY": make_bars([10, 10, 11, 12, 13, 14, 15, 16])}
    invalid = OptimizationCandidate(short_window=5, long_window=3, rsi_entry_ceiling=70.0, target_allocation=0.2)
    valid = OptimizationCandidate(short_window=2, long_window=3, rsi_entry_ceiling=101.0, target_allocation=0.2)

    result = optimize_strategy(config, bars, candidates=[invalid, valid], train_ratio=0.75)

    assert [candidate.candidate for candidate in result.candidates] == [valid]
    assert result.best.candidate == valid


def test_optimize_selects_by_training_score_not_test_score():
    config = AppConfig(symbols=("SPY",), risk=RiskConfig(max_symbol_allocation=0.6))
    bars = {"SPY": make_bars([10] * 5 + list(range(11, 36)) + list(range(35, 25, -1)))}
    low_allocation = OptimizationCandidate(short_window=2, long_window=3, rsi_entry_ceiling=101.0, target_allocation=0.1)
    high_allocation = OptimizationCandidate(short_window=2, long_window=3, rsi_entry_ceiling=101.0, target_allocation=0.5)

    result = optimize_strategy(config, bars, candidates=[low_allocation, high_allocation], train_ratio=0.7)

    assert result.best.candidate == high_allocation
    assert result.best.train_metrics.total_return >= result.candidates[0].train_metrics.total_return
    assert result.best.test_metrics is not None


def test_optimize_rejects_candidate_above_risk_limit():
    config = AppConfig(symbols=("SPY",), risk=RiskConfig(max_symbol_allocation=0.2))
    bars = {"SPY": make_bars([10, 10, 11, 12, 13, 14, 15, 16])}
    too_large = OptimizationCandidate(short_window=2, long_window=3, rsi_entry_ceiling=101.0, target_allocation=0.5)

    result = optimize_strategy(config, bars, candidates=[too_large], train_ratio=0.75)

    assert result.candidates == []
    assert result.best is None


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
    assert results["best"]["candidate"]["short_window"] < results["best"]["candidate"]["long_window"]


def test_default_sample_optimization_has_holdout_exposure():
    config = AppConfig()

    result = optimize_strategy(config, load_sample_bars(config.symbols))

    assert result.best is not None
    assert result.best.test_metrics.exposure > 0
