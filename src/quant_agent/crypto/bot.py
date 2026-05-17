from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timezone
from typing import Any

from quant_agent.config import AppConfig
from quant_agent.crypto.aggregator import CandleAggregator
from quant_agent.crypto.base import CryptoAdapter
from quant_agent.crypto.broker import OKXBroker
from quant_agent.crypto.models import BotStatus, CryptoPosition, CryptoTrade, candle_to_bar
from quant_agent.crypto.risk import CryptoRiskConfig, CryptoRiskManager
from quant_agent.strategies import get_strategy
from quant_agent.strategies.multi_indicator import MultiIndicatorConfig, MultiIndicatorStrategy


class CryptoTradingBot:
    """Automated crypto trading bot running as a background thread."""

    def __init__(
        self,
        adapter: CryptoAdapter,
        broker: OKXBroker,
        symbols: list[str] | None = None,
        timeframe: str = "5m",
        strategy_name: str = "multi_indicator",
        risk_config: CryptoRiskConfig | None = None,
        optimization_interval_hours: float = 4.0,
        check_interval_seconds: float = 30.0,
        starting_cash: float = 10_000.0,
    ) -> None:
        self._adapter = adapter
        self._broker = broker
        self._symbols = symbols or ["ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"]
        self._timeframe = timeframe
        self._strategy_name = strategy_name
        self._risk = CryptoRiskManager(risk_config or CryptoRiskConfig(
            max_per_trade_pct=0.20, max_total_allocation=0.80,
            trailing_stop_pct=0.03, take_profit_pct=0.06, base_stop_loss_pct=0.02,
        ))
        self._opt_interval = optimization_interval_hours * 3600
        self._check_interval = check_interval_seconds
        self._starting_cash = starting_cash

        self._aggregator = CandleAggregator()
        if strategy_name == "multi_indicator":
            self._strategy = MultiIndicatorStrategy(config=MultiIndicatorConfig(
                buy_threshold=0, sell_threshold=4,
                rsi_overbought=90.0, rsi_oversold=10.0,
                macd_fast=8, macd_slow=17, macd_signal=6,
                bb_period=15, bb_std=1.5,
                st_period=7, st_multiplier=2.0,
            ))
        else:
            self._strategy = get_strategy(strategy_name)
        self._positions: dict[str, CryptoPosition] = {}
        self._trades: list[CryptoTrade] = []
        self._equity_curve: list[float] = []
        self._errors: list[str] = []
        self._start_time: float = 0.0
        self._last_optimization: str = "从未"
        self._last_opt_result: dict | None = None
        self._last_fed_ts: dict[str, int] = {}

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._start_time = time.time()
        self._prefill_history()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CryptoBot")
        self._thread.start()

    def _prefill_history(self) -> None:
        """Fetch historical 1m candles from OKX REST API to seed the aggregator."""
        import json as _json
        from urllib import request as _req
        for symbol in self._symbols:
            try:
                url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar=1m&limit=300"
                req = _req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with _req.urlopen(req, timeout=10) as resp:
                    data = _json.loads(resp.read())
                if data.get("code") != "0" or not data.get("data"):
                    continue
                from quant_agent.crypto.base import Candle
                candles = []
                for arr in data["data"]:
                    candle = Candle(
                        inst_id=symbol,
                        ts=int(arr[0]),
                        open=float(arr[1]),
                        high=float(arr[2]),
                        low=float(arr[3]),
                        close=float(arr[4]),
                        vol=float(arr[5]),
                        complete=True,
                    )
                    candles.append(candle)
                candles.sort(key=lambda c: c.ts)
                for c in candles:
                    self._aggregator.feed(c)
                if candles:
                    self._last_fed_ts[symbol] = max(c.ts for c in candles)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._thread = None

    def status(self) -> BotStatus:
        with self._lock:
            equity = self._get_equity()
            positions_list = []
            trailing_stops = {}
            for sym, pos in self._positions.items():
                if pos.is_open:
                    positions_list.append({
                        "symbol": sym,
                        "qty": pos.quantity,
                        "avg_price": pos.average_price,
                        "highest": pos.highest_price,
                    })
                    trailing_stops[sym] = pos.highest_price

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trades_today = sum(1 for t in self._trades if t.date.startswith(today))
            pnl_total = equity - self._starting_cash
            wins = sum(1 for t in self._trades if t.side == "sell" and t.reason.startswith("take profit"))
            sells = sum(1 for t in self._trades if t.side == "sell")
            win_rate = wins / sells if sells > 0 else 0.0

            return BotStatus(
                running=self.running,
                uptime_seconds=time.time() - self._start_time if self.running else 0,
                symbols=self._symbols,
                strategy=self._strategy_name,
                timeframe=self._timeframe,
                equity=equity,
                cash=self._get_cash(),
                positions=positions_list,
                trades_today=trades_today,
                total_trades=len(self._trades),
                pnl_total=pnl_total,
                pnl_today=0.0,
                win_rate=win_rate,
                max_drawdown=self._compute_max_drawdown(),
                trailing_stops=trailing_stops,
                last_optimization=self._last_optimization,
                optimization_result=self._last_opt_result,
                errors=self._errors[-10:],
            )

    def _get_equity(self) -> float:
        try:
            bal = self._broker.get_usdt_balance()
            cash = bal.get("available", 0.0)
            pos_value = sum(
                p.quantity * self._get_current_price(p.symbol, p.average_price)
                for p in self._positions.values() if p.is_open
            )
            return cash + pos_value
        except Exception:
            return self._starting_cash

    def _get_cash(self) -> float:
        try:
            bal = self._broker.get_usdt_balance()
            return bal.get("available", 0.0)
        except Exception:
            return 0.0

    def _get_current_price(self, symbol: str, fallback: float) -> float:
        ticker = self._adapter.store.get_ticker(symbol)
        if ticker and ticker.last > 0:
            return ticker.last
        return fallback

    def _compute_max_drawdown(self) -> float:
        if len(self._equity_curve) < 2:
            return 0.0
        peak = self._equity_curve[0]
        max_dd = 0.0
        for eq in self._equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._sync_positions()
                for symbol in self._symbols:
                    if self._stop_event.is_set():
                        break
                    self._tick(symbol)
                equity = self._get_equity()
                with self._lock:
                    self._equity_curve.append(equity)
                    if len(self._equity_curve) > 10000:
                        self._equity_curve = self._equity_curve[-5000:]
                self._maybe_optimize()
            except Exception as exc:
                with self._lock:
                    self._errors.append(f"[{datetime.now(timezone.utc).strftime('%H:%M')}] {exc}")
                    if len(self._errors) > 50:
                        self._errors = self._errors[-25:]
            self._stop_event.wait(self._check_interval)

    def _tick(self, symbol: str) -> None:
        candles = self._adapter.store.get_candles(symbol, limit=3600)
        new_candles = []
        last_ts = self._last_fed_ts.get(symbol, 0)
        for c in candles:
            if c.ts > last_ts and c.complete:
                new_candles.append(c)
        if new_candles:
            for c in new_candles:
                self._aggregator.feed(c)
            self._last_fed_ts[symbol] = max(c.ts for c in new_candles)

        bars = self._aggregator.get_bars(symbol, self._timeframe)
        if not bars:
            return

        position = self._positions.get(symbol)
        current_price = bars[-1].close

        if position and position.is_open:
            should_sell, reason = self._check_risk_exits(position, current_price)
            if should_sell:
                self._execute_sell(symbol, position.quantity, reason)
                return

        try:
            signal = self._strategy.generate_signal(symbol, bars, position)
        except Exception:
            return

        if signal.target_allocation > 0 and (not position or not position.is_open):
            remaining = self._risk.check_total_allocation(self._positions, self._get_equity())
            if remaining <= 0:
                return
            alloc = min(signal.target_allocation, remaining)
            equity = self._get_equity()
            qty = self._risk.compute_quantity(equity, current_price, alloc)
            if qty > 0:
                self._execute_buy(symbol, qty, signal.reason)

        elif signal.target_allocation == 0 and position and position.is_open:
            self._execute_sell(symbol, position.quantity, signal.reason)

    def _check_risk_exits(self, position: CryptoPosition, current_price: float) -> tuple[bool, str]:
        should, reason = self._risk.check_trailing_stop(position, current_price)
        if should:
            return True, reason
        should, reason = self._risk.check_stop_loss(position, current_price)
        if should:
            return True, reason
        should, reason = self._risk.check_take_profit(position, current_price)
        if should:
            return True, reason
        return False, ""

    def _execute_buy(self, symbol: str, qty: float, reason: str) -> None:
        try:
            price = self._get_current_price(symbol, 0)
            if price <= 0:
                return
            qty_str = f"{qty:.8f}".rstrip("0").rstrip(".")
            result = self._broker.submit_order(symbol, "buy", qty_str, "market")
            if result.get("order_id"):
                with self._lock:
                    existing = self._positions.get(symbol)
                    if existing and existing.is_open:
                        total_qty = existing.quantity + qty
                        existing.average_price = (existing.average_price * existing.quantity + price * qty) / total_qty
                        existing.quantity = total_qty
                    else:
                        self._positions[symbol] = CryptoPosition(
                            symbol=symbol, quantity=qty, average_price=price, highest_price=price,
                        )
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    self._trades.append(CryptoTrade(
                        date=now, symbol=symbol, side="buy", quantity=qty, price=price, reason=reason,
                    ))
        except Exception as exc:
            with self._lock:
                self._errors.append(f"BUY {symbol} error: {exc}")

    def _execute_sell(self, symbol: str, qty: float, reason: str) -> None:
        try:
            price = self._get_current_price(symbol, 0)
            qty_str = f"{qty:.8f}".rstrip("0").rstrip(".")
            result = self._broker.submit_order(symbol, "sell", qty_str, "market")
            if result.get("order_id"):
                with self._lock:
                    pos = self._positions.get(symbol)
                    if pos:
                        pos.quantity = 0.0
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    self._trades.append(CryptoTrade(
                        date=now, symbol=symbol, side="sell", quantity=qty, price=price, reason=reason,
                    ))
        except Exception as exc:
            with self._lock:
                self._errors.append(f"SELL {symbol} error: {exc}")

    def _sync_positions(self) -> None:
        try:
            broker_positions = self._broker.list_positions()
            with self._lock:
                broker_syms = set()
                for bp in broker_positions:
                    sym = bp.get("symbol", "")
                    qty = float(bp.get("qty", 0))
                    if qty <= 0.001 or sym == "USDT" or sym not in self._symbols:
                        continue
                    broker_syms.add(sym)
                    if sym not in self._positions or not self._positions[sym].is_open:
                        ticker = self._adapter.store.get_ticker(sym)
                        if not ticker or ticker.last <= 0:
                            continue
                        current = ticker.last
                        # OKX demo returns avg_entry_price=1.0 for all assets;
                        # always use market price as cost basis to avoid fake PnL triggers.
                        self._positions[sym] = CryptoPosition(
                            symbol=sym, quantity=qty, average_price=current,
                            highest_price=current,
                        )
                    else:
                        self._positions[sym].quantity = qty
                for sym in list(self._positions.keys()):
                    if sym not in broker_syms and self._positions[sym].is_open:
                        self._positions[sym].quantity = 0.0
        except Exception:
            pass

    def _maybe_optimize(self) -> None:
        bars_counts = {s: self._aggregator.candle_count(s, "1h") for s in self._symbols}
        min_bars = min(bars_counts.values()) if bars_counts else 0
        if min_bars < 200:
            return
        threading.Thread(target=self._run_optimization, daemon=True, name="CryptoBot-Opt").start()

    def _run_optimization(self) -> None:
        try:
            bars_by_symbol = {}
            for sym in self._symbols:
                bars = self._aggregator.get_bars(sym, "1h", limit=500)
                if len(bars) < 50:
                    return
                bars_by_symbol[sym] = bars

            config = AppConfig(
                mode="backtest",
                symbols=tuple(self._symbols),
                starting_cash=self._starting_cash,
            )
            from quant_agent.optimizer import optimize_strategy
            result = optimize_strategy(config, bars_by_symbol, strategy_name="multi_indicator")

            if result.best and result.best.train_metrics.total_return > 0:
                params = result.best.candidate.params
                new_config = MultiIndicatorConfig(**params)
                new_strategy = MultiIndicatorStrategy(config=new_config)
                with self._lock:
                    self._strategy = new_strategy
                    self._strategy_name = f"multi_indicator({params})"
                self._last_optimization = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                self._last_opt_result = {
                    "params": params,
                    "train_return": f"{result.best.train_metrics.total_return:.2%}",
                    "test_return": f"{result.best.test_metrics.total_return:.2%}",
                    "train_sharpe": f"{result.best.train_metrics.sharpe_ratio:.2f}",
                }
        except Exception as exc:
            with self._lock:
                self._errors.append(f"Optimization error: {exc}")
