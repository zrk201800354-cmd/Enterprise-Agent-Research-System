from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MonitorStatus:
    running: bool = False
    auto_execute: bool = False
    last_check: str = ""
    last_cycle: str = ""
    cycle_count: int = 0
    stop_loss_triggers: int = 0
    take_profit_triggers: int = 0
    orders_executed: int = 0
    alerts: list[dict[str, Any]] = field(default_factory=list)
    executed_orders: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class TradingMonitor:
    """Background monitor for stop-loss/take-profit and scheduled trading cycles."""

    def __init__(
        self,
        broker: Any = None,
        market_data: Any = None,
        config: Any = None,
        strategy: Any = None,
        check_interval: int = 60,
        stop_loss_pct: float = 0.08,
        take_profit_pct: float = 0.20,
        auto_execute: bool = False,
    ) -> None:
        self._broker = broker
        self._market_data = market_data
        self._config = config
        self._strategy = strategy
        self._check_interval = check_interval
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._auto_execute = auto_execute
        self._status = MonitorStatus(auto_execute=auto_execute)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._sold_symbols: set[str] = set()  # prevent duplicate sells in same session

    @property
    def status(self) -> MonitorStatus:
        return self._status

    def set_auto_execute(self, enabled: bool) -> None:
        self._auto_execute = enabled
        self._status.auto_execute = enabled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._status.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._status.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_positions()
                self._status.last_check = datetime.now().isoformat()
            except Exception as exc:
                self._status.errors.append(f"{datetime.now().strftime('%H:%M:%S')}: {str(exc)}")
                if len(self._status.errors) > 20:
                    self._status.errors = self._status.errors[-10:]
            self._stop_event.wait(self._check_interval)

    def _execute_sell(self, symbol: str, qty: float, reason: str, pnl_pct: float) -> dict[str, Any] | None:
        """Submit a market sell order for the given symbol."""
        if not self._broker:
            return None
        if symbol in self._sold_symbols:
            return None  # already sold this symbol this session
        try:
            from quant_agent.broker import BrokerOrder
            order = BrokerOrder(symbol=symbol, qty=qty, side="sell")
            result = self._broker.submit_order_if_no_duplicate(order)
            self._sold_symbols.add(symbol)
            exec_record = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": symbol,
                "qty": qty,
                "side": "sell",
                "reason": reason,
                "pnl_pct": round(pnl_pct * 100, 2),
                "order_id": str(result.get("id", "")),
                "status": str(result.get("status", "submitted")),
            }
            self._status.executed_orders.append(exec_record)
            if len(self._status.executed_orders) > 50:
                self._status.executed_orders = self._status.executed_orders[-30:]
            self._status.orders_executed += 1
            return result
        except Exception as exc:
            self._status.errors.append(
                f"{datetime.now().strftime('%H:%M:%S')}: 卖出失败 {symbol}: {exc}"
            )
            return None

    def _check_positions(self) -> None:
        if not self._broker:
            return
        try:
            positions = self._broker.list_positions()
        except Exception:
            return

        for pos in positions:
            symbol = str(pos.get("symbol", ""))
            qty = float(pos.get("qty", 0))
            if qty <= 0:
                continue
            entry = float(pos.get("avg_entry_price", 0))
            current = float(pos.get("current_price", 0))
            if current <= 0 and qty > 0:
                current = float(pos.get("market_value", 0)) / qty
            if entry <= 0 or current <= 0:
                continue

            pnl_pct = (current - entry) / entry
            triggered = False
            reason = ""

            if pnl_pct <= -self._stop_loss_pct:
                self._status.stop_loss_triggers += 1
                triggered = True
                reason = "stop_loss"
                self._status.alerts.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "stop_loss",
                    "symbol": symbol,
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "message": f"止损触发: {symbol} 亏损 {pnl_pct:.1%}",
                })
            elif pnl_pct >= self._take_profit_pct:
                self._status.take_profit_triggers += 1
                triggered = True
                reason = "take_profit"
                self._status.alerts.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "take_profit",
                    "symbol": symbol,
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "message": f"止盈触发: {symbol} 盈利 {pnl_pct:.1%}",
                })

            if triggered and self._auto_execute and symbol not in self._sold_symbols:
                self._execute_sell(symbol, qty, reason, pnl_pct)

        if len(self._status.alerts) > 50:
            self._status.alerts = self._status.alerts[-30:]

    def run_cycle_once(self) -> dict[str, Any] | None:
        if not self._broker or not self._market_data or not self._config:
            return None
        try:
            from quant_agent.trading_cycle import PaperTradingCycle
            cycle = PaperTradingCycle(
                self._config, self._broker, self._market_data, strategy=self._strategy,
            )
            result = cycle.run("2025-01-01", "2025-12-31", timeframe="1Day", submit_orders=False)
            self._status.last_cycle = datetime.now().isoformat()
            self._status.cycle_count += 1
            return asdict(result)
        except Exception as exc:
            self._status.errors.append(f"Cycle error: {exc}")
            return None
