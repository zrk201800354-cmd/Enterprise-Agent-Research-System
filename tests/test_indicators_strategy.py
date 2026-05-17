import pytest

from quant_agent.config import StrategyConfig
from quant_agent.indicators import relative_strength_index, simple_moving_average
from quant_agent.models import Bar, Position
from quant_agent.strategies import TrendRsiStrategy


def bars_from_closes(closes):
    return [
        Bar(
            date=f"2026-01-{index + 1:02d}",
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_simple_moving_average_uses_latest_window():
    assert simple_moving_average([10, 20, 30, 40], window=3) == 30.0


@pytest.mark.parametrize("window", [0, -1])
def test_simple_moving_average_rejects_nonpositive_window(window):
    with pytest.raises(ValueError, match="Window must be positive"):
        simple_moving_average([10, 20, 30], window=window)


def test_simple_moving_average_returns_none_for_insufficient_history():
    assert simple_moving_average([10, 20], window=3) is None


def test_rsi_returns_high_value_after_consistent_gains():
    value = relative_strength_index([10, 11, 12, 13, 14, 15], period=5)

    assert value == 100.0


def test_rsi_returns_neutral_value_after_flat_prices():
    value = relative_strength_index([10, 10, 10, 10], period=3)

    assert value == 50.0


def test_rsi_keeps_gain_into_flat_plateau_overbought():
    value = relative_strength_index([10, 10, 10, 12, 12, 12], period=3)

    assert value == 100.0


@pytest.mark.parametrize("period", [0, -1])
def test_rsi_rejects_nonpositive_period(period):
    with pytest.raises(ValueError, match="Period must be positive"):
        relative_strength_index([10, 11, 12], period=period)


def test_rsi_returns_none_for_insufficient_history():
    assert relative_strength_index([10, 11, 12], period=3) is None


def test_rsi_returns_standard_mixed_gain_loss_value():
    value = relative_strength_index([10, 12, 11, 13, 12], period=4)

    assert value == pytest.approx(66.6666666667)


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


def test_strategy_allows_entry_when_positive_trend_has_flat_neutral_rsi():
    config = StrategyConfig(short_window=3, long_window=5, rsi_period=3, rsi_entry_ceiling=70.0)
    strategy = TrendRsiStrategy(config)

    signal = strategy.generate_signal("SPY", bars_from_closes([10, 10, 12, 12, 12, 12]), existing_position=None)

    assert signal.target_allocation == 0.20


def test_strategy_holds_existing_position_when_trend_remains_positive():
    config = StrategyConfig(short_window=3, long_window=5, rsi_period=3)
    strategy = TrendRsiStrategy(config)
    position = Position(symbol="SPY", quantity=10, average_price=100.0)

    signal = strategy.generate_signal("SPY", bars_from_closes([10, 10, 10, 11, 12, 13]), existing_position=position)

    assert signal.target_allocation == 0.20
    assert "Hold" in signal.reason


def test_strategy_exits_existing_position_when_trend_turns_negative():
    config = StrategyConfig(short_window=2, long_window=4, rsi_period=3)
    strategy = TrendRsiStrategy(config)
    position = Position(symbol="SPY", quantity=10, average_price=100.0)

    signal = strategy.generate_signal("SPY", bars_from_closes([15, 14, 13, 12, 11]), existing_position=position)

    assert signal.target_allocation == 0.0
    assert "trend turned negative" in signal.reason


def test_strategy_returns_no_entry_when_trend_negative_without_open_position():
    config = StrategyConfig(short_window=2, long_window=4, rsi_period=3)
    strategy = TrendRsiStrategy(config)

    signal = strategy.generate_signal("SPY", bars_from_closes([15, 14, 13, 12, 11]), existing_position=None)

    assert signal.target_allocation == 0.0
    assert "trend is not positive" in signal.reason
