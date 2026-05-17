from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from flask import Flask, jsonify, request

from quant_agent.backtest import Backtester
from quant_agent.broker import AlpacaPaperBroker, PaperBrokerSettings
from quant_agent.config import AppConfig, load_default_config
from quant_agent.market_data import AlpacaMarketDataClient, MarketDataSettings
from quant_agent.optimizer import optimize_strategy, optimization_to_dict
from quant_agent.sample_data import load_sample_bars
from quant_agent.strategies import get_strategy, list_strategies
from quant_agent.trading_cycle import PaperTradingCycle


class _MarketDataCache:
    """Cache market data to avoid hitting Alpaca API on every request."""

    def __init__(self, ttl: int = 300) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._ttl:
                return data
        return None

    def set(self, key: str, data: Any) -> None:
        self._cache[key] = (time.time(), data)


_data_cache = _MarketDataCache(ttl=300)


BrokerFactory = Callable[[], Any]
MarketDataFactory = Callable[[], Any]


def _align_bars(bars_by_symbol: dict[str, list]) -> dict[str, list]:
    if not bars_by_symbol:
        return bars_by_symbol
    date_sets = [set(b.date for b in bars) for bars in bars_by_symbol.values()]
    common_dates = sorted(set.intersection(*date_sets))
    if not common_dates:
        return bars_by_symbol
    aligned = {}
    for symbol, bars in bars_by_symbol.items():
        date_map = {b.date: b for b in bars}
        aligned[symbol] = [date_map[d] for d in common_dates if d in date_map]
    return aligned


def _resolve_strategy(name: str | None, config: AppConfig) -> Any:
    if name is None:
        from quant_agent.strategies import TrendRsiStrategy
        return TrendRsiStrategy(config.strategy)
    return get_strategy(name)


