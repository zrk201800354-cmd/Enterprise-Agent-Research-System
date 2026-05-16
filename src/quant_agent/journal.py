from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from quant_agent.backtest import BacktestResult
from quant_agent.optimizer import OptimizationResult, optimization_to_dict


def write_backtest_summary(
    result: BacktestResult, output_dir: str | os.PathLike[str] = "logs"
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / "backtest-summary.md"
    metrics_path = directory / "backtest-metrics.json"

    summary = "\n".join(
        [
            "# Backtest Summary",
            "",
            f"- Initial cash: {result.initial_cash:.2f}",
            f"- Final equity: {result.final_equity:.2f}",
            f"- Total return: {result.metrics.total_return:.4f}",
            f"- Annualized return: {result.metrics.annualized_return:.4f}",
            f"- Max drawdown: {result.metrics.max_drawdown:.4f}",
            f"- Win rate: {result.metrics.win_rate:.4f}",
            f"- Trades: {result.metrics.trade_count}",
            f"- Exposure: {result.metrics.exposure:.4f}",
            "",
        ]
    )
    summary_path.write_text(summary, encoding="utf-8")
    metrics_path.write_text(json.dumps(asdict(result.metrics), indent=2), encoding="utf-8")
    return summary_path, metrics_path


def write_optimization_summary(
    result: OptimizationResult, output_dir: str | os.PathLike[str] = "logs"
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / "optimization-summary.md"
    results_path = directory / "optimization-results.json"

    if result.best is None:
        lines = ["# Optimization Summary", "", "No valid candidates found.", ""]
    else:
        best = result.best
        lines = [
            "# Optimization Summary",
            "",
            f"- Short window: {best.candidate.short_window}",
            f"- Long window: {best.candidate.long_window}",
            f"- RSI entry ceiling: {best.candidate.rsi_entry_ceiling:.2f}",
            f"- Target allocation: {best.candidate.target_allocation:.2f}",
            f"- Train return: {best.train_metrics.total_return:.4f}",
            f"- Train max drawdown: {best.train_metrics.max_drawdown:.4f}",
            f"- Test return: {best.test_metrics.total_return:.4f}",
            f"- Test max drawdown: {best.test_metrics.max_drawdown:.4f}",
            f"- Candidates tested: {len(result.candidates)}",
            "",
        ]

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    results_path.write_text(json.dumps(optimization_to_dict(result), indent=2), encoding="utf-8")
    return summary_path, results_path
