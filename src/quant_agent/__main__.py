from __future__ import annotations

import argparse
import json
import os
import sys

from quant_agent.backtest import Backtester
from quant_agent.broker import AlpacaPaperBroker, BrokerOrder, PaperBrokerSettings, reject_live_mode
from quant_agent.config import AppConfig, load_default_config
from quant_agent.journal import write_backtest_summary, write_optimization_summary
from quant_agent.optimizer import optimize_strategy
from quant_agent.sample_data import load_sample_bars


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant_agent")
    parser.add_argument("command", choices=["backtest", "optimize", "paper", "paper-preview", "paper-submit"])
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    args = parser.parse_args(argv)

    if args.command == "backtest":
        config = load_default_config()
        result = Backtester(config).run(load_sample_bars(config.symbols))
        output_dir = os.getenv("QUANT_AGENT_LOG_DIR", "logs")
        summary_path, metrics_path = write_backtest_summary(result, output_dir)
        print(f"Backtest complete. Summary: {summary_path}. Metrics: {metrics_path}.")
        return 0

    if args.command == "optimize":
        config = load_default_config()
        result = optimize_strategy(config, load_sample_bars(config.symbols))
        output_dir = os.getenv("QUANT_AGENT_LOG_DIR", "logs")
        summary_path, results_path = write_optimization_summary(result, output_dir)
        print(f"Optimization complete. Summary: {summary_path}. Results: {results_path}.")
        return 0

    if args.command == "paper":
        try:
            PaperBrokerSettings.from_environment()
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        config = AppConfig(mode="paper")
        print(
            f"Paper mode configured for {len(config.symbols)} symbols. "
            "Order placement is not connected in this milestone."
        )
        return 0

    if args.command == "paper-preview":
        order = BrokerOrder(symbol=args.symbol, qty=args.qty, side=args.side)
        preview = AlpacaPaperBroker(PaperBrokerSettings("preview", "preview")).preview_order(order)
        print("Paper order preview:")
        print(json.dumps(preview, indent=2))
        return 0

    if args.command == "paper-submit":
        try:
            settings = PaperBrokerSettings.from_environment()
            response = AlpacaPaperBroker(settings).submit_order(BrokerOrder(args.symbol, args.qty, args.side))
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(response, indent=2))
        return 0

    reject_live_mode()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
