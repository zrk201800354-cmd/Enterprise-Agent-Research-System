from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from quant_agent.backtest import BacktestMetrics, Backtester
from quant_agent.config import AppConfig, StrategyConfig
from quant_agent.models import Bar
from quant_agent.strategy import TrendRsiStrategy


@dataclass(frozen=True)
class OptimizationCandidate:
    short_window: int
    long_window: int
    rsi_entry_ceiling: float
    target_allocation: float


@dataclass(frozen=True)
class CandidateResult:
    candidate: OptimizationCandidate
    train_metrics: BacktestMetrics
    test_metrics: BacktestMetrics
    train_score: float


@dataclass(frozen=True)
class OptimizationResult:
    best: CandidateResult | None
    candidates: list[CandidateResult]


def default_candidates() -> list[OptimizationCandidate]:
    candidates: list[OptimizationCandidate] = []
    for short_window in (5, 10, 20):
        for long_window in (20, 40, 60):
            for rsi_entry_ceiling in (65.0, 70.0, 80.0, 101.0):
                for target_allocation in (0.10, 0.20):
                    candidates.append(
                        OptimizationCandidate(
                            short_window=short_window,
                            long_window=long_window,
                            rsi_entry_ceiling=rsi_entry_ceiling,
                            target_allocation=target_allocation,
                        )
                    )
    return candidates


def split_bars_by_ratio(
    bars_by_symbol: dict[str, list[Bar]], train_ratio: float
) -> tuple[dict[str, list[Bar]], dict[str, list[Bar]]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not bars_by_symbol:
        raise ValueError("bars are required")

    first_symbol = next(iter(bars_by_symbol))
    split_index = int(len(bars_by_symbol[first_symbol]) * train_ratio)
    if split_index <= 0 or split_index >= len(bars_by_symbol[first_symbol]):
        raise ValueError("train/test split must leave bars in both segments")

    train: dict[str, list[Bar]] = {}
    test: dict[str, list[Bar]] = {}
    for symbol, bars in bars_by_symbol.items():
        train[symbol] = bars[:split_index]
        test[symbol] = bars[split_index:]
    return train, test


def optimize_strategy(
    config: AppConfig,
    bars_by_symbol: dict[str, list[Bar]],
    candidates: list[OptimizationCandidate] | None = None,
    train_ratio: float = 0.70,
) -> OptimizationResult:
    train_bars, test_bars = split_bars_by_ratio(bars_by_symbol, train_ratio)
    valid_results: list[CandidateResult] = []

    for candidate in candidates or default_candidates():
        if not _candidate_is_valid(candidate, config):
            continue

        candidate_config = replace(
            config,
            strategy=StrategyConfig(
                short_window=candidate.short_window,
                long_window=candidate.long_window,
                rsi_period=config.strategy.rsi_period,
                rsi_entry_ceiling=candidate.rsi_entry_ceiling,
            ),
        )
        strategy = TrendRsiStrategy(candidate_config.strategy, target_allocation=candidate.target_allocation)
        train_result = Backtester(candidate_config, strategy=strategy).run(train_bars)
        test_result = Backtester(candidate_config, strategy=strategy).run(test_bars)
        train_score = _score(train_result.metrics)
        valid_results.append(
            CandidateResult(
                candidate=candidate,
                train_metrics=train_result.metrics,
                test_metrics=test_result.metrics,
                train_score=train_score,
            )
        )

    valid_results.sort(key=lambda result: result.train_score, reverse=True)
    return OptimizationResult(best=valid_results[0] if valid_results else None, candidates=valid_results)


def optimization_to_dict(result: OptimizationResult) -> dict:
    return {
        "best": _candidate_result_to_dict(result.best) if result.best else None,
        "candidates": [_candidate_result_to_dict(candidate) for candidate in result.candidates],
    }


def _candidate_result_to_dict(result: CandidateResult) -> dict:
    return {
        "candidate": asdict(result.candidate),
        "train_metrics": asdict(result.train_metrics),
        "test_metrics": asdict(result.test_metrics),
        "train_score": result.train_score,
    }


def _candidate_is_valid(candidate: OptimizationCandidate, config: AppConfig) -> bool:
    if candidate.short_window <= 0 or candidate.long_window <= 0:
        return False
    if candidate.short_window >= candidate.long_window:
        return False
    if candidate.rsi_entry_ceiling <= 0:
        return False
    if candidate.target_allocation <= 0:
        return False
    return candidate.target_allocation <= config.risk.max_symbol_allocation


def _score(metrics: BacktestMetrics) -> float:
    return metrics.total_return + metrics.max_drawdown * 0.50
