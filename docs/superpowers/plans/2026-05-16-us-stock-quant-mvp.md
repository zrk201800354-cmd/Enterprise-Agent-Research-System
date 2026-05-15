# US Stock Quant MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python MVP for US stock quant backtesting with paper-trading safety gates and no live trading path.

**Architecture:** Use a small standard-library-first package under `src/quant_agent`. Core trading logic is deterministic: config, data models, indicators, strategy, risk, backtest accounting, journal output, CLI, and a paper broker guard. Backtests run against built-in sample daily bars first so the MVP is runnable without network credentials.

**Tech Stack:** Python 3.11+, `pytest`, standard-library dataclasses, JSON/CSV/Markdown logs, optional future Alpaca/yfinance adapters.

---

## File Structure

- Create: `pyproject.toml` for package metadata and pytest configuration.
- Create: `src/quant_agent/__init__.py` for package version.
- Create: `src/quant_agent/__main__.py` for `python -m quant_agent` commands.
- Create: `src/quant_agent/config.py` for default symbols, strategy parameters, risk limits, and mode validation.
- Create: `src/quant_agent/models.py` for immutable bars, signals, positions, trades, and metrics.
- Create: `src/quant_agent/indicators.py` for SMA and RSI calculations.
- Create: `src/quant_agent/strategy.py` for deterministic trend plus RSI signals.
- Create: `src/quant_agent/risk.py` for portfolio and order safety gates.
- Create: `src/quant_agent/sample_data.py` for offline sample daily bars.
- Create: `src/quant_agent/backtest.py` for day-by-day simulation and metrics.
- Create: `src/quant_agent/journal.py` for JSONL trade logs and Markdown summaries.
- Create: `src/quant_agent/broker.py` for paper broker configuration checks and explicit live rejection.
- Create: `tests/test_config.py`.
- Create: `tests/test_indicators_strategy.py`.
- Create: `tests/test_risk.py`.
- Create: `tests/test_backtest.py`.
- Create: `tests/test_journal_cli_broker.py`.

## Task 1: Project Scaffold, Models, And Config

**Files:**
- Create: `pyproject.toml`
- Create: `src/quant_agent/__init__.py`
- Create: `src/quant_agent/models.py`
- Create: `src/quant_agent/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config and model tests**

```python
# tests/test_config.py
import pytest

from quant_agent.config import AppConfig, DEFAULT_SYMBOLS, load_default_config
from quant_agent.models import Bar, Signal


def test_default_config_is_backtest_only_with_expected_symbols():
    config = load_default_config()

    assert config.mode == "backtest"
    assert config.symbols == DEFAULT_SYMBOLS
    assert config.risk.max_symbol_allocation == 0.20
    assert config.risk.max_total_allocation == 0.80
    assert config.strategy.short_window == 20
    assert config.strategy.long_window == 50
    assert config.strategy.rsi_period == 14
    assert config.strategy.rsi_entry_ceiling == 70.0


def test_live_mode_is_rejected_in_first_version():
    with pytest.raises(ValueError, match="Live trading is not supported"):
        AppConfig(mode="live")


def test_bar_rejects_invalid_prices():
    with pytest.raises(ValueError, match="positive"):
        Bar(date="2026-01-02", open=10.0, high=11.0, low=9.0, close=0.0, volume=1000)


def test_signal_rejects_short_targets():
    with pytest.raises(ValueError, match="long-only"):
        Signal(symbol="SPY", target_allocation=-0.1, reason="short")
```

- [ ] **Step 2: Run config tests to verify they fail**

Run: `pytest tests/test_config.py -v`

Expected: FAIL because `quant_agent.config` and `quant_agent.models` do not exist.

- [ ] **Step 3: Add project metadata**

```toml
# pyproject.toml
[project]
name = "quant-agent"
version = "0.1.0"
description = "US stock quant backtest and paper-trading MVP"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Add package version**

```python
# src/quant_agent/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 5: Add models**

```python
# src/quant_agent/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        prices = (self.open, self.high, self.low, self.close)
        if any(price <= 0 for price in prices):
            raise ValueError("Bar prices must be positive")
        if self.low > self.high:
            raise ValueError("Bar low cannot exceed high")
        if self.volume < 0:
            raise ValueError("Bar volume cannot be negative")


