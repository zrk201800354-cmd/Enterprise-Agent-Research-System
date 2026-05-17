from __future__ import annotations

from dataclasses import dataclass

from quant_agent.crypto.models import CryptoPosition


@dataclass(frozen=True)
class CryptoRiskConfig:
    max_per_trade_pct: float = 0.02
    max_total_allocation: float = 0.10
    trailing_stop_pct: float = 0.03
    take_profit_pct: float = 0.06
    base_stop_loss_pct: float = 0.02


class CryptoRiskManager:
    def __init__(self, config: CryptoRiskConfig | None = None) -> None:
        self.config = config or CryptoRiskConfig()

    def compute_quantity(self, equity: float, price: float, target_allocation: float) -> float:
        alloc = min(target_allocation, self.config.max_per_trade_pct)
        value = equity * alloc
        if price <= 0:
            return 0.0
        qty = value / price
        return int(qty * 1e8) / 1e8

    def check_trailing_stop(self, position: CryptoPosition, current_price: float) -> tuple[bool, str]:
        if current_price > position.highest_price:
            position.highest_price = current_price
            return False, ""
        if position.highest_price <= 0:
            return False, ""
        drop_pct = (position.highest_price - current_price) / position.highest_price
        if drop_pct >= self.config.trailing_stop_pct:
            return True, f"trailing stop ({drop_pct:.1%} from peak {position.highest_price:.2f})"
        return False, ""

    def check_stop_loss(self, position: CryptoPosition, current_price: float) -> tuple[bool, str]:
        if position.average_price <= 0:
            return False, ""
        pnl_pct = (current_price - position.average_price) / position.average_price
        if pnl_pct <= -self.config.base_stop_loss_pct:
            return True, f"stop loss ({pnl_pct:.1%})"
        return False, ""

    def check_take_profit(self, position: CryptoPosition, current_price: float) -> tuple[bool, str]:
        if position.average_price <= 0:
            return False, ""
        pnl_pct = (current_price - position.average_price) / position.average_price
        if pnl_pct >= self.config.take_profit_pct:
            return True, f"take profit ({pnl_pct:.1%})"
        return False, ""

    def check_total_allocation(self, positions: dict[str, CryptoPosition], equity: float) -> float:
        if equity <= 0:
            return 0.0
        used = sum(p.quantity * p.average_price for p in positions.values() if p.is_open) / equity
        return max(0.0, self.config.max_total_allocation - used)
