# CLAUDE.md

## Quick Start

```bash
# First-time setup
make setup                    # Creates venv, installs deps, seeds DB

# Maverick MCP (port 8003)
make dev                  # SSE transport (recommended)

# Saty API (port 8080)
venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# Tests
venv/bin/pytest tests/satyland/ -v   # Saty (115 tests, no containers, ~0.5s)
make test                             # Maverick unit tests

# Code quality
make check   # = format + lint + typecheck (ruff + ty)
```

## Project Overview

Two complementary trading systems:

- **Maverick MCP** (`maverick_mcp/`): Stock analysis MCP server for Claude Desktop — 520 pre-seeded S&P 500 stocks, technical analysis, screening, portfolio tracking, backtesting (VectorBT), AI research (OpenRouter)
- **Saty API** (`api/`): Exact Python ports of Saty Pine Scripts as REST API — ATR Levels, Pivot Ribbon Pro, Phase Oscillator, Green Flag grading, Schwab integration. Deployed on Railway.

```
Maverick (WHAT to trade) → Saty (WHEN to trade it)
```

## Project Structure

```
maverick_mcp/
├── api/server.py              # FastMCP server
├── api/routers/               # Tool groups (25 routers: data, technical, screening, portfolio, research, backtesting, ...)
├── agents/, workflows/        # Multi-agent orchestration
├── domain/, infrastructure/   # DDD layers
├── config/, core/, data/, providers/, utils/, validation/

api/
├── main.py                    # FastAPI app
├── endpoints/
│   ├── satyland.py            # /api/satyland/* (calculate, trade-plan, price-structure)
│   ├── schwab.py              # /api/schwab/* (quote, options-chain, auth)
│   └── options.py             # /api/options/* (atm-straddle, gamma-exposure)
├── indicators/satyland/
│   ├── atr_levels.py          # Wilder ATR14 + PDC-anchored Fibonacci levels
│   ├── pivot_ribbon.py        # EMA 8/13/21/48/200 + compression tracker
│   ├── phase_oscillator.py    # ATR-normalized momentum oscillator
│   ├── green_flag.py          # A+/A/B/skip trade grading (10 flags)
│   └── price_structure.py     # PDH/PDL/PMH/PML
└── integrations/schwab/       # OAuth2 + token refresh

conductor/                     # Product guidelines & workflow orchestration
scripts/                       # Utility scripts (seed_sp500.py, schwab_auth.py, dev.sh, etc.)
alembic/                       # DB migrations (18 versions)
examples/                      # Usage examples
tests/satyland/                # 115 tests, no external deps
docs/saty_trading_skill.md     # Full Saty reference
docs/*.txt                     # Pine Script ground truth
```

## Environment

```bash
# Required
TIINGO_API_KEY=...             # Maverick data (tiingo.com, free tier)

# Recommended
OPENROUTER_API_KEY=...         # AI research (400+ models)
EXA_API_KEY=...                # Web search for research

# Optional
FRED_API_KEY=...               # Macro data
DATABASE_URL=postgresql://...  # Default: SQLite
REDIS_HOST=localhost           # Default: in-memory cache
TAVILY_API_KEY=...             # Alternative web search
SENTRY_DSN=...                 # Error tracking
CACHE_TTL_SECONDS=300          # Cache expiry (default: 300)

# Saty/Schwab
SCHWAB_CLIENT_ID=...
SCHWAB_CLIENT_SECRET=...
SCHWAB_REDIRECT_URI=https://127.0.0.1
SCHWAB_TOKEN_FILE=/tmp/schwab_tokens.json
ALLOWED_ORIGINS=*
```

## Make Targets

| Command | Action |
|---|---|
| `make dev` / `make d` | SSE server on 8003 (recommended) |
| `make dev-http` / `make dh` | Streamable-HTTP server |
| `make dev-stdio` / `make ds` | STDIO transport |
| `make test` / `make t` | Unit tests |
| `make lint` / `make l` | Ruff linting |
| `make check` / `make c` | All checks (format + lint + typecheck) |
| `make stop` | Stop all services |
| `make migrate` | DB migrations |
| `make redis-start` | Start Redis |

## Claude Desktop Setup

**Recommended**: SSE via mcp-remote (tested, prevents tool disappearing):

```json
{
  "mcpServers": {
    "maverick-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8003/sse"]
    }
  }
}
```

Config location: `~/Library/Application Support/Claude/claude_desktop_config.json`

Other clients (Cursor, Continue.dev, Windsurf) can use direct SSE: `http://localhost:8003/sse`

Claude Code CLI: `claude mcp add --transport sse maverick-mcp http://localhost:8003/sse`

## Saty Indicators

> Full reference: `docs/saty_trading_skill.md` | Pine Script ground truth: `docs/*.txt`