@dataclass(frozen=True)
class Signal:
    symbol: str
    target_allocation: float
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Signal symbol is required")
        if self.target_allocation < 0:
            raise ValueError("This MVP is long-only and rejects short targets")
        if self.target_allocation > 1:
            raise ValueError("Signal target allocation cannot exceed 100%")


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: int
    average_price: float

    @property
    def is_open(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True)
class Trade:
    date: str
    symbol: str
    side: str
    quantity: int
    price: float
    reason: str

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    exposure: float
```

- [ ] **Step 6: Add config**

```python
# src/quant_agent/config.py
from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


@dataclass(frozen=True)
class StrategyConfig:
    short_window: int = 20
    long_window: int = 50
    rsi_period: int = 14
    rsi_entry_ceiling: float = 70.0


@dataclass(frozen=True)
class RiskConfig:
    max_symbol_allocation: float = 0.20
    max_total_allocation: float = 0.80
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.20
    cooldown_days: int = 3


@dataclass(frozen=True)
class AppConfig:
    mode: str = "backtest"
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    starting_cash: float = 100_000.0
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    def __post_init__(self) -> None:
        if self.mode == "live":
            raise ValueError("Live trading is not supported in the first version")
        if self.mode not in {"backtest", "paper"}:
            raise ValueError("Mode must be backtest or paper")
        if not self.symbols:
            raise ValueError("At least one symbol is required")
        if self.starting_cash <= 0:
            raise ValueError("Starting cash must be positive")


def load_default_config() -> AppConfig:
    return AppConfig()
```

- [ ] **Step 7: Run config tests to verify they pass**

Run: `pytest tests/test_config.py -v`

Expected: PASS with 4 passed.

- [ ] **Step 8: Commit scaffold**

Run:

```bash
git add pyproject.toml src/quant_agent/__init__.py src/quant_agent/models.py src/quant_agent/config.py tests/test_config.py
git commit -m "feat: add quant config and models"
```

## Task 2: Indicators And Strategy

**Files:**
- Create: `src/quant_agent/indicators.py`
- Create: `src/quant_agent/strategy.py`
- Test: `tests/test_indicators_strategy.py`

- [ ] **Step 1: Write failing tests for indicators and strategy**

```python
# tests/test_indicators_strategy.py
from quant_agent.config import StrategyConfig
from quant_agent.models import Bar, Position
from quant_agent.strategy import TrendRsiStrategy
from quant_agent.indicators import relative_strength_index, simple_moving_average


def bars_from_closes(closes):
    return [
        Bar(date=f"2026-01-{index + 1:02d}", open=close, high=close + 1, low=close - 1, close=close, volume=1000)
        for index, close in enumerate(closes)
    ]


def test_simple_moving_average_uses_latest_window():
    assert simple_moving_average([10, 20, 30, 40], window=3) == 30.0


def test_rsi_returns_high_value_after_consistent_gains():
    value = relative_strength_index([10, 11, 12, 13, 14, 15], period=5)

    assert value == 100.0


def test_strategy_waits_for_enough_history():
    strategy = TrendRsiStrategy(StrategyConfig(short_window=3, long_window=5, rsi_period=3))

    signal = strategy.generate_signal("SPY", bars_from_closes([10, 11, 12, 13]), existing_position=None)

    assert signal.target_allocation == 0.0
    assert "Not enough history" in signal.reason


def test_strategy_creates_long_signal_when_trend_positive_and_rsi_allowed():
    config = StrategyConfig(short_window=3, long_window=5, rsi_period=3, rsi_entry_ceiling=101.0)
    strategy = TrendRsiStrategy(config)

    signal = strategy.generate_signal("SPY", bars_from_closes([10, 10, 10, 11, 12, 13]), existing_position=None)

    assert signal.target_allocation == 0.20
    assert "positive trend" in signal.reason


def test_strategy_blocks_new_entry_when_rsi_is_too_high():
    config = StrategyConfig(short_window=3, long_window=5, rsi_period=3, rsi_entry_ceiling=70.0)
    strategy = TrendRsiStrategy(config)

    signal = strategy.generate_signal("SPY", bars_from_closes([10, 11, 12, 13, 14, 15]), existing_position=None)

    assert signal.target_allocation == 0.0
    assert "RSI" in signal.reason


