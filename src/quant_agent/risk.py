from __future__ import annotations

import math
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
        if not math.isfinite(signal.target_allocation) or signal.target_allocation < 0:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected invalid allocation")

        if any(not math.isfinite(allocation) or allocation < 0 for allocation in current_allocations.values()):
            return RiskDecision(False, signal.symbol, 0.0, "Rejected invalid allocation")

        has_existing_exposure = signal.symbol in positions or signal.symbol in current_allocations
        if signal.target_allocation == 0.0 and (signal.symbol in self.allowed_symbols or has_existing_exposure):
            return RiskDecision(True, signal.symbol, 0.0, signal.reason)

        if signal.symbol not in self.allowed_symbols:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected unknown symbol")

        if signal.target_allocation > self.config.max_symbol_allocation:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected symbol allocation above limit")

        other_allocation = sum(
            allocation for symbol, allocation in current_allocations.items() if symbol != signal.symbol
        )
        proposed_total = other_allocation + signal.target_allocation
        if proposed_total > self.config.max_total_allocation:
            return RiskDecision(False, signal.symbol, 0.0, "Rejected total allocation above limit")

        return RiskDecision(True, signal.symbol, signal.target_allocation, signal.reason)
