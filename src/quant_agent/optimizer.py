from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass, replace
from typing import Any

from quant_agent.backtest import BacktestMetrics, Backtester
from quant_agent.config import AppConfig, StrategyConfig
from quant_agent.models import Bar
from quant_agent.strategies import (
    DCAStrategy,
    GridStrategy,
    MartingaleStrategy,
    MultiIndicatorStrategy,
    RegimeSwitchStrategy,
    TrendRsiStrategy,
    get_strategy,
)
from quant_agent.strategies.multi_indicator import MultiIndicatorConfig


@dataclass(frozen=True)
class OptimizationCandidate:
    strategy_name: str
    params: dict[str, Any]
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
    strategy: str
    run_id: int


def _generate_trend_rsi_candidates(rng: random.Random) -> list[OptimizationCandidate]:
    candidates = []
    short_windows = [3, 5, 7, 10, 15, 20]
    long_windows = [20, 30, 40, 50, 60, 80, 100]
    rsi_ceilings = [55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 90.0, 101.0]
    allocations = [0.08, 0.10, 0.15, 0.20, 0.25]

    for _ in range(40):
        sw = rng.choice(short_windows)
        lw = rng.choice(long_windows)
        rce = rng.choice(rsi_ceilings)
        alloc = rng.choice(allocations)
        candidates.append(OptimizationCandidate(
            strategy_name="trend_rsi",
            params={"short_window": sw, "long_window": lw, "rsi_entry_ceiling": rce},
            target_allocation=alloc,
        ))
    return candidates


def _generate_multi_indicator_candidates(rng: random.Random) -> list[OptimizationCandidate]:
    candidates = []
    rsi_periods = [7, 10, 14, 21]
    rsi_oversolds = [20.0, 25.0, 30.0, 35.0]
    rsi_overboughts = [65.0, 70.0, 75.0, 80.0]
    macd_fast = [8, 10, 12, 15]
    macd_slow = [20, 24, 26, 30]
    macd_signal = [7, 9, 12]
    bb_periods = [15, 20, 25, 30]
    bb_stds = [1.5, 2.0, 2.5, 3.0]
    st_periods = [7, 10, 14, 20]
    st_multipliers = [2.0, 2.5, 3.0, 4.0]
    thresholds = [2, 3, 4]
    allocations = [0.08, 0.10, 0.15, 0.20]

    for _ in range(40):
        candidates.append(OptimizationCandidate(
            strategy_name="multi_indicator",
            params={
                "rsi_period": rng.choice(rsi_periods),
                "rsi_oversold": rng.choice(rsi_oversolds),
                "rsi_overbought": rng.choice(rsi_overboughts),
                "macd_fast": rng.choice(macd_fast),
                "macd_slow": rng.choice(macd_slow),
                "macd_signal": rng.choice(macd_signal),
                "bb_period": rng.choice(bb_periods),
                "bb_std": rng.choice(bb_stds),
                "st_period": rng.choice(st_periods),
                "st_multiplier": rng.choice(st_multipliers),
                "buy_threshold": rng.choice(thresholds),
                "sell_threshold": rng.choice(thresholds),
            },
            target_allocation=rng.choice(allocations),
        ))
    return candidates


def _generate_dca_candidates(rng: random.Random) -> list[OptimizationCandidate]:
    candidates = []
    intervals = [1, 3, 5, 7, 14]
    amounts = [500, 1000, 2000, 5000]

    for _ in range(20):
        candidates.append(OptimizationCandidate(
            strategy_name="dca",
            params={
                "interval_days": rng.choice(intervals),
                "amount_per_buy": rng.choice(amounts),
            },
            target_allocation=0.10,
        ))
    return candidates


def _generate_grid_candidates(rng: random.Random) -> list[OptimizationCandidate]:
    candidates = []
    grid_counts = [3, 5, 7, 10, 15, 20]
    allocations = [0.05, 0.08, 0.10, 0.15]

    for _ in range(20):
        candidates.append(OptimizationCandidate(
            strategy_name="grid",
            params={
                "grid_count": rng.choice(grid_counts),
            },
            target_allocation=rng.choice(allocations),
        ))
    return candidates