def test_strategy_exits_existing_position_when_trend_turns_negative():
    config = StrategyConfig(short_window=2, long_window=4, rsi_period=3)
    strategy = TrendRsiStrategy(config)
    position = Position(symbol="SPY", quantity=10, average_price=100.0)

    signal = strategy.generate_signal("SPY", bars_from_closes([15, 14, 13, 12, 11]), existing_position=position)

    assert signal.target_allocation == 0.0
    assert "trend turned negative" in signal.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_indicators_strategy.py -v`

Expected: FAIL because `quant_agent.indicators` and `quant_agent.strategy` do not exist.

- [ ] **Step 3: Add indicator functions**

```python
# src/quant_agent/indicators.py
from __future__ import annotations


def simple_moving_average(values: list[float], window: int) -> float | None:
    if window <= 0:
        raise ValueError("Window must be positive")
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def relative_strength_index(values: list[float], period: int) -> float | None:
    if period <= 0:
        raise ValueError("Period must be positive")
    if len(values) <= period:
        return None

    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = deltas[-period:]
    gains = [max(delta, 0.0) for delta in recent]
    losses = [abs(min(delta, 0.0)) for delta in recent]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))
```

- [ ] **Step 4: Add trend plus RSI strategy**

```python
# src/quant_agent/strategy.py
from __future__ import annotations

from quant_agent.config import StrategyConfig
from quant_agent.indicators import relative_strength_index, simple_moving_average
from quant_agent.models import Bar, Position, Signal


class TrendRsiStrategy:
    def __init__(self, config: StrategyConfig, target_allocation: float = 0.20) -> None:
        self.config = config
        self.target_allocation = target_allocation

    def generate_signal(self, symbol: str, bars: list[Bar], existing_position: Position | None) -> Signal:
        closes = [bar.close for bar in bars]
        short_ma = simple_moving_average(closes, self.config.short_window)
        long_ma = simple_moving_average(closes, self.config.long_window)
        rsi = relative_strength_index(closes, self.config.rsi_period)

        if short_ma is None or long_ma is None or rsi is None:
            return Signal(symbol=symbol, target_allocation=0.0, reason="Not enough history for indicators")

        if short_ma <= long_ma:
            if existing_position and existing_position.is_open:
                return Signal(symbol=symbol, target_allocation=0.0, reason="Exit because trend turned negative")
            return Signal(symbol=symbol, target_allocation=0.0, reason="No entry because trend is not positive")

        if existing_position and existing_position.is_open:
            return Signal(symbol=symbol, target_allocation=self.target_allocation, reason="Hold while trend remains positive")

        if rsi >= self.config.rsi_entry_ceiling:
            return Signal(symbol=symbol, target_allocation=0.0, reason=f"No entry because RSI {rsi:.2f} is too high")

        return Signal(symbol=symbol, target_allocation=self.target_allocation, reason="Enter because positive trend and RSI allowed")
```

- [ ] **Step 5: Run strategy tests**

Run: `pytest tests/test_indicators_strategy.py -v`

Expected: PASS with 6 passed.

- [ ] **Step 6: Run existing tests**

Run: `pytest tests/test_config.py tests/test_indicators_strategy.py -v`

Expected: PASS with 10 passed.

- [ ] **Step 7: Commit indicators and strategy**

Run:

```bash
git add src/quant_agent/indicators.py src/quant_agent/strategy.py tests/test_indicators_strategy.py
git commit -m "feat: add trend RSI strategy"
```

## Task 3: Risk Manager

**Files:**
- Create: `src/quant_agent/risk.py`
- Test: `tests/test_risk.py`

- [ ] **Step 1: Write failing risk tests**

```python
# tests/test_risk.py
from quant_agent.config import RiskConfig
from quant_agent.models import Position, Signal
from quant_agent.risk import RiskManager


def test_risk_rejects_unknown_symbols():
    manager = RiskManager(RiskConfig(), allowed_symbols=["SPY"])

    result = manager.approve(
        signal=Signal(symbol="TSLA", target_allocation=0.2, reason="entry"),
        current_allocations={},
        positions={},
    )

    assert result.approved is False
    assert "unknown symbol" in result.reason


def test_risk_rejects_symbol_allocation_above_limit():
    manager = RiskManager(RiskConfig(max_symbol_allocation=0.2), allowed_symbols=["SPY"])

    result = manager.approve(
        signal=Signal(symbol="SPY", target_allocation=0.25, reason="entry"),
        current_allocations={},
        positions={},
    )

    assert result.approved is False
    assert "symbol allocation" in result.reason


