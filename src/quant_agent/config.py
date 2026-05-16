from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_SYMBOLS = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")


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
    max_order_notional: float = 25_000.0
    max_orders_per_cycle: int = 3
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.20
    cooldown_days: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.max_symbol_allocation <= 1:
            raise ValueError("max symbol allocation must be > 0 and <= 1")
        if not 0 < self.max_total_allocation <= 1:
            raise ValueError("max total allocation must be > 0 and <= 1")
        if self.max_symbol_allocation > self.max_total_allocation:
            raise ValueError("max symbol allocation cannot exceed max total allocation")
        if self.max_order_notional <= 0:
            raise ValueError("max order notional must be positive")
        if self.max_orders_per_cycle <= 0:
            raise ValueError("max orders per cycle must be positive")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop loss percent must be positive")
        if self.take_profit_pct <= 0:
            raise ValueError("take profit percent must be positive")
        if self.cooldown_days < 0:
            raise ValueError("cooldown days cannot be negative")


@dataclass(frozen=True)
class AppConfig:
    mode: str = "backtest"
    symbols: tuple[str, ...] = field(default_factory=lambda: DEFAULT_SYMBOLS)
    starting_cash: float = 100_000.0
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", tuple(self.symbols))
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
