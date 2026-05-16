from __future__ import annotations

from dataclasses import dataclass

from quant_agent.config import AppConfig
from quant_agent.models import BacktestMetrics, Bar, Position, Trade
from quant_agent.risk import RiskManager
from quant_agent.strategy import TrendRsiStrategy


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_equity: float
    trades: list[Trade]
    equity_curve: list[float]
    metrics: BacktestMetrics


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = (equity - peak) / peak
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


class Backtester:
    def __init__(self, config: AppConfig, strategy=None) -> None:
        self.config = config
        self.strategy = strategy or TrendRsiStrategy(config.strategy)
        self.risk = RiskManager(config.risk, allowed_symbols=list(config.symbols))

    def run(self, bars_by_symbol: dict[str, list[Bar]]) -> BacktestResult:
        self._validate_bars(bars_by_symbol)

        bar_count = len(bars_by_symbol[self.config.symbols[0]])
        cash = self.config.starting_cash
        positions: dict[str, Position] = {}
        trades: list[Trade] = []
        equity_curve: list[float] = []
        invested_days = 0
        sell_count = 0
        winning_sell_count = 0

        for index in range(bar_count):
            latest_prices = {symbol: bars_by_symbol[symbol][index].close for symbol in self.config.symbols}
            equity = self._equity(cash, positions, latest_prices)

            for symbol in self.config.symbols:
                bars = bars_by_symbol[symbol][: index + 1]
                signal = self.strategy.generate_signal(symbol, bars, positions.get(symbol))
                allocations = self._allocations(positions, latest_prices, equity)
                decision = self.risk.approve(signal, allocations, positions)
                if not decision.approved:
                    continue

                current_position = positions.get(symbol)
                price = latest_prices[symbol]
                target_value = decision.target_allocation * equity
                current_value = 0.0 if current_position is None else current_position.quantity * price
                delta_value = target_value - current_value

                if delta_value > 0:
                    quantity = int(delta_value // price)
                    if quantity == 0:
                        continue
                    cash = self._buy(cash, positions, trades, bars[-1], symbol, quantity, price, decision.reason)
                elif current_position is not None:
                    quantity = current_position.quantity if decision.target_allocation == 0.0 else int(abs(delta_value) // price)
                    if quantity == 0:
                        continue
                    if price > current_position.average_price:
                        winning_sell_count += 1
                    sell_count += 1
                    cash = self._sell(cash, positions, trades, bars[-1], symbol, quantity, price, decision.reason)

                equity = self._equity(cash, positions, latest_prices)

            end_equity = self._equity(cash, positions, latest_prices)
            equity_curve.append(end_equity)
            if positions:
                invested_days += 1

        metrics = self._metrics(equity_curve, trades, invested_days, sell_count, winning_sell_count)
        return BacktestResult(
            initial_cash=self.config.starting_cash,
            final_equity=equity_curve[-1] if equity_curve else self.config.starting_cash,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    def _validate_bars(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        for symbol in self.config.symbols:
            if symbol not in bars_by_symbol or not bars_by_symbol[symbol]:
                raise ValueError(f"Missing bars for {symbol}")

        expected_count = len(bars_by_symbol[self.config.symbols[0]])
        for symbol in self.config.symbols:
            if len(bars_by_symbol[symbol]) != expected_count:
                raise ValueError("All symbols must have same number of bars")

        baseline_symbol = self.config.symbols[0]
        for index, expected_bar in enumerate(bars_by_symbol[baseline_symbol]):
            for symbol in self.config.symbols[1:]:
                bar = bars_by_symbol[symbol][index]
                if bar.date != expected_bar.date:
                    raise ValueError(
                        f"Mismatched bar date for {symbol} at index {index}: "
                        f"expected {expected_bar.date}, got {bar.date}"
                    )

    def _buy(
        self,
        cash: float,
        positions: dict[str, Position],
        trades: list[Trade],
        bar: Bar,
        symbol: str,
        quantity: int,
        price: float,
        reason: str,
    ) -> float:
        cost = quantity * price
        if cost > cash:
            return cash

        current_position = positions.get(symbol)
        previous_quantity = current_position.quantity if current_position else 0
        previous_cost = current_position.average_price * previous_quantity if current_position else 0.0
        new_quantity = previous_quantity + quantity
        average_price = (previous_cost + cost) / new_quantity
        positions[symbol] = Position(symbol=symbol, quantity=new_quantity, average_price=average_price)
        trades.append(Trade(bar.date, symbol, "BUY", quantity, price, reason))
        return cash - cost

    def _sell(
        self,
        cash: float,
        positions: dict[str, Position],
        trades: list[Trade],
        bar: Bar,
        symbol: str,
        quantity: int,
        price: float,
        reason: str,
    ) -> float:
        current_position = positions[symbol]
        sell_quantity = min(quantity, current_position.quantity)
        remaining = current_position.quantity - sell_quantity

        if remaining:
            positions[symbol] = Position(symbol=symbol, quantity=remaining, average_price=current_position.average_price)
        else:
            positions.pop(symbol)

        trades.append(Trade(bar.date, symbol, "SELL", sell_quantity, price, reason))
        return cash + sell_quantity * price

    def _equity(self, cash: float, positions: dict[str, Position], prices: dict[str, float]) -> float:
        return cash + sum(position.quantity * prices[symbol] for symbol, position in positions.items())

    def _allocations(self, positions: dict[str, Position], prices: dict[str, float], equity: float) -> dict[str, float]:
        if equity <= 0:
            return {}
        return {symbol: position.quantity * prices[symbol] / equity for symbol, position in positions.items()}

    def _metrics(
        self,
        equity_curve: list[float],
        trades: list[Trade],
        invested_days: int,
        sell_count: int,
        winning_sell_count: int,
    ) -> BacktestMetrics:
        if not equity_curve:
            return BacktestMetrics(0.0, 0.0, 0.0, 0.0, 0, 0.0)

        total_return = equity_curve[-1] / self.config.starting_cash - 1.0
        years = max(len(equity_curve) / 252.0, 1 / 252.0)
        annualized_return = (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1.0 else -1.0
        exposure = invested_days / len(equity_curve)
        win_rate = winning_sell_count / sell_count if sell_count else 0.0
        return BacktestMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=calculate_max_drawdown(equity_curve),
            win_rate=win_rate,
            trade_count=len(trades),
            exposure=exposure,
        )
