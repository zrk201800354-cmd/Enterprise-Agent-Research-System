from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_SYMBOLS = (
    # ETF
    "SPY", "QQQ",
    # 科技巨头
    "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN",
    # 半导体
    "AMD", "AVGO", "ARM", "INTC", "QCOM", "MU",
    # 软件/云
    "CRM", "ORCL", "PLTR",
    # 流媒体/通信
    "NFLX", "DIS", "CMCSA",
    # 金融
    "JPM", "BAC", "GS", "V",
    # 医疗
    "JNJ", "UNH", "PFE",
    # 消费
    "WMT", "COST", "HD", "MCD",
    # 能源
    "XOM", "CVX",
    # 工业
    "CAT", "BA",
)

DEFAULT_CRYPTO_SYMBOLS = ("BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT")
DEFAULT_CRYPTO_CHANNELS = ("tickers", "trades", "candle1m", "books5")


@dataclass(frozen=True)
class StrategyConfig:
    short_window: int = 50
    long_window: int = 100
    rsi_period: int = 14
    rsi_entry_ceiling: float = 60.0


@dataclass(frozen=True)
class RiskConfig:
    max_symbol_allocation: float = 0.20
    max_total_allocation: float = 0.80
    max_order_notional: float = 25_000.0
    max_orders_per_cycle: int = 8
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.20
    cooldown_days: int = 3
    auto_execute_sl_tp: bool = False

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
class CryptoConfig:
    exchange: str = "okx"
    symbols: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CRYPTO_SYMBOLS)
    channels: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CRYPTO_CHANNELS)


@dataclass(frozen=True)
class AppConfig:
    mode: str = "backtest"
    symbols: tuple[str, ...] = field(default_factory=lambda: DEFAULT_SYMBOLS)
    starting_cash: float = 100_000.0
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    crypto: CryptoConfig | None = None

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
