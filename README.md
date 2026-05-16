# Quant Agent

Testing-only US stock quant MVP.

## Safety

- First version does not implement live trading.
- Default command is local backtesting.
- Paper trading requires Alpaca paper credentials.
- Strategy signals are deterministic and risk-checked.

## Run Tests

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest -v
```

## Run Backtest

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent backtest
```

Outputs are written to `logs/backtest-summary.md` and `logs/backtest-metrics.json` unless `QUANT_AGENT_LOG_DIR` is set.

## Optimize Strategy

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent optimize
```

Optimization uses a train/test split and writes `logs/optimization-summary.md` plus `logs/optimization-results.json`.

## Paper Mode

```powershell
$env:PYTHONPATH = "src"
$env:ALPACA_API_KEY = "your-paper-key"
$env:ALPACA_SECRET_KEY = "your-paper-secret"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent paper
```

Paper mode checks `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. This milestone does not place paper orders yet.

## Paper Order Preview

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent paper-preview --symbol SPY --qty 1 --side buy
```

Preview does not require credentials and does not call the broker.

## Submit Paper Order

```powershell
$env:PYTHONPATH = "src"
$env:ALPACA_API_KEY = "your-paper-key"
$env:ALPACA_SECRET_KEY = "your-paper-secret"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent paper-submit --symbol SPY --qty 1 --side buy
```

`paper-submit` uses Alpaca's paper trading endpoint, checks Alpaca's market clock before submitting, and blocks a new order when the same symbol and side already has an open paper order. There is still no live trading command.

## Paper Market Clock

```powershell
$env:PYTHONPATH = "src"
$env:ALPACA_API_KEY = "your-paper-key"
$env:ALPACA_SECRET_KEY = "your-paper-secret"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent paper-clock
```

The clock command reads Alpaca's paper trading clock and reports whether the regular market is open.

## Market Data Preview

```powershell
$env:PYTHONPATH = "src"
$env:ALPACA_API_KEY = "your-paper-key"
$env:ALPACA_SECRET_KEY = "your-paper-secret"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent data-preview --symbol SPY --timeframe 1Min --start 2025-01-01T14:30:00Z --end 2025-01-01T15:30:00Z
```

Supported bars are `1Min`, `5Min`, `15Min`, `30Min`, `1Hour`, and `1Day`. The current strategy still defaults to daily bars for backtests; minute bars are available for preview and the next paper-trading loop.

## Paper Account Sync

The broker adapter can read the Alpaca paper account, current positions, and open orders before submitting a paper order. This lets the next dashboard show buying power, holdings, pending orders, and order-blocking reasons.
