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
