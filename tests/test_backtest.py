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
