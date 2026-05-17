from __future__ import annotations

from typing import Protocol, runtime_checkable

from quant_agent.models import Bar, Position, Signal


@runtime_checkable
class Strategy(Protocol):
    name: str
    allows_live_trading: bool

    def generate_signal(
        self, symbol: str, bars: list[Bar], existing_position: Position | None
    ) -> Signal: ...


_STRATEGY_REGISTRY: dict[str, type] = {}


def register_strategy(cls: type) -> type:
    _STRATEGY_REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str, **kwargs) -> Strategy:
    if name not in _STRATEGY_REGISTRY:
        available = ", ".join(sorted(_STRATEGY_REGISTRY.keys()))
        raise ValueError(f"Unknown strategy: {name}. Available: {available}")
    return _STRATEGY_REGISTRY[name](**kwargs)


def list_strategies() -> list[dict[str, object]]:
    result = []
    for name, cls in sorted(_STRATEGY_REGISTRY.items()):
        instance = cls()
        result.append({
            "name": name,
            "allows_live_trading": instance.allows_live_trading,
        })
    return result
