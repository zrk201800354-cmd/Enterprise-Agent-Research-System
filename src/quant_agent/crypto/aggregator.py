from __future__ import annotations

import threading

from quant_agent.crypto.base import Candle
from quant_agent.crypto.models import candle_to_bar
from quant_agent.models import Bar


class CandleAggregator:
    """Aggregates 1m candles into 5m, 15m, 1h timeframes."""

    INTERVALS = {
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
    }

    def __init__(self, max_per_tf: int = 500) -> None:
        self._candles: dict[str, dict[str, list[Candle]]] = {}
        self._current: dict[str, dict[str, Candle | None]] = {}
        self._last_ts: dict[str, int] = {}
        self._max = max_per_tf
        self._lock = threading.Lock()

    def feed(self, candle: Candle) -> None:
        if not candle.complete:
            return
        with self._lock:
            last = self._last_ts.get(candle.inst_id, 0)
            if candle.ts <= last:
                return
            self._last_ts[candle.inst_id] = candle.ts

            for tf_name, interval_ms in self.INTERVALS.items():
                bucket_ts = (candle.ts // interval_ms) * interval_ms
                cur = self._current.setdefault(candle.inst_id, {}).get(tf_name)

                if cur is not None and cur.ts == bucket_ts:
                    self._current[candle.inst_id][tf_name] = Candle(
                        inst_id=candle.inst_id,
                        ts=cur.ts,
                        open=cur.open,
                        high=max(cur.high, candle.high),
                        low=min(cur.low, candle.low),
                        close=candle.close,
                        vol=cur.vol + candle.vol,
                        complete=False,
                    )
                else:
                    if cur is not None:
                        finalized = Candle(
                            inst_id=cur.inst_id,
                            ts=cur.ts,
                            open=cur.open,
                            high=cur.high,
                            low=cur.low,
                            close=cur.close,
                            vol=cur.vol,
                            complete=True,
                        )
                        buf = self._candles.setdefault(candle.inst_id, {}).setdefault(tf_name, [])
                        buf.append(finalized)
                        if len(buf) > self._max:
                            self._candles[candle.inst_id][tf_name] = buf[-self._max:]
                    self._current[candle.inst_id][tf_name] = Candle(
                        inst_id=candle.inst_id,
                        ts=bucket_ts,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        vol=candle.vol,
                        complete=False,
                    )

    def get_candles(self, inst_id: str, timeframe: str, limit: int = 200) -> list[Candle]:
        with self._lock:
            buf = self._candles.get(inst_id, {}).get(timeframe, [])
            return list(buf[-limit:])

    def get_bars(self, inst_id: str, timeframe: str, limit: int = 200) -> list[Bar]:
        return [candle_to_bar(c) for c in self.get_candles(inst_id, timeframe, limit)]

    def candle_count(self, inst_id: str, timeframe: str) -> int:
        with self._lock:
            return len(self._candles.get(inst_id, {}).get(timeframe, []))