def _generate_regime_switch_candidates(rng: random.Random) -> list[OptimizationCandidate]:
    candidates = []
    adx_periods = [10, 14, 20, 28]
    trend_thresholds = [20.0, 25.0, 30.0, 35.0]
    range_thresholds = [15.0, 18.0, 20.0, 22.0]
    allocations = [0.10, 0.15, 0.20]

    for _ in range(20):
        candidates.append(OptimizationCandidate(
            strategy_name="regime_switch",
            params={
                "adx_period": rng.choice(adx_periods),
                "trend_threshold": rng.choice(trend_thresholds),
                "range_threshold": rng.choice(range_thresholds),
            },
            target_allocation=rng.choice(allocations),
        ))
    return candidates


_STRATEGY_GENERATORS = {
    "trend_rsi": _generate_trend_rsi_candidates,
    "multi_indicator": _generate_multi_indicator_candidates,
    "dca": _generate_dca_candidates,
    "grid": _generate_grid_candidates,
    "regime_switch": _generate_regime_switch_candidates,
}


def _build_strategy(strategy_name: str, params: dict[str, Any], target_allocation: float):
    if strategy_name == "trend_rsi":
        cfg = StrategyConfig(
            short_window=params["short_window"],
            long_window=params["long_window"],
            rsi_entry_ceiling=params["rsi_entry_ceiling"],
        )
        return TrendRsiStrategy(cfg, target_allocation=target_allocation)
    elif strategy_name == "multi_indicator":
        cfg = MultiIndicatorConfig(
            rsi_period=params["rsi_period"],
            rsi_oversold=params["rsi_oversold"],
            rsi_overbought=params["rsi_overbought"],
            macd_fast=params["macd_fast"],
            macd_slow=params["macd_slow"],
            macd_signal=params["macd_signal"],
            bb_period=params["bb_period"],
            bb_std=params["bb_std"],
            st_period=params["st_period"],
            st_multiplier=params["st_multiplier"],
            buy_threshold=params["buy_threshold"],
            sell_threshold=params["sell_threshold"],
        )
        return MultiIndicatorStrategy(cfg, target_allocation=target_allocation)
    elif strategy_name == "dca":
        return DCAStrategy(
            interval_days=params.get("interval_days", 7),
            amount_per_buy=params.get("amount_per_buy", 1000.0),
        )
    elif strategy_name == "grid":
        return GridStrategy(
            grid_count=params.get("grid_count", 10),
            target_allocation=target_allocation,
        )
    elif strategy_name == "regime_switch":
        return RegimeSwitchStrategy(target_allocation=target_allocation)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


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
    strategy_name: str = "trend_rsi",
    candidates: list[OptimizationCandidate] | None = None,
    train_ratio: float = 0.70,
    seed: int | None = None,
) -> OptimizationResult:
    if seed is None:
        seed = int(time.time() * 1000) % (2**31)
    rng = random.Random(seed)

    if candidates is None:
        generator = _STRATEGY_GENERATORS.get(strategy_name)
        if generator is None:
            raise ValueError(f"No optimizer for strategy: {strategy_name}. Available: {list(_STRATEGY_GENERATORS.keys())}")
        candidates = generator(rng)

    train_bars, test_bars = split_bars_by_ratio(bars_by_symbol, train_ratio)
    valid_results: list[CandidateResult] = []

    for candidate in candidates:
        try:
            strategy = _build_strategy(candidate.strategy_name, candidate.params, candidate.target_allocation)
            train_result = Backtester(config, strategy=strategy).run(train_bars)
            test_result = Backtester(config, strategy=strategy).run(test_bars)
            train_score = _score(train_result.metrics)
            valid_results.append(
                CandidateResult(
                    candidate=candidate,
                    train_metrics=train_result.metrics,
                    test_metrics=test_result.metrics,
                    train_score=train_score,
                )
            )
        except Exception:
            continue

    valid_results.sort(key=lambda result: result.train_score, reverse=True)
    return OptimizationResult(
        best=valid_results[0] if valid_results else None,
        candidates=valid_results,
        strategy=strategy_name,
        run_id=seed,
    )


def optimization_to_dict(result: OptimizationResult) -> dict:
    return {
        "best": _candidate_result_to_dict(result.best) if result.best else None,
        "candidates": [_candidate_result_to_dict(candidate) for candidate in result.candidates[:10]],
        "strategy": result.strategy,
        "run_id": result.run_id,
        "total_tested": len(result.candidates),
    }


def _candidate_result_to_dict(result: CandidateResult) -> dict:
    return {
        "candidate": asdict(result.candidate),
        "train_metrics": asdict(result.train_metrics),
        "test_metrics": asdict(result.test_metrics),
        "train_score": result.train_score,
    }


def _score(metrics: BacktestMetrics) -> float:
    return metrics.total_return + metrics.max_drawdown * 0.50