def create_app(
    broker_factory: BrokerFactory | None = None,
    market_data_factory: MarketDataFactory | None = None,
) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    def _get_broker() -> Any:
        if broker_factory:
            return broker_factory()
        return AlpacaPaperBroker(PaperBrokerSettings.from_environment())

    def _get_market_data() -> Any:
        if market_data_factory:
            return market_data_factory()
        return AlpacaMarketDataClient(MarketDataSettings.from_environment())

    @app.route("/")
    def index():
        return app.send_static_file("dashboard.html")

    @app.route("/crypto")
    def crypto_page():
        return app.send_static_file("crypto.html")

    @app.route("/api/backtest")
    def api_backtest():
        from datetime import date, timedelta
        config = load_default_config()
        start_date = request.args.get("start", (date.today() - timedelta(days=365)).isoformat())
        end_date = request.args.get("end", date.today().isoformat())
        strategy_name = request.args.get("strategy")
        try:
            strategy = _resolve_strategy(strategy_name, config)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        cache_key = f"bars_{start_date}_{end_date}"
        bars = _data_cache.get(cache_key)
        if bars is None:
            try:
                market_data = _get_market_data()
                bars = market_data.fetch_bars(
                    list(config.symbols), start=start_date, end=end_date, timeframe="1Day",
                )
                bars = _align_bars(bars)
                valid_symbols = [s for s in config.symbols if s in bars and len(bars[s]) >= config.strategy.long_window + 5]
                if len(valid_symbols) >= 2:
                    config = AppConfig(
                        mode=config.mode, symbols=tuple(valid_symbols),
                        starting_cash=config.starting_cash, strategy=config.strategy, risk=config.risk,
                    )
                else:
                    bars = load_sample_bars(config.symbols)
            except Exception:
                bars = load_sample_bars(config.symbols)
            _data_cache.set(cache_key, bars)

        result = Backtester(config, strategy=strategy).run(bars)
        return jsonify(asdict(result))

    @app.route("/api/optimize")
    def api_optimize():
        config = load_default_config()
        strategy_name = request.args.get("strategy", "trend_rsi")
        result = optimize_strategy(config, load_sample_bars(config.symbols), strategy_name=strategy_name)
        return jsonify(optimization_to_dict(result))

    @app.route("/api/paper-cycle", methods=["POST"])
    def api_paper_cycle():
        body: dict[str, Any] = request.get_json(silent=True) or {}
        config = AppConfig(mode="paper")
        strategy_name = body.get("strategy")
        try:
            strategy = _resolve_strategy(strategy_name, config)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            broker = _get_broker()
            market_data = _get_market_data()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            result = PaperTradingCycle(
                config,
                broker,
                market_data,
                strategy=strategy,
            ).run(
                body.get("start", "2025-01-01"),
                body.get("end", "2025-12-31"),
                timeframe=body.get("timeframe", "1Day"),
                submit_orders=body.get("submit", False),
            )
        except (RuntimeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 502

        return jsonify(asdict(result))

    @app.route("/api/account")
    def api_account():
        try:
            broker = _get_broker()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            return jsonify(broker.get_account())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.route("/api/positions")
    def api_positions():
        try:
            broker = _get_broker()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            return jsonify(broker.list_positions())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.route("/api/orders")
    def api_orders():
        try:
            broker = _get_broker()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            return jsonify(broker.list_open_orders())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @app.route("/api/strategies")
    def api_strategies():
        return jsonify(list_strategies())

    @app.route("/api/news")
    def api_news():
        from quant_agent.news import FinnhubClient
        symbol = request.args.get("symbol")
        client = FinnhubClient()
        try:
            if symbol:
                items = client.fetch_company_news(symbol.upper())
            else:
                items = client.fetch_market_news()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify([asdict(item) for item in items])

    @app.route("/api/news/summary")
    def api_news_summary():
        from quant_agent.news import FinnhubClient, summarize_news
        symbol = request.args.get("symbol")
        client = FinnhubClient()
        try:
            if symbol:
                items = client.fetch_company_news(symbol.upper())
            else:
                items = client.fetch_market_news()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        summary = summarize_news(items)
        return jsonify(asdict(summary))

    @app.route("/api/indicators")
    def api_indicators():
        from quant_agent.indicators import (
            bollinger_bands, bollinger_bandwidth, bollinger_percent_b,
            kdj, macd, relative_strength_index, simple_moving_average, supertrend,
        )
        symbol = request.args.get("symbol", "SPY")
        from datetime import date, timedelta
        start_date = (date.today() - timedelta(days=365)).isoformat()
        end_date = date.today().isoformat()

        cache_key = f"ind_{symbol}_{start_date}"
        cached = _data_cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

        try:
            market_data = _get_market_data()
            bars = market_data.fetch_bars([symbol], start=start_date, end=end_date, timeframe="1Day")
            bars_list = bars.get(symbol, [])
        except Exception:
            bars_list = []

        if not bars_list:
            return jsonify({"error": f"No data for {symbol}"}), 404

        closes = [b.close for b in bars_list]
        highs = [b.high for b in bars_list]
        lows = [b.low for b in bars_list]

        result = {
            "symbol": symbol,
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
        _data_cache.set(cache_key, result)
        return jsonify(result)

    # --- Monitor endpoints ---
    _monitor = None

    def _get_monitor():
        nonlocal _monitor
        if _monitor is None:
            from quant_agent.monitor import TradingMonitor
            config = load_default_config()
            _monitor = TradingMonitor(
                broker=_get_broker() if not broker_factory else broker_factory(),
                market_data=_get_market_data() if not market_data_factory else market_data_factory(),
                config=config,
                check_interval=60,
                stop_loss_pct=config.risk.stop_loss_pct,
                take_profit_pct=config.risk.take_profit_pct,
                auto_execute=config.risk.auto_execute_sl_tp,
            )
        return _monitor

    @app.route("/api/monitor/status")
    def api_monitor_status():
        monitor = _get_monitor()
        return jsonify(asdict(monitor.status))

    @app.route("/api/monitor/start", methods=["POST"])
    def api_monitor_start():
        monitor = _get_monitor()
        monitor.start()
        return jsonify({"status": "started"})

    @app.route("/api/monitor/stop", methods=["POST"])
    def api_monitor_stop():
        monitor = _get_monitor()
        monitor.stop()
        return jsonify({"status": "stopped"})

    @app.route("/api/monitor/auto-execute", methods=["POST"])
    def api_monitor_auto_execute():
        monitor = _get_monitor()
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("enabled", True))
        monitor.set_auto_execute(enabled)
        return jsonify({"auto_execute": enabled})

    # --- Crypto endpoints ---
    _crypto_adapter = None

    def _get_crypto():
        nonlocal _crypto_adapter
        if _crypto_adapter is None:
            from quant_agent.crypto import OKXAdapter
            from quant_agent.config import CryptoConfig
            cfg = CryptoConfig()
            _crypto_adapter = OKXAdapter()
            _crypto_adapter.start(list(cfg.symbols), list(cfg.channels))
        return _crypto_adapter

    @app.route("/api/crypto/status")
    def api_crypto_status():
        adapter = _get_crypto()
        return jsonify(adapter.status())

    @app.route("/api/crypto/ticker/<inst_id>")
    def api_crypto_ticker(inst_id):
        adapter = _get_crypto()
        ticker = adapter.store.get_ticker(inst_id)
        if ticker is None:
            return jsonify({"error": "no data"}), 404
        return jsonify(asdict(ticker))

    @app.route("/api/crypto/tickers")
    def api_crypto_tickers():
        adapter = _get_crypto()
        tickers = {k: asdict(v) for k, v in adapter.store.get_all_tickers().items()}
        return jsonify(tickers)

    @app.route("/api/crypto/trades/<inst_id>")
    def api_crypto_trades(inst_id):
        adapter = _get_crypto()
        limit = request.args.get("limit", 50, type=int)
        trades = [asdict(t) for t in adapter.store.get_trades(inst_id, limit)]
        return jsonify(trades)

    @app.route("/api/crypto/candles/<inst_id>")
    def api_crypto_candles(inst_id):
        adapter = _get_crypto()
        limit = request.args.get("limit", 60, type=int)
        candles = [asdict(c) for c in adapter.store.get_candles(inst_id, limit)]
        return jsonify(candles)

    @app.route("/api/crypto/books/<inst_id>")
    def api_crypto_books(inst_id):
        adapter = _get_crypto()
        book = adapter.store.get_book(inst_id)
        if book is None:
            return jsonify({"error": "no data"}), 404
        return jsonify(asdict(book))

    @app.route("/api/crypto/subscribe", methods=["POST"])
    def api_crypto_subscribe():
        adapter = _get_crypto()
        data = request.get_json(silent=True) or {}
        symbols = data.get("symbols", [])
        if not symbols:
            return jsonify({"error": "symbols required"}), 400
        adapter.subscribe(symbols)
        return jsonify({"subscribed": adapter.subscribed_symbols})

    # --- Crypto Trading endpoints ---
    _okx_broker = None

    def _get_okx_broker():
        nonlocal _okx_broker
        if _okx_broker is None:
            from quant_agent.crypto.broker import OKXBroker, OKXBrokerSettings
            _okx_broker = OKXBroker(OKXBrokerSettings.from_environment())
        return _okx_broker

    @app.route("/api/crypto/account")
    def api_crypto_account():
        try:
            broker = _get_okx_broker()
            balance = broker.get_usdt_balance()
            return jsonify(balance)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/crypto/positions")
    def api_crypto_positions():
        try:
            broker = _get_okx_broker()
            positions = broker.list_positions()
            return jsonify(positions)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/crypto/orders")
    def api_crypto_orders():
        try:
            broker = _get_okx_broker()
            orders = broker.list_open_orders()
            return jsonify(orders)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/crypto/order", methods=["POST"])
    def api_crypto_submit_order():
        try:
            broker = _get_okx_broker()
            data = request.get_json(silent=True) or {}
            symbol = data.get("symbol", "")
            side = data.get("side", "buy")
            qty = str(data.get("qty", ""))
            order_type = data.get("order_type", "market")
            price = data.get("price")
            if not symbol or not qty:
                return jsonify({"error": "symbol and qty required"}), 400
            result = broker.submit_order(symbol, side, qty, order_type, price)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/crypto/order", methods=["DELETE"])
    def api_crypto_cancel_order():
        try:
            broker = _get_okx_broker()
            data = request.get_json(silent=True) or {}
            inst_id = data.get("inst_id", "")
            ord_id = data.get("ord_id", "")
            if not inst_id or not ord_id:
                return jsonify({"error": "inst_id and ord_id required"}), 400
            result = broker.cancel_order(inst_id, ord_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Crypto Bot endpoints ---
    _crypto_bot = None

    def _get_bot():
        nonlocal _crypto_bot
        if _crypto_bot is None:
            from quant_agent.crypto.bot import CryptoTradingBot
            _crypto_bot = CryptoTradingBot(
                adapter=_get_crypto(),
                broker=_get_okx_broker(),
            )
        return _crypto_bot

    @app.route("/api/crypto-bot/start", methods=["POST"])
    def api_crypto_bot_start():
        bot = _get_bot()
        bot.start()
        return jsonify({"status": "started"})

    @app.route("/api/crypto-bot/stop", methods=["POST"])
    def api_crypto_bot_stop():
        bot = _get_bot()
        bot.stop()
        return jsonify({"status": "stopped"})

    @app.route("/api/crypto-bot/status")
    def api_crypto_bot_status():
        bot = _get_bot()
        s = bot.status()
        from dataclasses import asdict
        return jsonify(asdict(s))

    @app.route("/api/crypto-bot/trades")
    def api_crypto_bot_trades():
        bot = _get_bot()
        limit = request.args.get("limit", 50, type=int)
        from dataclasses import asdict
        trades = [asdict(t) for t in bot._trades[-limit:]]
        return jsonify(trades)

    return app
