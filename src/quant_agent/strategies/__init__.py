from quant_agent.strategies.base import Strategy, get_strategy, list_strategies
from quant_agent.strategies.dca import DCAStrategy
from quant_agent.strategies.grid import GridStrategy
from quant_agent.strategies.martingale import MartingaleStrategy
from quant_agent.strategies.multi_indicator import MultiIndicatorStrategy
from quant_agent.strategies.regime_switch import RegimeSwitchStrategy
from quant_agent.strategies.trend_rsi import TrendRsiStrategy

__all__ = [
    "Strategy",
    "TrendRsiStrategy",
    "GridStrategy",
    "DCAStrategy",
    "MartingaleStrategy",
    "MultiIndicatorStrategy",
    "RegimeSwitchStrategy",
    "get_strategy",
    "list_strategies",
]
