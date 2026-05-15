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