| Indicator | File | Key Output |
|-----------|------|------------|
| ATR Levels | `atr_levels.py` | `pdc`, `atr`, `call_trigger`, `put_trigger`, `levels` (Fib dict), `atr_status`, `trigger_box`, `trend` |
| Pivot Ribbon | `pivot_ribbon.py` | `ribbon_state`, `bias_candle` (green/blue/orange/red/gray), `in_compression`, `conviction_arrow`, `above_200ema` |
| Phase Oscillator | `phase_oscillator.py` | `oscillator`, `phase` (green/red/compression), `current_zone`, `zone_crosses` |
| Green Flag | `green_flag.py` | 10 flags -> score -> grade (A+ >= 5 / A = 4 / B = 3 / skip < 3) |
| Price Structure | `price_structure.py` | PDH/PDL/PMH/PML levels |

**Entry rule**: Wait for blue (bullish pullback) or orange (bearish pullback) bias_candle. Never enter green/red.

### Saty API Endpoints

```
POST /api/satyland/calculate       # ATR Levels + Pivot Ribbon + Phase Oscillator
POST /api/satyland/trade-plan      # Above + Price Structure + Green Flag
POST /api/satyland/price-structure # PDH/PDL/PMH/PML only
POST /api/schwab/quote             # Real-time quote
POST /api/schwab/options-chain     # Options chain
POST /api/options/atm-straddle     # ATM straddle + expected move
POST /api/options/gamma-exposure   # GEX by strike
GET  /api/schwab/auth/url          # Start OAuth2
POST /api/schwab/auth/callback     # Complete OAuth2
```

Request body: `{"ticker":"SPY","timeframe":"5m","direction":"bullish","vix":15.2}`

Timeframes: 1m | 5m | 15m | 1h | 4h | 1d | 1w

## Maverick MCP Tools (39+)

- **Data**: `get_stock_data`, `get_stock_info`, `get_multiple_stocks_data`
- **Technical**: `calculate_sma/ema/rsi/macd/bollinger_bands`, `get_full_technical_analysis`
- **Screening**: `get_maverick_recommendations`, `get_maverick_bear_recommendations`, `get_trending_breakout_recommendations`
- **Research**: `research_comprehensive`, `research_company`, `analyze_market_sentiment`, `coordinate_agents`
- **Portfolio**: `portfolio_add_position`, `portfolio_get_my_portfolio`, `portfolio_remove_position`, `portfolio_clear_portfolio`, `risk_adjusted_analysis`, `compare_tickers`, `portfolio_correlation_analysis`
- **Backtesting**: `run_backtest`, `compare_strategies`, `optimize_strategy`, `analyze_backtest_results`, `get_backtest_report`
- **Market**: `get_market_overview`, `get_watchlist`

## Code Guidelines

### General
- Python 3.12+, type hints, Google-style docstrings
- Use `pandas_ta` for technical indicators
- Register MCP tools with `@mcp.tool()`, return JSON-serializable results

### Saty Indicator Rules (Non-negotiable)
- **Pine Script parity**: Must match `docs/*_pine_script.txt` exactly
- **Wilder ATR**: `ewm(alpha=1/period, adjust=False)` — NOT `ewm(span=period)`
- **Ribbon EMAs**: `ewm(span=N, adjust=False)` — NOT Wilder
- **ATR/PDC from `iloc[-2]`**: Previous settled bar, not forming bar
- **Compression tracker**: Stateful bar-by-bar `for` loop (vectorized = wrong)
- **Phase strings**: `"green"` / `"red"` / `"compression"` — never `"firing_up"` / `"firing_down"`
- **call_trigger/put_trigger**: Top-level keys in atr dict, not nested
- **No yfinance in indicator files**: I/O stays in endpoint layer
- **Test first**: Verify against `tests/satyland/` before committing

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: api` | Run from project root: `cd /Users/krishnaeedula/claude/trend-trading-mcp` |
| `/trade-plan` 500 KeyError | New indicator key not handled in green_flag.py — run `test_green_flag.py` |
| yfinance empty DataFrame | Invalid ticker, or intraday data only available for recent days |
| Server won't start | `make stop && make clean && make dev` |
| Port 8003 in use | `lsof -i :8003` then `make stop` |
| Claude Desktop tools disappear | Use SSE config with mcp-remote (see above) |
| Redis errors | `brew services start redis` or unset `REDIS_HOST` |
| DB errors | `unset DATABASE_URL && make dev` (falls back to SQLite) |
| Missing S&P 500 data | `uv run python scripts/seed_sp500.py` |
| conftest blocks satyland tests | Check `_MAVERICK_AVAILABLE` guard in root `tests/conftest.py` |