def test_risk_rejects_total_exposure_above_limit():
    manager = RiskManager(RiskConfig(max_total_allocation=0.8), allowed_symbols=["SPY", "QQQ"])

    result = manager.approve(
        signal=Signal(symbol="SPY", target_allocation=0.2, reason="entry"),
        current_allocations={"QQQ": 0.7},
        positions={},
    )

    assert result.approved is False
    assert "total allocation" in result.reason


def test_risk_allows_exit_to_zero_even_when_portfolio_is_full():
    manager = RiskManager(RiskConfig(max_total_allocation=0.8), allowed_symbols=["SPY"])

    result = manager.approve(
        signal=Signal(symbol="SPY", target_allocation=0.0, reason="exit"),
        current_allocations={"SPY": 0.9},
        positions={"SPY": Position(symbol="SPY", quantity=10, average_price=100.0)},
    )

    assert result.approved is True
    assert result.target_allocation == 0.0
```

- [ ] **Step 2: Run risk tests to verify they fail**

Run: `pytest tests/test_risk.py -v`

Expected: FAIL because `quant_agent.risk` does not exist.

- [ ] **Step 3: Add risk manager**

```python
# src/quant_agent/risk.py
from __future__ import annotations

from dataclasses import dataclass

from quant_agent.config import RiskConfig
from quant_agent.models import Position, Signal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    symbol: str
    target_allocation: float
    reason: str


class RiskManager:
    def __init__(self, config: RiskConfig, allowed_symbols: list[str]) -> None:
        self.config = config
        self.allowed_symbols = set(allowed_symbols)

    def approve(
        self,
        signal: Signal,
        current_allocations: dict[str, float],
        positions: dict[str, Position],
    ) -> RiskDecision:
        if signal.symbol not in self.allowed_symbols:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected unknown symbol")

        if signal.target_allocation == 0.0:
            return RiskDecision(True, signal.symbol, 0.0, signal.reason)

        if signal.target_allocation > self.config.max_symbol_allocation:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected symbol allocation above limit")

        other_allocation = sum(
            allocation for symbol, allocation in current_allocations.items() if symbol != signal.symbol
        )
        proposed_total = other_allocation + signal.target_allocation
        if proposed_total > self.config.max_total_allocation:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected total allocation above limit")

        return RiskDecision(True, signal.symbol, signal.target_allocation, signal.reason)
```

- [ ] **Step 4: Run risk tests**

Run: `pytest tests/test_risk.py -v`

Expected: PASS with 4 passed.

- [ ] **Step 5: Run all current tests**

Run: `pytest tests/test_config.py tests/test_indicators_strategy.py tests/test_risk.py -v`

Expected: PASS with 14 passed.

- [ ] **Step 6: Commit risk manager**

Run:

```bash
git add src/quant_agent/risk.py tests/test_risk.py
git commit -m "feat: add quant risk manager"
```

## Task 4: Backtest Engine And Metrics

**Files:**
- Create: `src/quant_agent/backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write failing backtest tests**

```python
# tests/test_backtest.py
from quant_agent.backtest import Backtester, calculate_max_drawdown
from quant_agent.config import AppConfig, RiskConfig, StrategyConfig
from quant_agent.models import BacktestMetrics, Bar, Signal


class FixedSignalStrategy:
    def __init__(self, allocations):
        self.allocations = allocations

    def generate_signal(self, symbol, bars, existing_position):
        index = len(bars) - 1
        allocation = self.allocations[index]
        return Signal(symbol=symbol, target_allocation=allocation, reason=f"target {allocation}")


def make_bars(closes):
    return [
        Bar(date=f"2026-01-{index + 1:02d}", open=close, high=close + 1, low=close - 1, close=close, volume=1000)
        for index, close in enumerate(closes)
    ]


def test_max_drawdown_uses_peak_to_trough_decline():
    assert calculate_max_drawdown([100.0, 120.0, 90.0, 110.0]) == -0.25


def test_backtest_buys_and_exits_using_approved_allocations():
    config = AppConfig(
        symbols=["SPY"],
        starting_cash=1000.0,
        strategy=StrategyConfig(short_window=2, long_window=3, rsi_period=2),
        risk=RiskConfig(max_symbol_allocation=0.5, max_total_allocation=0.8),
    )
    strategy = FixedSignalStrategy([0.0, 0.5, 0.5, 0.0])
    backtester = Backtester(config=config, strategy=strategy)

    result = backtester.run({"SPY": make_bars([10.0, 10.0, 12.0, 12.0])})

    assert len(result.trades) == 2
    assert result.trades[0].side == "BUY"
    assert result.trades[0].quantity == 50
    assert result.trades[1].side == "SELL"
    assert result.final_equity == 1100.0
    assert isinstance(result.metrics, BacktestMetrics)
    assert result.metrics.trade_count == 2


def test_backtest_rejects_mismatched_symbol_data():
    config = AppConfig(symbols=["SPY"])
    backtester = Backtester(config=config)

    try:
        backtester.run({})
    except ValueError as error:
        assert "Missing bars for SPY" in str(error)
    else:
        raise AssertionError("Expected missing bars error")
```

