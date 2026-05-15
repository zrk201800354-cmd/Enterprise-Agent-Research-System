import pytest

from quant_agent.config import AppConfig, DEFAULT_SYMBOLS, RiskConfig, load_default_config
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


def test_default_symbols_are_immutable():
    assert DEFAULT_SYMBOLS == ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")


def test_config_normalizes_symbols_to_immutable_tuple():
    symbols = ["SPY", "QQQ"]
    config = AppConfig(symbols=symbols)

    symbols.append("AAPL")

    assert config.symbols == ("SPY", "QQQ")


def test_live_mode_is_rejected_in_first_version():
    with pytest.raises(ValueError, match="Live trading is not supported"):
        AppConfig(mode="live")


def test_bar_rejects_invalid_prices():
    with pytest.raises(ValueError, match="positive"):
        Bar(date="2026-01-02", open=10.0, high=11.0, low=9.0, close=0.0, volume=1000)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"open": 8.0, "high": 11.0, "low": 9.0, "close": 10.0},
        {"open": 12.0, "high": 11.0, "low": 9.0, "close": 10.0},
        {"open": 10.0, "high": 11.0, "low": 9.0, "close": 8.0},
        {"open": 10.0, "high": 11.0, "low": 9.0, "close": 12.0},
    ],
)
def test_bar_rejects_open_or_close_outside_daily_range(kwargs):
    with pytest.raises(ValueError, match="within low and high"):
        Bar(date="2026-01-02", volume=1000, **kwargs)


def test_signal_rejects_short_targets():
    with pytest.raises(ValueError, match="long-only"):
        Signal(symbol="SPY", target_allocation=-0.1, reason="short")


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"max_symbol_allocation": 0.0}, "max symbol allocation"),
        ({"max_symbol_allocation": 1.1}, "max symbol allocation"),
        ({"max_total_allocation": 0.0}, "max total allocation"),
        ({"max_total_allocation": 1.1}, "max total allocation"),
        (
            {"max_symbol_allocation": 0.80, "max_total_allocation": 0.20},
            "cannot exceed",
        ),
        ({"stop_loss_pct": 0.0}, "stop loss"),
        ({"take_profit_pct": 0.0}, "take profit"),
        ({"cooldown_days": -1}, "cooldown"),
    ],
)
def test_risk_config_rejects_unsafe_values(kwargs, match):
    with pytest.raises(ValueError, match=match):
        RiskConfig(**kwargs)
