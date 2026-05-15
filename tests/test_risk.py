from dataclasses import FrozenInstanceError

import pytest

from quant_agent.config import RiskConfig
from quant_agent.models import Position, Signal
from quant_agent.risk import RiskDecision, RiskManager


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


def test_risk_total_exposure_excludes_same_symbol_current_allocation():
    manager = RiskManager(RiskConfig(max_total_allocation=0.8), allowed_symbols=["SPY", "QQQ"])

    result = manager.approve(
        signal=Signal(symbol="SPY", target_allocation=0.2, reason="rebalance"),
        current_allocations={"SPY": 0.5, "QQQ": 0.5},
        positions={},
    )

    assert result.approved is True
    assert result.target_allocation == 0.2


def test_risk_approved_nonzero_path_returns_requested_target_and_reason():
    manager = RiskManager(RiskConfig(), allowed_symbols=["SPY"])

    result = manager.approve(
        signal=Signal(symbol="SPY", target_allocation=0.15, reason="entry"),
        current_allocations={},
        positions={},
    )

    assert result.approved is True
    assert result.target_allocation == 0.15
    assert result.reason == "entry"


def test_risk_decision_is_frozen():
    decision = RiskDecision(approved=True, symbol="SPY", target_allocation=0.2, reason="entry")

    with pytest.raises(FrozenInstanceError):
        decision.approved = False


def test_risk_manager_stores_config_and_allowed_symbols():
    config = RiskConfig(max_symbol_allocation=0.15)

    manager = RiskManager(config, allowed_symbols=["SPY", "QQQ"])

    assert manager.config is config
    assert manager.allowed_symbols == {"SPY", "QQQ"}