- [ ] **Step 2: Run backtest tests to verify they fail**

Run: `pytest tests/test_backtest.py -v`

Expected: FAIL because `quant_agent.backtest` does not exist.

- [ ] **Step 3: Add backtest engine**

```python
# src/quant_agent/backtest.py
from __future__ import annotations

from dataclasses import dataclass

from quant_agent.config import AppConfig
from quant_agent.models import BacktestMetrics, Bar, Position, Trade
from quant_agent.risk import RiskManager
from quant_agent.strategy import TrendRsiStrategy


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_equity: float
    trades: list[Trade]
    equity_curve: list[float]
    metrics: BacktestMetrics


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = (equity - peak) / peak
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


class Backtester:
    def __init__(self, config: AppConfig, strategy=None) -> None:
        self.config = config
        self.strategy = strategy or TrendRsiStrategy(config.strategy)
        self.risk = RiskManager(config.risk, allowed_symbols=config.symbols)

    def run(self, bars_by_symbol: dict[str, list[Bar]]) -> BacktestResult:
        for symbol in self.config.symbols:
            if symbol not in bars_by_symbol:
                raise ValueError(f"Missing bars for {symbol}")

        bar_count = min(len(bars_by_symbol[symbol]) for symbol in self.config.symbols)
        cash = self.config.starting_cash
        positions: dict[str, Position] = {}
        trades: list[Trade] = []
        equity_curve: list[float] = []
        invested_days = 0

        for index in range(bar_count):
            latest_prices = {symbol: bars_by_symbol[symbol][index].close for symbol in self.config.symbols}
            equity = self._equity(cash, positions, latest_prices)
            allocations = self._allocations(positions, latest_prices, equity)

            for symbol in self.config.symbols:
                bars = bars_by_symbol[symbol][: index + 1]
                signal = self.strategy.generate_signal(symbol, bars, positions.get(symbol))
                decision = self.risk.approve(signal, allocations, positions)
                if not decision.approved:
                    continue

                target_value = decision.target_allocation * equity
                current_position = positions.get(symbol)
                current_value = 0.0 if current_position is None else current_position.quantity * latest_prices[symbol]
                delta_value = target_value - current_value
                quantity = int(abs(delta_value) // latest_prices[symbol])

                if quantity == 0:
                    continue

                if delta_value > 0:
                    cost = quantity * latest_prices[symbol]
                    if cost > cash:
                        continue
                    cash -= cost
                    previous_quantity = current_position.quantity if current_position else 0
                    previous_cost = current_position.average_price * previous_quantity if current_position else 0.0
                    new_quantity = previous_quantity + quantity
                    average_price = (previous_cost + cost) / new_quantity
                    positions[symbol] = Position(symbol=symbol, quantity=new_quantity, average_price=average_price)
                    trades.append(Trade(bars[-1].date, symbol, "BUY", quantity, latest_prices[symbol], decision.reason))
                else:
                    if current_position is None:
                        continue
                    sell_quantity = min(quantity, current_position.quantity)
                    cash += sell_quantity * latest_prices[symbol]
                    remaining = current_position.quantity - sell_quantity
                    if remaining:
                        positions[symbol] = Position(symbol=symbol, quantity=remaining, average_price=current_position.average_price)
                    else:
                        positions.pop(symbol)
                    trades.append(Trade(bars[-1].date, symbol, "SELL", sell_quantity, latest_prices[symbol], decision.reason))

                equity = self._equity(cash, positions, latest_prices)
                allocations = self._allocations(positions, latest_prices, equity)

            end_equity = self._equity(cash, positions, latest_prices)
            equity_curve.append(end_equity)
            if positions:
                invested_days += 1

        metrics = self._metrics(equity_curve, trades, invested_days)
        return BacktestResult(
            initial_cash=self.config.starting_cash,
            final_equity=equity_curve[-1] if equity_curve else self.config.starting_cash,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    def _equity(self, cash: float, positions: dict[str, Position], prices: dict[str, float]) -> float:
        return cash + sum(position.quantity * prices[symbol] for symbol, position in positions.items())

    def _allocations(self, positions: dict[str, Position], prices: dict[str, float], equity: float) -> dict[str, float]:
        if equity <= 0:
            return {}
        return {symbol: position.quantity * prices[symbol] / equity for symbol, position in positions.items()}

    def _metrics(self, equity_curve: list[float], trades: list[Trade], invested_days: int) -> BacktestMetrics:
        if not equity_curve:
            return BacktestMetrics(0.0, 0.0, 0.0, 0.0, 0, 0.0)
        total_return = equity_curve[-1] / self.config.starting_cash - 1.0
        years = max(len(equity_curve) / 252.0, 1 / 252.0)
        annualized_return = (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1.0 else -1.0
        sell_count = len([trade for trade in trades if trade.side == "SELL"])
        win_rate = 0.0
        exposure = invested_days / len(equity_curve)
        return BacktestMetrics(total_return, annualized_return, calculate_max_drawdown(equity_curve), win_rate, len(trades), exposure)
```

