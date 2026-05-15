# US Stock Quant MVP Design

## Goal

Build a first-version US stock quantitative trading system for testing only. The system must support historical backtesting and Alpaca paper trading, with clear strategy logic, explicit risk controls, and trade journaling. It must not place live-money orders by default.

This version optimizes for safety, explainability, and testability over aggressive performance.

## Non-Goals

- No live trading integration in the first version.
- No leverage, short selling, options, futures, or margin behavior.
- No opaque machine-learning prediction model in the first version.
- No AI-only buy or sell decisions. Any AI/agent layer may summarize, explain, or orchestrate, but trade signals must come from deterministic strategy and risk modules.

## Recommended Approach

Use a rule-based long-only strategy engine with a backtest-first workflow:

1. Load daily price data for a small default watchlist.
2. Generate deterministic entry and exit signals using trend and momentum indicators.
3. Apply hard risk limits before any order is allowed.
4. Backtest the full flow and write trade logs.
5. Connect to Alpaca paper trading only after the same logic passes local tests.

This approach is more useful for a first version than a machine-learning model because it is easier to validate, inspect, and improve.

## Default Universe

The default symbol list is:

- SPY
- QQQ
- AAPL
- MSFT
- NVDA

The list will live in configuration and can be changed without editing strategy code.

## Architecture

The first version will be a Python project. It will expose command-line entry points for backtesting first, then paper trading after the local engine passes tests.

Initial commands:

- `python -m quant_agent backtest`
- `python -m quant_agent paper`

The `paper` command must fail with a clear message until Alpaca paper credentials are configured. A `live` command will not exist in the first version.

### Data Module

Responsibilities:

- Fetch historical daily OHLCV data.
- Normalize data into one internal table shape.
- Cache or load local sample data for tests.
- Expose data by symbol and date range.

Initial source:

- Historical data for local backtests may use `yfinance` or another free daily-data provider.
- Paper trading execution will target Alpaca paper trading.

### Strategy Module

Responsibilities:

- Calculate indicators.
- Generate raw target signals.
- Stay deterministic and testable.

Initial strategy:

- Long-only trend following.
- Allow long entries only when short moving average is above long moving average.
- Avoid new entries when RSI indicates overbought conditions.
- Exit when trend turns negative or stop rules are hit by the risk layer.

Default parameters:

- Short moving average: 20 trading days.
- Long moving average: 50 trading days.
- RSI period: 14 trading days.
- RSI entry ceiling: 70.

### Risk Module

Responsibilities:

- Convert raw strategy signals into allowed target positions.
- Enforce portfolio-level limits.
- Enforce symbol-level limits.
- Block orders that violate safety rules.

Default limits:

- Max allocation per symbol: 20%.
- Max total invested allocation: 80%.
- No leverage.
- No short positions.
- Optional stop loss: 8% from entry.
- Optional take profit: 20% from entry.
- Cooldown after exit: 3 trading days before re-entry for the same symbol.

### Backtest Module

Responsibilities:

- Simulate historical trading day by day.
- Apply strategy, risk checks, position accounting, and cash accounting.
- Record every simulated trade.
- Report performance metrics.

Minimum metrics:

- Total return.
- Annualized return.
- Max drawdown.
- Win rate.
- Number of trades.
- Exposure percentage.

### Broker Module

Responsibilities:

- Provide a broker interface that can support paper trading now and live trading later.
- Implement an Alpaca paper broker adapter.
- Reject live trading unless explicitly enabled in configuration in a future version.

First version behavior:

- Paper trading only.
- Market orders or limit orders can be supported, but the default should be simple paper market orders at the next available price.
- API keys must be read from environment variables, never committed to files.

### Agent Module

Responsibilities:

- Run the trading workflow as an orchestrator.
- Produce decision summaries.
- Write a daily trading journal.
- Optionally prepare notifications.

The agent must not override risk controls. It can explain and record decisions, but the risk module has final authority over whether an order is allowed.

### Config Module

Responsibilities:

- Store default symbols, strategy parameters, risk limits, and mode.
- Make the default mode `backtest`.
- Require explicit configuration for `paper`.
- Reserve `live` as unsupported in first version.

### Journal And Logs

Responsibilities:

- Record each run.
- Record each signal and whether it was accepted or blocked.
- Record each simulated or paper trade.
- Record portfolio metrics after each run.

Initial format:

- CSV or JSONL files under a local `logs/` directory.
- Human-readable daily summary in Markdown.

## Data Flow

1. The user runs a command for backtest or paper mode.
2. Configuration is loaded.
3. Market data is fetched or loaded.
4. Strategy generates raw signals.
5. Risk module converts raw signals into approved target positions.
6. Backtest or broker module simulates or places paper orders.
7. Journal module records decisions, trades, and metrics.
8. Agent summary explains what happened and why.

## Safety Rules

- Live trading is not implemented in this version.
- Missing API keys must never crash backtests.
- Missing API keys should only block paper trading.
- Any order that would exceed max symbol allocation or max total allocation is rejected.
- Any order for an unknown symbol is rejected.
- Any negative quantity or short target is rejected.
- Any invalid or stale price data blocks trading for that symbol.

## Testing Plan

Use test-driven development for implementation.

Core tests:

- Strategy creates no signal until enough indicator history exists.
- Strategy creates a long signal when trend is positive and RSI is below the entry ceiling.
- Strategy blocks new long entries when RSI is too high.
- Risk rejects allocations above the symbol limit.
- Risk rejects total exposure above the portfolio limit.
- Backtest accounting updates cash and positions correctly.
- Backtest metrics calculate max drawdown and total return correctly.
- Broker interface defaults to paper-only behavior.
- Config defaults to backtest mode and rejects live mode.

## First Implementation Milestone

The first runnable milestone should include:

- Project scaffold.
- Config file.
- Strategy and risk modules.
- Backtest module.
- Tests for strategy, risk, config, and backtest accounting.
- A command to run a backtest on the default symbol list.
- A generated summary report after each backtest.

Alpaca paper trading should be added only after the local backtest engine and risk controls pass tests.

## Fixed Decisions

The following decisions are fixed for the first version:

- Use Alpaca paper trading when broker integration begins.
- Use a deterministic rule-based strategy.
- Use daily bars, not intraday bars.
- Use long-only positions.
- Start with the five-symbol default universe.

Future versions may add intraday data, richer factor models, portfolio optimization, notifications, or live trading gates.
