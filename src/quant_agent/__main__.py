from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
import sys

from quant_agent.backtest import Backtester
from quant_agent.broker import (
    AlpacaPaperBroker,
    BrokerOrder,
    DuplicateOrderError,
    PaperBrokerSettings,
    reject_live_mode,
)
from quant_agent.config import AppConfig, load_default_config
from quant_agent.journal import write_backtest_summary, write_optimization_summary
from quant_agent.market_clock import AlpacaClockClient, TradingPreflight
from quant_agent.market_data import AlpacaMarketDataClient, MarketDataSettings
from quant_agent.optimizer import optimize_strategy
from quant_agent.sample_data import load_sample_bars
from quant_agent.screener import StockScreener
from quant_agent.strategies import get_strategy
from quant_agent.trading_cycle import PaperTradingCycle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant_agent")
    parser.add_argument(
        "command",
        choices=[
            "backtest",
            "optimize",
            "paper",
            "paper-preview",
            "paper-submit",
            "paper-clock",
            "paper-cycle",
            "data-preview",
            "screen",
            "serve",
            "news",
            "indicators",
            "strategies",
        ],
    )
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument("--timeframe", default="1Day")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-volume", type=float, default=500000)
    parser.add_argument("--strategy", default=None, help="Strategy name: trend_rsi, grid, dca, martingale")
    parser.add_argument("--category", default="general", help="News category for news command")
    args = parser.parse_args(argv)

    if args.command == "backtest":
        config = load_default_config()
        strategy = get_strategy(args.strategy) if args.strategy else None
        result = Backtester(config, strategy=strategy).run(load_sample_bars(config.symbols))
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
            TradingPreflight(lambda: AlpacaClockClient(settings).get_clock()).assert_can_submit_order()
            response = AlpacaPaperBroker(settings).submit_order_if_no_duplicate(BrokerOrder(args.symbol, args.qty, args.side))
        except (DuplicateOrderError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(response, indent=2))
        return 0

    if args.command == "paper-clock":
        try:
            settings = PaperBrokerSettings.from_environment()
            clock = AlpacaClockClient(settings).get_clock()
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(clock.__dict__, indent=2))
        return 0

    if args.command == "paper-cycle":
        try:
            broker_settings = PaperBrokerSettings.from_environment()
            data_settings = MarketDataSettings.from_environment()
            if args.submit:
                TradingPreflight(lambda: AlpacaClockClient(broker_settings).get_clock()).assert_can_submit_order()
            config = AppConfig(mode="paper")
            strategy = get_strategy(args.strategy) if args.strategy else None
            result = PaperTradingCycle(
                config,
                AlpacaPaperBroker(broker_settings),
                AlpacaMarketDataClient(data_settings),
                strategy=strategy,
            ).run(args.start, args.end, timeframe=args.timeframe, submit_orders=args.submit)
        except (DuplicateOrderError, RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(result, default=lambda value: value.__dict__, indent=2))
        return 0

    if args.command == "data-preview":
        try:
            settings = MarketDataSettings.from_environment()
            bars = AlpacaMarketDataClient(settings).fetch_bars(
                [args.symbol],
                start=args.start,
                end=args.end,
                timeframe=args.timeframe,
            )
        except (RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps({symbol: [bar.__dict__ for bar in symbol_bars[:5]] for symbol, symbol_bars in bars.items()}, indent=2))
        return 0

    if args.command == "screen":
        try:
            from quant_agent.broker import _load_env_if_needed
            from quant_agent.universe import get_full_universe
            _load_env_if_needed()
            settings = MarketDataSettings.from_environment()
            client = AlpacaMarketDataClient(settings)
            all_symbols = get_full_universe()
            print(f"Scanning {len(all_symbols)} stocks...", file=sys.stderr)
            bars_by_symbol = client.fetch_bars_for_symbols(
                all_symbols, start=args.start, end=args.end, timeframe=args.timeframe,
            )
            print(f"Got bars for {len(bars_by_symbol)} stocks", file=sys.stderr)
            config = load_default_config()
            screener = StockScreener(config, min_avg_volume=args.min_volume, top_n=args.top)
            result = screener.screen(bars_by_symbol)
        except (RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        output = {
            "total_scanned": result.total_scanned,
            "passed_filters": result.passed_filters,
            "buy_signals": [{"symbol": r.symbol, "price": r.latest_price, "volume": int(r.avg_volume), "reason": r.signal.reason} for r in result.buy_signals],
            "sell_signals": [{"symbol": r.symbol, "price": r.latest_price, "volume": int(r.avg_volume), "reason": r.signal.reason} for r in result.sell_signals],
        }
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "serve":
        try:
            from quant_agent.server import create_app
        except ImportError:
            print(
                "Flask is required for the serve command. "
                "Install it with: pip install flask",
                file=sys.stderr,
            )
            return 2
        app = create_app()
        app.run(host="127.0.0.1", port=args.port, debug=False)
        return 0

    if args.command == "news":
        from dataclasses import asdict
        from quant_agent.news import FinnhubClient
        client = FinnhubClient()
        try:
            items = client.fetch_market_news(args.category)
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 2
        for item in items[:10]:
            print(f"[{item.source}] {item.headline}")
            print(f"  {item.url}")
        return 0

    if args.command == "indicators":
        from dataclasses import asdict
        from quant_agent.indicators import (
            bollinger_bands, bollinger_percent_b, bollinger_bandwidth,
            kdj, macd, relative_strength_index, simple_moving_average, supertrend,
        )
        try:
            settings = MarketDataSettings.from_environment()
            bars = AlpacaMarketDataClient(settings).fetch_bars(
                [args.symbol], start=args.start, end=args.end, timeframe=args.timeframe,
            )
        except (RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        bars_list = bars.get(args.symbol, [])
        if not bars_list:
            print(f"No data for {args.symbol}", file=sys.stderr)
            return 2
        closes = [b.close for b in bars_list]
        highs = [b.high for b in bars_list]
        lows = [b.low for b in bars_list]
        result = {
            "symbol": args.symbol,
            "price": closes[-1],
            "sma_50": simple_moving_average(closes, 50),
            "sma_100": simple_moving_average(closes, 100),
            "rsi_14": relative_strength_index(closes, 14),
            "macd": macd(closes),
            "bollinger": bollinger_bands(closes),
            "bollinger_pct_b": bollinger_percent_b(closes),
            "bollinger_bw": bollinger_bandwidth(closes),
            "kdj": kdj(highs, lows, closes),
            "supertrend": supertrend(highs, lows, closes),
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "strategies":
        from quant_agent.strategies import list_strategies
        print(json.dumps(list_strategies(), indent=2))
        return 0

    reject_live_mode()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