- [ ] **Step 4: Run backtest tests**

Run: `pytest tests/test_backtest.py -v`

Expected: PASS with 3 passed.

- [ ] **Step 5: Run all current tests**

Run: `pytest tests/test_config.py tests/test_indicators_strategy.py tests/test_risk.py tests/test_backtest.py -v`

Expected: PASS with 17 passed.

- [ ] **Step 6: Commit backtest engine**

Run:

```bash
git add src/quant_agent/backtest.py tests/test_backtest.py
git commit -m "feat: add backtest engine"
```

## Task 5: Sample Data, Journal, Broker Guard, And CLI

**Files:**
- Create: `src/quant_agent/sample_data.py`
- Create: `src/quant_agent/journal.py`
- Create: `src/quant_agent/broker.py`
- Create: `src/quant_agent/__main__.py`
- Test: `tests/test_journal_cli_broker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_journal_cli_broker.py
import json
import os
import subprocess
import sys

import pytest

from quant_agent.backtest import BacktestResult
from quant_agent.broker import PaperBrokerSettings, reject_live_mode
from quant_agent.journal import write_backtest_summary
from quant_agent.models import BacktestMetrics
from quant_agent.sample_data import load_sample_bars


def test_sample_data_contains_default_symbols_with_enough_bars():
    data = load_sample_bars(["SPY", "QQQ"])

    assert set(data) == {"SPY", "QQQ"}
    assert len(data["SPY"]) >= 60
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


def test_live_mode_is_explicitly_rejected():
    with pytest.raises(RuntimeError, match="Live trading is not implemented"):
        reject_live_mode()


def test_cli_backtest_runs_without_network(tmp_path):
    env = os.environ.copy()
    env["QUANT_AGENT_LOG_DIR"] = str(tmp_path)

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_journal_cli_broker.py -v`

Expected: FAIL because sample data, journal, broker, and CLI modules do not exist.

- [ ] **Step 3: Add offline sample data**

```python
# src/quant_agent/sample_data.py
from __future__ import annotations

from quant_agent.models import Bar


def load_sample_bars(symbols: list[str]) -> dict[str, list[Bar]]:
    return {symbol: _make_symbol_bars(symbol, offset=index * 2.0) for index, symbol in enumerate(symbols)}


def _make_symbol_bars(symbol: str, offset: float) -> list[Bar]:
    bars: list[Bar] = []
    price = 100.0 + offset
    for index in range(80):
        if index < 30:
            price += 0.15
        elif index < 60:
            price += 0.45
        else:
            price -= 0.20
        rounded = round(price, 2)
        bars.append(
            Bar(
                date=f"2026-01-{(index % 28) + 1:02d}",
                open=rounded,
                high=round(rounded + 1.0, 2),
                low=round(rounded - 1.0, 2),
                close=rounded,
                volume=1_000_000 + index,
            )
        )
    return bars
```

- [ ] **Step 4: Add journal writer**

