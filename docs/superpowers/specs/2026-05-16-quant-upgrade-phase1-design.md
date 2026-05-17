# Quant Agent Upgrade — Phase 1 Design Spec

**Date**: 2026-05-16
**Scope**: Phase 1 — More indicators/strategies, UI upgrade, financial news

## Overview

Upgrade the existing Alpaca paper trading system with:
1. 4 new technical indicators (MACD, Bollinger Bands, KDJ, SuperTrend)
2. 3 new trading strategies (Grid, DCA, Martingale)
3. Financial news integration (Finnhub API)
4. Complete dashboard redesign (dark trading terminal theme)

## Architecture

**Approach**: Modular Monolith — Flask stays as the single server, Python code modularized, dashboard rebuilt as dark terminal HTML.

**No new framework dependencies** — stays with Flask + vanilla JS + Chart.js.

## Configuration

- Finnhub API key: add `FINNHUB_API_KEY` to `.env` file (same pattern as Alpaca keys)
- `indicators.py` (old flat file): deleted after migration — no compatibility shim needed since all internal
- `strategy.py` (old flat file): deleted after migration to `strategies/trend_rsi.py`

## Module Structure

```
quant_agent/
├── __init__.py
├── __main__.py              # CLI (expanded with new commands)
├── config.py                # Keep
├── models.py                # Keep
├── indicators/              # NEW — one file per indicator
│   ├── __init__.py
│   ├── sma.py               # Move from indicators.py
│   ├── rsi.py               # Move from indicators.py
│   ├── macd.py              # NEW
│   ├── bollinger.py         # NEW
│   ├── kdj.py               # NEW
│   └── supertrend.py        # NEW
├── strategies/              # NEW — one file per strategy
│   ├── __init__.py
│   ├── base.py              # Strategy protocol/interface
│   ├── trend_rsi.py         # Move from strategy.py
│   ├── grid.py              # NEW
│   ├── dca.py               # NEW
│   └── martingale.py        # NEW
├── news/                    # NEW
│   ├── __init__.py
│   └── finnhub.py           # Finnhub API client
├── broker.py                # Keep
├── market_data.py           # Keep
├── market_clock.py          # Keep
├── backtest.py              # Updated: strategy selection
├── optimizer.py             # Keep
├── trading_cycle.py         # Updated: strategy selection + safety checks
├── screener.py              # Keep
├── universe.py              # Keep
├── risk.py                  # Keep
├── journal.py               # Keep
├── sample_data.py           # Keep
├── server.py                # Expanded with new endpoints
└── static/
    └── dashboard.html       # Rebuilt — dark terminal theme
```

## Indicators

### Existing (refactored into separate files)

**SMA** — Simple Moving Average
- Function: `sma(values: list[float], window: int) -> float | None`
- Moved from `indicators.py` to `indicators/sma.py`

**RSI** — Relative Strength Index
- Function: `rsi(values: list[float], period: int) -> float | None`
- Moved from `indicators.py` to `indicators/rsi.py`

### New

**MACD** — Moving Average Convergence Divergence
- File: `indicators/macd.py`
- Function: `macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float] | None`
- Returns: (macd_line, signal_line, histogram)
- Uses EMA internally

**Bollinger Bands**
- File: `indicators/bollinger.py`
- Function: `bollinger_bands(closes: list[float], period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float] | None`
- Returns: (upper, middle, lower)
- Also provide `bollinger_percent_b()` and `bollinger_bandwidth()` helpers

**KDJ** — Stochastic Oscillator Variant
- File: `indicators/kdj.py`
- Function: `kdj(highs: list[float], lows: list[float], closes: list[float], k_period: int = 9, d_period: int = 3, j_period: int = 3) -> tuple[float, float, float] | None`
- Returns: (K, D, J)

**SuperTrend**
- File: `indicators/supertrend.py`
- Function: `supertrend(highs: list[float], lows: list[float], closes: list[float], period: int = 10, multiplier: float = 3.0) -> tuple[float, int] | None`
- Returns: (supertrend_value, direction) where direction is 1 (up/bullish) or -1 (down/bearish)

## Strategies

### Interface

All strategies implement the same protocol:

```python
class Strategy(Protocol):
    name: str
    allows_live_trading: bool

    def generate_signal(
        self, symbol: str, bars: list[Bar], existing_position: Position | None
    ) -> Signal: ...
```

### Safety Rules

| Strategy     | Backtest | Paper Preview | Paper Submit |
|-------------|----------|---------------|--------------|
| TrendRsi    | Yes      | Yes           | Yes          |
| DCA         | Yes      | Yes           | Yes          |
| Grid        | Yes      | Yes           | **No** (disabled by default) |
| Martingale  | Yes      | Yes           | **No** (disabled by default) |

- `allows_live_trading = False` for Grid and Martingale
- `submit=true` is **never the default** — always requires explicit opt-in
- Live trading mode is permanently blocked (`reject_live_mode()`)
- Grid/Martingale can be enabled for paper submit only by setting `allow_dangerous_strategies=True` in config

### Existing (refactored)

**TrendRsiStrategy** — moved to `strategies/trend_rsi.py`
- `allows_live_trading = True`

### New

**Grid Trading** — `strategies/grid.py`
- `allows_live_trading = False`
- Config: `grid_count=10`, `lower_price`, `upper_price`
- Price range: auto-calculated from recent 52-week high/low if not specified
- Logic: calculate grid levels, buy at lower bands, sell at upper bands
- Signal generation: compare current price to grid levels

