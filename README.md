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

## Paper Mode

```powershell
$env:PYTHONPATH = "src"
$env:ALPACA_API_KEY = "your-paper-key"
$env:ALPACA_SECRET_KEY = "your-paper-secret"
& "C:\Users\Ethan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m quant_agent paper
```

Paper mode checks `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. This milestone does not place paper orders yet.
