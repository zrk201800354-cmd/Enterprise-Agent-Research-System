from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from quant_agent.backtest import BacktestResult


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
