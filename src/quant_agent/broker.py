from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PaperBrokerSettings:
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"

    @classmethod
    def from_environment(cls) -> "PaperBrokerSettings":
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError(
                "Paper trading requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables"
            )
        return cls(api_key=api_key, secret_key=secret_key)


def reject_live_mode() -> None:
    raise RuntimeError("Live trading is not implemented in this first version")