```python
# src/quant_agent/journal.py
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from quant_agent.backtest import BacktestResult


def write_backtest_summary(result: BacktestResult, output_dir: str | os.PathLike[str] = "logs") -> tuple[Path, Path]:
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
            f"- Trades: {result.metrics.trade_count}",
            f"- Exposure: {result.metrics.exposure:.4f}",
            "",
        ]
    )
    summary_path.write_text(summary, encoding="utf-8")
    metrics_path.write_text(json.dumps(asdict(result.metrics), indent=2), encoding="utf-8")
    return summary_path, metrics_path
```

- [ ] **Step 5: Add broker guard**

```python
# src/quant_agent/broker.py
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PaperBrokerSettings:
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"

    @classmethod
    def from_environment(cls) -> "PaperBrokerSettings":
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("Paper trading requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        return cls(api_key=api_key, secret_key=secret_key)


def reject_live_mode() -> None:
    raise RuntimeError("Live trading is not implemented in this first version")
```

- [ ] **Step 6: Add CLI**

```python
# src/quant_agent/__main__.py
from __future__ import annotations

import argparse
import os
import sys

from quant_agent.backtest import Backtester
from quant_agent.broker import PaperBrokerSettings, reject_live_mode
from quant_agent.config import AppConfig, load_default_config
from quant_agent.journal import write_backtest_summary
from quant_agent.sample_data import load_sample_bars


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant_agent")
    parser.add_argument("command", choices=["backtest", "paper"])
    args = parser.parse_args(argv)

    if args.command == "backtest":
        config = load_default_config()
        result = Backtester(config).run(load_sample_bars(config.symbols))
        output_dir = os.getenv("QUANT_AGENT_LOG_DIR", "logs")
        summary_path, metrics_path = write_backtest_summary(result, output_dir)
        print(f"Backtest complete. Summary: {summary_path}. Metrics: {metrics_path}.")
        return 0

    if args.command == "paper":
        try:
            PaperBrokerSettings.from_environment()
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        config = AppConfig(mode="paper")
        print(f"Paper mode configured for {len(config.symbols)} symbols. Order placement is not connected in this milestone.")
        return 0

    reject_live_mode()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run journal, broker, and CLI tests**

Run: `pytest tests/test_journal_cli_broker.py -v`

Expected: PASS with 5 passed.

- [ ] **Step 8: Run full suite**

Run: `pytest -v`

Expected: PASS with 22 passed.

- [ ] **Step 9: Commit runnable MVP**

Run:

```bash
git add src/quant_agent/sample_data.py src/quant_agent/journal.py src/quant_agent/broker.py src/quant_agent/__main__.py tests/test_journal_cli_broker.py
git commit -m "feat: add offline backtest CLI"
```

## Task 6: Final Verification And Usage Notes

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Write README**

````markdown
# Quant Agent

Testing-only US stock quant MVP.

## Safety

- First version does not implement live trading.
- Default command is local backtesting.
- Paper trading requires Alpaca paper credentials.
- Strategy signals are deterministic and risk-checked.

## Run Tests

```bash
pytest -v
```

## Run Backtest

```bash
python -m quant_agent backtest
```

Outputs are written to `logs/backtest-summary.md` and `logs/backtest-metrics.json` unless `QUANT_AGENT_LOG_DIR` is set.

## Paper Mode

```bash
python -m quant_agent paper
```

Paper mode checks `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. This milestone does not place paper orders yet.
````

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
.pytest_cache/
.venv/
logs/
*.pyc
```

- [ ] **Step 3: Run full verification**

Run: `pytest -v`

Expected: PASS with 22 passed.

- [ ] **Step 4: Run backtest command**

Run: `python -m quant_agent backtest`

Expected: exit code 0 and stdout containing `Backtest complete`.

- [ ] **Step 5: Inspect generated outputs**

Run:

```bash
python -c "from pathlib import Path; print(Path('logs/backtest-summary.md').read_text(encoding='utf-8').splitlines()[0]); print(Path('logs/backtest-metrics.json').exists())"
```

Expected output:

```text
# Backtest Summary
True
```

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md .gitignore
git commit -m "docs: add quant MVP usage notes"
```

## Self-Review Checklist

- Spec coverage: Tasks cover project scaffold, config, strategy, risk, backtest, paper guard, journal, CLI, tests, and usage notes.
- Safety coverage: There is no live command, live mode is rejected, and paper mode requires Alpaca paper credentials.
- Test coverage: Each production module has a failing-test-first task before implementation.
- Offline runnable path: Backtest uses built-in sample bars, so it does not need network access.
- Future extension point: Broker guard exists without order placement; Alpaca order placement remains outside this MVP until local logic passes.