**DCA (Dollar Cost Averaging)** — `strategies/dca.py`
- `allows_live_trading = True`
- Config: `interval_days=7`, `amount_per_buy=1000`
- Logic: buy at fixed intervals regardless of price
- Simple and safe for long-term accumulation

**Martingale (Modified)** — `strategies/martingale.py`
- `allows_live_trading = False`
- Config: `base_allocation=0.05`, `max_doubles=3`
- Modified with hard stop-loss at `max_doubles` to prevent ruin
- Logic: double allocation after loss, reset on win, cap at max

## Financial News

### Finnhub Integration

- File: `news/finnhub.py`
- API Base: `https://finnhub.io/api/v1`
- Endpoints used:
  - `/company-news?symbol={symbol}&from={date}&to={date}` — company-specific
  - `/news?category=general` — market-wide news
- Rate limit: 60 calls/minute (free tier)
- Cache: 15-minute TTL to stay within limits

### News Client

```python
class FinnhubClient:
    def __init__(self, api_key: str): ...
    def fetch_market_news(self, category: str = "general") -> list[NewsItem]: ...
    def fetch_company_news(self, symbol: str, days_back: int = 7) -> list[NewsItem]: ...
```

### Data Model

```python
@dataclass
class NewsItem:
    headline: str
    source: str
    url: str
    summary: str
    datetime: str  # ISO format
    image: str | None
```

## Dashboard Redesign

### Design System

**Color Tokens** (dark trading terminal):
- `--bg-primary`: #0f1117 (near-black background)
- `--bg-card`: #1a1d29 (dark card surfaces)
- `--bg-elevated`: #242736 (hover/active states)
- `--text-primary`: #e2e8f0 (high contrast text, 12.6:1 on bg-primary)
- `--text-secondary`: #94a3b8 (muted labels, 5.7:1 on bg-primary)
- `--accent-blue`: #3b82f6 (primary actions)
- `--accent-green`: #22c55e (positive/PnL)
- `--accent-red`: #ef4444 (negative/loss)
- `--border`: #2d3148 (subtle dividers)

**Typography**:
- Font: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
- Monospace: "JetBrains Mono", "SF Mono", monospace (for numbers)
- Base: 14px, line-height 1.5
- `font-variant-numeric: tabular-nums` for data columns

### Layout

```
┌──────────────────────────────────────────────────┐
│  ◉ QUANT AGENT        $127,450  +$2,340 (+1.87%) │  ← Top bar
├──────────────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │  ← Metrics row
│  │Equity│ │Return│ │MaxDD │ │WinRt │ │Trades│  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
├──────────────────────────────────────────────────┤
│  ┌────────────────────┐ ┌──────────────────┐    │  ← Main grid
│  │  Equity Curve      │ │  Positions       │    │
│  │  ████████████████  │ │  AAPL  +3.2%     │    │
│  │  ▓▓▓▓▓▓▓▓▓▓▓      │ │  NVDA  +5.1%     │    │
│  │                    │ │                  │    │
│  ├────────────────────┤ ├──────────────────┤    │
│  │  Trade Log         │ │  Market News     │    │
│  │  Date | Sym | Side │ │  • Fed holds...  │    │
│  │  ...               │ │  • NVDA beats... │    │
│  └────────────────────┘ └──────────────────┘    │
├──────────────────────────────────────────────────┤
│  Strategy: [TrendRsi ▼]  Timeframe: [1Day ▼]    │  ← Controls
│  [Run Backtest]  [Run Cycle]  [Refresh Account]  │
└──────────────────────────────────────────────────┘
```

### UX Rules Applied

- All touch targets ≥44px
- Color + icon (never color alone) for buy/sell signals
- Loading skeleton states for async data
- Contrast ≥4.5:1 for all text
- No emoji icons — use SVG (Lucide icons)
- Tabular numbers for data columns
- Auto-dismiss toasts (3-5s)
- Responsive: 2-column on desktop, 1-column on mobile

## API Endpoints

### Existing (keep as-is)

- `GET /api/backtest` — run backtest (enhanced with `?strategy=` param)
- `GET /api/optimize` — run optimization
- `POST /api/paper-cycle` — run paper trading cycle (enhanced with `?strategy=` param)
- `GET /api/account` — account info
- `GET /api/positions` — open positions
- `GET /api/orders` — open orders

### New

- `GET /api/news` — general market news
- `GET /api/news?symbol=AAPL` — symbol-specific news
- `GET /api/indicators?symbol=AAPL` — all indicator values for a symbol
- `GET /api/strategies` — list available strategies with status (enabled/disabled/allows_live)

### Strategy Selection

`GET /api/backtest?strategy=grid` and `POST /api/paper-cycle` with `{"strategy": "grid"}`

Default: `trend_rsi`. Options: `trend_rsi`, `grid`, `dca`, `martingale`.

Safety enforcement in `trading_cycle.py`:
- If `submit=true` and strategy `allows_live_trading=False` → reject with error
- If `allow_dangerous_strategies=True` in config → allow

## Implementation Order

1. **Indicators** — MACD, Bollinger, KDJ, SuperTrend (pure functions, easy to test)
2. **Strategies** — Grid, DCA, Martingale with safety flags
3. **News module** — Finnhub client + caching
4. **Server expansion** — New API endpoints
5. **Dashboard rebuild** — Dark terminal theme with all new sections

## Out of Scope (Phase 2)

- Crypto trading (Binance API)
- Real-time stop-loss/take-profit monitoring
- Auto-scheduled trading (cron/scheduler)
- WebSocket live price streaming
