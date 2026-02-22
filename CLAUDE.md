# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the MaverickMCP + Saty Trading System codebase.

**🚀 QUICK START (Maverick MCP)**: Run `make dev` to start the MCP server. Connect with Claude Desktop using `mcp-remote`. See "Claude Desktop Setup" section below.

**🚀 QUICK START (Saty API)**: Run `venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload` to start the Saty indicator REST API. See "Saty Trading System" section below.

## Project Overview

This repository contains **two complementary trading systems** that can be used independently or combined:

### System 1: MaverickMCP (Claude Desktop MCP Server)

A personal stock analysis MCP server for Claude Desktop:

- Pre-seeded database with all 520 S&P 500 stocks and screening recommendations
- Real-time and historical stock data access with intelligent caching
- Advanced technical analysis tools (RSI, MACD, Bollinger Bands, etc.)
- Multiple stock screening strategies (Maverick Bullish/Bearish, Supply/Demand Breakouts)
- **Personal portfolio tracking with cost basis averaging and live P&L**
- Portfolio optimization and correlation analysis with auto-detection
- Market and macroeconomic data integration
- SQLAlchemy-based database integration with SQLite default (PostgreSQL optional)
- Redis caching for high performance (optional)
- Clean, personal-use architecture without authentication complexity

### System 2: Saty Trading System (FastAPI REST Server)

An exact Python port of the Saty Trading System Pine Scripts, exposing indicators as a REST API:

- **Saty ATR Levels**: Dynamic support/resistance map anchored to Previous Day Close (PDC) with Fibonacci multiples of ATR
- **Saty Pivot Ribbon Pro**: EMA 8/13/21/48/200 trend engine with 4-color bias candle logic and compression detection
- **Saty Phase Oscillator**: ATR-normalized momentum oscillator with zone classification and cross signals
- **Price Structure Levels**: PDH/PDL/PMH/PML structural bias for every session
- **Green Flag Checklist**: A+/A/B/skip trade grading (9 setups × 10 confirmation flags)
- Deployed separately on Railway; no Tiingo/Redis/PostgreSQL dependency

### Integration Vision

Use the systems together for a complete trading workflow:
```
Maverick (WHAT to trade)  →  Saty (WHEN to trade it)
Screening + macro context  →  Indicator timing + entry grading
```

## Project Structure

### Maverick MCP (`maverick_mcp/`)
- `api/`: MCP server implementation
  - `server.py`: Main FastMCP server (simple stock analysis mode)
  - `routers/`: Domain-specific routers for organized tool groups
- `config/`: Configuration and settings
- `core/`: Core financial analysis functions
- `data/`: Data handling, caching, and database models
- `providers/`: Stock, market, and macro data providers
- `utils/`: Development utilities and performance optimizations
- `validation/`: Request/response validation

### Saty Trading System (`api/`)
- `main.py`: FastAPI app with CORS, mounts all routers
- `endpoints/`
  - `satyland.py`: `/api/satyland/*` — ATR Levels, Pivot Ribbon, Phase Oscillator, Trade Plan, Price Structure
  - `schwab.py`: `/api/schwab/*` — Schwab OAuth2 + real-time quotes + options chain
  - `options.py`: `/api/options/*` — ATM straddle, gamma exposure (GEX)
- `indicators/satyland/`
  - `atr_levels.py`: Wilder ATR14 + PDC-anchored Fibonacci levels (exact Pine Script port)
  - `pivot_ribbon.py`: EMA 8/13/21/48/200 + compression tracker (exact Pine Script port)
  - `phase_oscillator.py`: ATR-normalized oscillator + zone crosses (exact Pine Script port)
  - `green_flag.py`: A+/A/B/skip trade confirmation checklist
  - `price_structure.py`: PDH/PDL/PMH/PML structural bias
- `integrations/schwab/`: SchwabClient + OAuth2 token refresh
- `tests/satyland/`: 115 tests, no external dependencies — `venv/bin/pytest tests/satyland/`

### Shared
- `tests/`: Maverick test suite (requires postgres/redis containers)
- `docs/`: Architecture docs + **`saty_trading_skill.md`** (full Saty system reference)
- `docs/*.txt`: Pine Script source files used as ground truth for Python ports
- `scripts/`: Startup and utility scripts
- `Makefile`: Central command interface for Maverick

## Environment Setup

1. **Prerequisites**:

   - **Python 3.12+**: Core runtime environment
   - **[uv](https://docs.astral.sh/uv/)**: Modern Python package manager (recommended)
   - Redis server (optional, for enhanced caching performance)
   - PostgreSQL (optional, SQLite works fine for personal use)

2. **Installation**:

   ```bash
   # Clone the repository
   git clone https://github.com/wshobson/maverick-mcp.git
   cd maverick-mcp

   # Install dependencies using uv (recommended - fastest)
   uv sync

   # Or use traditional pip
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .

   # Set up environment
   cp .env.example .env
   # Add your Tiingo API key (required)
   ```

3. **Required Configuration** (add to `.env`):

   ```
   # Required - Stock data provider (free tier available)
   TIINGO_API_KEY=your-tiingo-key
   ```

4. **Optional Configuration** (add to `.env`):

   ```
   # OpenRouter API (strongly recommended for research - access to 400+ AI models with intelligent cost optimization)
   OPENROUTER_API_KEY=your-openrouter-key
   
   # Web Search API (recommended for research features)
   EXA_API_KEY=your-exa-key

   # Enhanced data providers (optional)
   FRED_API_KEY=your-fred-key

   # Database (optional - uses SQLite by default)
   DATABASE_URL=postgresql://localhost/maverick_mcp

   # Redis (optional - works without caching)
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

   **Get a free Tiingo API key**: Sign up at [tiingo.com](https://tiingo.com) - free tier includes 500 requests/day.

   **OpenRouter API (Recommended)**: Sign up at [openrouter.ai](https://openrouter.ai) for access to 400+ AI models with intelligent cost optimization. The system automatically selects optimal models based on task requirements.

## Quick Start Commands

### Saty API Server

```bash
# Start Saty REST API (port 8080)
venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# Run Saty test suite (no containers needed)
venv/bin/pytest tests/satyland/ -v

# Quick smoke test (server must be running)
curl -s -X POST http://localhost:8080/api/satyland/calculate \
  -H "Content-Type: application/json" \
  -d '{"ticker":"SPY","timeframe":"5m"}' | python3 -m json.tool

# Full trade plan with Green Flag grade
curl -s -X POST http://localhost:8080/api/satyland/trade-plan \
  -H "Content-Type: application/json" \
  -d '{"ticker":"SPY","timeframe":"5m","direction":"bullish","vix":15.2}' \
  | python3 -m json.tool | grep grade
```

### Maverick MCP Commands (Powered by Makefile)

```bash
# Start the MCP server
make dev              # Start with SSE transport (default, recommended)
make dev-sse          # Start with SSE transport (same as dev)
make dev-http         # Start with Streamable-HTTP transport (for testing/debugging)
make dev-stdio        # Start with STDIO transport (direct connection)

# Development
make backend          # Start backend server only
make tail-log         # Follow logs in real-time
make stop             # Stop all services

# Testing
make test             # Run unit tests (5-10 seconds)
make test-watch       # Auto-run tests on file changes
make test-cov         # Run with coverage report

# Code Quality
make lint             # Check code quality
make format           # Auto-format code
make typecheck        # Run type checking
make check            # Run all checks

# Database
make migrate          # Run database migrations
make setup            # Initial setup

# Utilities
make clean            # Clean up generated files
make redis-start      # Start Redis (if using caching)

# Quick shortcuts
make d                # Alias for make dev
make dh               # Alias for make dev-http
make ds               # Alias for make dev-stdio
make t                # Alias for make test
make l                # Alias for make lint
make c                # Alias for make check
```

## Claude Desktop Setup

### Connection Methods

**✅ RECOMMENDED**: Claude Desktop works best with the **SSE endpoint via mcp-remote bridge**. This configuration has been tested and **prevents tools from disappearing** after initial connection.

#### Method A: SSE Server with mcp-remote Bridge (Recommended - Stable)

This is the **tested and proven method for Claude Desktop** - provides stable tool registration:

1. **Start the SSE server**:
   ```bash
   make dev  # Runs SSE server on port 8003
   ```

2. **Configure with mcp-remote bridge**:
   Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

**Why This Configuration Works Best**:
- ✅ **Prevents Tool Disappearing**: Tools remain available throughout your session
- ✅ **Stable Connection**: SSE transport provides consistent communication
- ✅ **Session Persistence**: Maintains connection state for complex analysis workflows
- ✅ **All 35+ Tools Available**: Reliable access to all financial and research tools
- ✅ **Tested and Confirmed**: This exact configuration has been verified to work
- ✅ **No Trailing Slash Issues**: Server automatically handles both `/sse` and `/sse/` paths

#### Method B: HTTP Streamable Server with mcp-remote Bridge (Alternative)
   
1. **Start the HTTP Streamable server**:
   ```bash
   make dev  # Runs HTTP streamable server on port 8003
   ```

2. **Configure with mcp-remote bridge**:
   Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

   ```json
   {
     "mcpServers": {
       "maverick-mcp": {
         "command": "npx",
         "args": ["-y", "mcp-remote", "http://localhost:8003/mcp/"]
       }
     }
   }
   ```

**Benefits**:
- ✅ Uses HTTP Streamable transport
- ✅ Alternative to SSE endpoint
- ✅ Supports remote access

#### Method C: Remote via Claude.ai (Alternative)
   
   For native remote server support, use [Claude.ai web interface](https://claude.ai/settings/integrations) instead of Claude Desktop.

3. **Restart Claude Desktop** and test with: "Show me technical analysis for AAPL"

### Other Popular MCP Clients

> ⚠️ **Critical Transport Warning**: MCP clients have specific transport limitations. Using incorrect configurations will cause connection failures. Always verify which transports your client supports.

#### Transport Compatibility Matrix

| MCP Client           | STDIO | HTTP | SSE | Optimal Method                                |
|----------------------|-------|------|-----|-----------------------------------------------|
| **Claude Desktop**   | ❌    | ❌   | ✅  | **SSE via mcp-remote** (stable, tested)      |
| **Cursor IDE**       | ✅    | ❌   | ✅  | SSE and STDIO supported                       |
| **Claude Code CLI**  | ✅    | ✅   | ✅  | All transports supported                      |
| **Continue.dev**     | ✅    | ❌   | ✅  | SSE and STDIO supported                       |
| **Windsurf IDE**     | ✅    | ❌   | ✅  | SSE and STDIO supported                       |

#### Claude Desktop (Most Commonly Used)

**✅ TESTED CONFIGURATION**: Use SSE endpoint with mcp-remote bridge - prevents tools from disappearing and ensures stable connection.

**Configuration Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**SSE Connection with mcp-remote (Tested and Stable):**

1. Start the server:
   ```bash
   make dev  # Starts SSE server on port 8003
   ```

2. Configure Claude Desktop:
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

**Important**: This exact configuration has been tested and confirmed to prevent the common issue where tools appear initially but then disappear from Claude Desktop. The server now accepts both `/sse` and `/sse/` paths without redirects.

**Restart Required:** Always restart Claude Desktop after config changes.

#### Cursor IDE - SSE and STDIO Support

**Option 1: Direct SSE (Recommended):**
```json
{
  "mcpServers": {
    "maverick-mcp": {
      "url": "http://localhost:8003/sse"
    }
  }
}
```

**Location:** Cursor → Settings → MCP Servers

#### Claude Code CLI - Full Transport Support

**SSE Transport (Recommended):**
```bash
claude mcp add --transport sse maverick-mcp http://localhost:8003/sse
```

**HTTP Transport (Alternative):**
```bash
claude mcp add --transport http maverick-mcp http://localhost:8003/mcp/
```

**STDIO Transport (Development only):**
```bash
claude mcp add maverick-mcp uv run python -m maverick_mcp.api.server --transport stdio
```

#### Continue.dev - SSE and STDIO Support

**Option 1: Direct SSE (Recommended):**
```json
{
  "mcpServers": {
    "maverick-mcp": {
      "url": "http://localhost:8003/sse"
    }
  }
}
```

**Option 2: SSE via mcp-remote (Alternative):**
```json
{
  "experimental": {
    "modelContextProtocolServer": {
      "transport": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-remote", "http://localhost:8003/sse"]
      }
    }
  }
}
```

**Location:** `~/.continue/config.json`

#### Windsurf IDE - SSE and STDIO Support

**Option 1: Direct SSE (Recommended):**
```json
{
  "mcpServers": {
    "maverick-mcp": {
      "serverUrl": "http://localhost:8003/sse"
    }
  }
}
```

**Option 2: SSE via mcp-remote (Alternative):**
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

**Location:** Windsurf → Settings → Advanced Settings → MCP Servers

### How It Works

**Connection Architecture:**
- **STDIO Mode (Optimal for Claude Desktop)**: Direct subprocess communication - fastest, most reliable
- **Streamable-HTTP Endpoint**: `http://localhost:8003/` - For remote access via mcp-remote bridge
- **SSE Endpoint**: `http://localhost:8003/sse` - For other clients with native SSE support (accepts both `/sse` and `/sse/`)

> **Key Finding**: Direct STDIO is the optimal transport for Claude Desktop. HTTP/SSE require the mcp-remote bridge tool, adding latency and complexity. SSE is particularly problematic as it's incompatible with mcp-remote (GET vs POST mismatch).

**Transport Limitations by Client:**
- **Claude Desktop**: STDIO-only, cannot directly connect to HTTP/SSE
- **Most Other Clients**: Support STDIO + SSE (but not HTTP)
- **Claude Code CLI**: Full transport support (STDIO, HTTP, SSE)

**mcp-remote Bridge Tool:**
- **Purpose**: Converts STDIO client calls to HTTP/SSE server requests
- **Why Needed**: Bridges the gap between STDIO-only clients and HTTP/SSE servers
- **Connection Flow**: Client (STDIO) ↔ mcp-remote ↔ HTTP/SSE Server
- **Installation**: `npx mcp-remote <server-url>`

**Key Transport Facts:**
- **STDIO**: All clients support this for local connections
- **HTTP**: Only Claude Code CLI supports direct HTTP connections
- **SSE**: Cursor, Continue.dev, Windsurf support direct SSE connections  
- **Claude Desktop Limitation**: Cannot connect to HTTP/SSE without mcp-remote bridge

**Alternatives for Remote Access:**
- Use Claude.ai web interface for native remote server support (no mcp-remote needed)

## Key Features

### Stock Analysis

- Historical price data with database caching
- Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands)
- Support/resistance levels
- Volume analysis and patterns

### Stock Screening (Pre-seeded S&P 500 Data)

- **Maverick Bullish**: High momentum stocks with strong technicals from 520 S&P 500 stocks
- **Maverick Bearish**: Weak setups for short opportunities with pre-analyzed data
- **Supply/Demand Breakouts**: Stocks in confirmed uptrend phases with technical breakout patterns
- All screening data is pre-calculated and stored in database for instant results

### Portfolio Analysis

- Portfolio optimization using Modern Portfolio Theory
- Risk analysis and correlation matrices
- Performance metrics and comparisons

### Market Data

- Real-time quotes and market indices
- Sector performance analysis
- Economic indicators from FRED API

## Available Tools

All tools are organized into logical groups (39+ tools total):

### Data Tools (`/data/*`) - S&P 500 Pre-seeded

- `get_stock_data` - Historical price data with database caching
- `get_stock_info` - Company information from pre-seeded S&P 500 database
- `get_multiple_stocks_data` - Batch data fetching with optimized queries

### Technical Analysis (`/technical/*`)

- `calculate_sma`, `calculate_ema` - Moving averages
- `calculate_rsi` - Relative Strength Index
- `calculate_macd` - MACD indicator
- `calculate_bollinger_bands` - Bollinger Bands
- `get_full_technical_analysis` - Complete analysis suite

### Screening (`/screening/*`) - Pre-calculated Results

- `get_maverick_recommendations` - Bullish momentum stocks from S&P 500 database
- `get_maverick_bear_recommendations` - Bearish setups with pre-analyzed data
- `get_trending_breakout_recommendations` - Supply/demand breakout candidates from 520 stocks
- All screening results are pre-calculated and stored for instant access

### Advanced Research Tools (`/research/*`) - NEW AI-Powered Analysis

- `research_comprehensive` - Full parallel research with multiple AI agents (7-256x faster)
- `research_company` - Company-specific deep research with financial analysis
- `analyze_market_sentiment` - Multi-source sentiment analysis with confidence tracking
- `coordinate_agents` - Multi-agent supervisor for complex research orchestration

**Research Features:**
- **Parallel Execution**: 7-256x speedup with intelligent agent orchestration
- **Adaptive Timeouts**: 120s-600s based on research depth and complexity
- **Smart Model Selection**: Automatic selection from 400+ models via OpenRouter
- **Cost Optimization**: 40-60% cost reduction through intelligent model routing
- **Early Termination**: Confidence-based early stopping to save time and costs
- **Content Filtering**: High-credibility source prioritization
- **Error Recovery**: Circuit breakers and comprehensive error handling

### Portfolio Management (`/portfolio/*`) - Personal Holdings Tracking (NEW)

- `portfolio_add_position` - Add or update positions with automatic cost basis averaging
- `portfolio_get_my_portfolio` - View portfolio with live P&L calculations
- `portfolio_remove_position` - Remove partial or full positions
- `portfolio_clear_portfolio` - Clear all positions with safety confirmation

**Key Features:**
- Persistent storage with cost basis tracking (average cost method)
- Live unrealized P&L calculations with real-time prices
- Automatic cost averaging on repeat purchases
- Support for fractional shares and high-precision decimals
- Multi-portfolio support (track IRA, 401k, taxable separately)
- Portfolio resource (`portfolio://my-holdings`) for AI context

### Portfolio Analysis (`/portfolio/*`) - Intelligent Integration

- `risk_adjusted_analysis` - Risk-based position sizing (shows your existing positions)
- `compare_tickers` - Side-by-side comparison (auto-uses portfolio if no tickers provided)
- `portfolio_correlation_analysis` - Correlation matrix (auto-analyzes your holdings)

**Smart Features:**
- Tools auto-detect your portfolio positions
- Position-aware recommendations (averaging up/down, profit taking)
- No manual ticker entry needed for portfolio analysis

### Backtesting (`/backtesting/*`) - VectorBT-Powered Strategy Testing

- `run_backtest` - Execute backtests with any strategy
- `compare_strategies` - A/B testing for strategy comparison
- `optimize_strategy` - Walk-forward optimization and parameter tuning
- `analyze_backtest_results` - Comprehensive performance analytics
- `get_backtest_report` - Generate detailed HTML reports

**Capabilities:**
- 15+ built-in strategies including ML algorithms
- VectorBT engine for vectorized performance
- Parallel processing with 7-256x speedup
- Monte Carlo simulations and robustness testing
- Multi-timeframe support (1min to monthly)

### Market Data

- `get_market_overview` - Indices, sectors, market breadth
- `get_watchlist` - Sample portfolio with real-time data

## Saty Trading System

> **Full reference**: `docs/saty_trading_skill.md`
> **Pine Script ground truth**: `docs/saty_atr_levels_pine_script.txt`, `docs/pivot_ribbon_pine_script.txt`, `docs/phase_oscillator_pine_script.txt`

### Philosophy

The Saty system answers four questions before every trade:

1. **What is the trend?** → Pivot Ribbon Pro (EMA stack)
2. **Where are the key levels?** → ATR Levels + Price Structure (PDH/PDL/PMH/PML)
3. **Is there momentum to act?** → Phase Oscillator
4. **Is price in bullish/bearish structural context?** → Position vs PDH/PDL/PMH/PML

**Core discipline**: Never trade the first 10 minutes (9:30–9:40 ET). Never chase breakouts — wait for Blue/Orange bias candles on pullbacks. Verbal Audit before every entry (Setup → Trigger → Entry → Exit → Stop).

### Indicator 1: Saty ATR Levels (`atr_levels.py`)

**What it computes** (matching Pine Script exactly):

| Output key | Description |
|---|---|
| `pdc` | Previous Day Close = Zero Line / central pivot |
| `atr` | Wilder ATR14 from the *previous settled bar* (Pine: `ta.atr(14)[1]`) |
| `call_trigger` | PDC + 0.236×ATR — bullish GO signal (cyan) |
| `put_trigger` | PDC − 0.236×ATR — bearish GO signal (orange) |
| `levels` | Full dict: trigger, golden_gate, mid_50, mid_range, fib_786, full_range × bull/bear |
| `atr_covered_pct` | `(today_H − today_L) / ATR × 100` — how much of today's range is used |
| `atr_status` | `green` ≤70%, `orange` 70–90%, `red` ≥90% (room to run assessment) |
| `atr_room_ok` | `True` when status=green |
| `trigger_box` | `{inside: bool}` — True when price is between put/call trigger (Chopzilla zone) |
| `price_position` | Enum: `above_full_range` / `above_mid_range` / `inside_trigger_box` / etc. |
| `trend` | EMA 8/21/34 stack: `bullish` / `bearish` / `neutral` |
| `call_trigger` / `put_trigger` | Top-level aliases to `levels.trigger_bull/bear.price` |

**Critical implementation detail**: ATR and PDC come from `iloc[-2]` (previous settled bar), not the forming bar. Levels never move intraday — only the current_price changes.

**Endpoint**: `POST /api/satyland/calculate` — returns ATR Levels + Pivot Ribbon + Phase Oscillator together.

### Indicator 2: Saty Pivot Ribbon Pro (`pivot_ribbon.py`)

**What it computes**:

| EMA | Role |
|---|---|
| 8 | Fast / Momentum |
| 13 | Conviction crossover signal |
| 21 | **THE PIVOT CENTER** — key mean-reversion anchor |
| 48 | **Bias EMA** — above = bullish regime, below = bearish regime |
| 200 | Macro trend filter |

**Key output keys**:

| Key | Description |
|---|---|
| `ribbon_state` | `bullish` (8>21>48), `bearish` (8<21<48), `chopzilla` (mixed) |
| `bias_candle` | `green` (up+above48), `blue` (down+above48=BUY PULLBACK), `orange` (up+below48=SHORT), `red` (down+below48), `gray` (compression) |
| `in_compression` | Bool — uses 2.0×ATR14 threshold formula (NOT LazyBear BB-inside-KC) |
| `conviction_arrow` | `bullish_crossover` / `bearish_crossover` / None (EMA13 × EMA48) |
| `above_200ema` | Bool — macro regime filter |
| `chopzilla` | Bool — alias for `ribbon_state == "chopzilla"` |

**Entry rule**: Wait for `bias_candle = "blue"` (bullish pullback) or `bias_candle = "orange"` (bearish pullback). Never enter on green or red (trend candles — too late).

### Indicator 3: Saty Phase Oscillator (`phase_oscillator.py`)

**Formula** (exact Pine Script port):
```
raw_signal  = ((close − EMA21) / (3.0 × ATR14)) × 100
oscillator  = EMA3(raw_signal)          # alpha = 2/(3+1) = 0.5
```

**Key output keys**:

| Key | Description |
|---|---|
| `oscillator` | Current value (typically ±150 range in trending markets) |
| `oscillator_prev` | Previous bar value (for crossover detection) |
| `phase` | `green` (osc≥0), `red` (osc<0), `compression` (in_compression=True) |
| `in_compression` | Bool — same formula as Pivot Ribbon compression tracker |
| `current_zone` | `extreme_up/down` (±100), `distribution/accumulation` (±61.8), `neutral_up/down` (±23.6), `above/below_zero` |
| `zone_crosses` | `leaving_accumulation/extreme_down/distribution/extreme_up` — mean reversion signals |

**Note on phase strings**: phase is `"green"` / `"red"` / `"compression"` — NOT `"firing_up"` / `"firing_down"` (old Pine Script terminology).

### Price Structure Levels (`price_structure.py`)

Mark before the open, every day:

| Level | Meaning | Bullish trigger |
|---|---|---|
| PDH | Previous Day High | Price above PDH = strongly bullish structural bias |
| PDL | Previous Day Low | Price below PDL = strongly bearish structural bias |
| PMH | Pre-Market High | Price above PMH = intraday bullish bias |
| PML | Pre-Market Low | Price below PML = intraday bearish bias |

**Highest conviction**: When an ATR trigger level clusters within 0.5% of PDH/PDL/PMH/PML → confluence zone. Green Flag gives +1 bonus for this.

### Green Flag Checklist (`green_flag.py`)

Grades a trade setup A+/A/B/skip based on 10 confirmation flags:

| Flag | Bullish check | Bearish check |
|---|---|---|
| `trend_ribbon_stacked` | ribbon_state == "bullish" | ribbon_state == "bearish" |
| `price_above/below_cloud` | current_price > EMA48 | current_price < EMA48 |
| `trigger_hit` | price ≥ call_trigger | price ≤ put_trigger |
| `structure_confirmed` | price above PDH or PMH | price below PDL or PML |
| `mtf_aligned` | above_200ema = True | above_200ema = False |
| `momentum_confirmed` | phase == "green" | phase == "red" |
| `squeeze` | in_compression = True | in_compression = True |
| `atr_room_ok` | atr_status == "green" | atr_status == "green" |
| `vix_bias` | vix < 17 | vix > 20 |
| `confluence_bonus` | trigger within 0.5% of PDH | trigger within 0.5% of PDL |

| Score | Grade | Recommendation |
|---|---|---|
| ≥5 | A+ | Full size per Rule of 10 |
| 4 | A | Standard size |
| 3 | B | Reduce size / wait for one more |
| <3 | skip | Do not force the trade |

**Endpoint**: `POST /api/satyland/trade-plan` — returns all indicators + price structure + Green Flag grade.

### The Nine A+ Setups (Brief Reference)

Full setup documentation in `docs/saty_trading_skill.md`.

| # | Setup | Key Condition |
|---|---|---|
| 1 | Trend Continuation (Ribbon Retest) | Blue/Orange candle pulls back to 13/21 EMA in stacked ribbon |
| 2 | Golden Gate | Price breaks ±38.2% with conviction; target ±61.8% (60% hit rate) |
| 3 | Vomy (Bearish Reversal) | 5-stage: Fins → Sickness → Vomit → Trigger → Target |
| 4 | iVomy (Bullish Reversal) | Mirror of Vomy |
| 5 | Squeeze | Phase Oscillator compression fires; direction from ribbon orientation |
| 6 | ORB (10-min Open Range Breakout) | Candle close outside 9:30–9:40 range; retest preferred |
| 7 | Divergence from Extreme | Price new HOD/LOD, oscillator does not confirm |
| 8 | 1-min EOD Divergence (0DTE) | 2:00–3:45 PM ET; phase oscillator reversal at extreme |
| 9 | Dip Connoisseur | Gap into demand zone at −1 ATR; ribbon stabilizing |
| B | NASA (IV Flush) | Post-earnings IV crush; buy deflated premiums |

### Valhalla Exit Framework

Scale at **Mid-Range (+61.8%)**: sell 70%, move stop to breakeven on 30% runners. Exit runners at Full Range (+100%) or Ribbon fold. Extension levels beyond 100% = Valhalla territory (runners only).

### Saty API Endpoints

```
POST /api/satyland/calculate       → ATR Levels + Pivot Ribbon + Phase Oscillator
POST /api/satyland/trade-plan      → Above + Price Structure + Green Flag (A+/A/B/skip)
POST /api/satyland/price-structure → PDH/PDL/PMH/PML only
POST /api/schwab/quote             → Real-time quote via Schwab
POST /api/schwab/options-chain     → Full options chain via Schwab
POST /api/options/atm-straddle     → ATM straddle + expected move
POST /api/options/gamma-exposure   → GEX by strike
GET  /api/schwab/auth/url          → Start OAuth2 flow
POST /api/schwab/auth/callback     → Complete OAuth2 flow
```

Request body for `/calculate` and `/trade-plan`:
```json
{
  "ticker": "SPY",
  "timeframe": "5m",        // 1m | 5m | 15m | 1h | 4h | 1d | 1w
  "direction": "bullish",   // trade-plan only: "bullish" | "bearish"
  "vix": 15.2,              // trade-plan only: optional VIX level
  "atr_period": 14,         // default 14
  "include_extensions": false  // include Valhalla levels beyond 100%
}
```

### Saty Testing

```bash
# Run full test suite (115 tests, no containers needed, ~0.5s)
venv/bin/pytest tests/satyland/ -v

# Run by category
venv/bin/pytest tests/satyland/test_atr_levels.py -v       # ATR math
venv/bin/pytest tests/satyland/test_pivot_ribbon.py -v     # Ribbon + bias candle
venv/bin/pytest tests/satyland/test_phase_oscillator.py -v # Phase oscillator formula
venv/bin/pytest tests/satyland/test_green_flag.py -v       # Green flag + bug regressions
venv/bin/pytest tests/satyland/test_behavioral.py -v       # Pine Script invariants
venv/bin/pytest tests/satyland/test_endpoints.py -v        # FastAPI endpoints (mocked yfinance)
```

### Saty Environment Variables

```
# Schwab integration (required for real-time data)
SCHWAB_CLIENT_ID=
SCHWAB_CLIENT_SECRET=
SCHWAB_REDIRECT_URI=https://127.0.0.1
SCHWAB_TOKEN_FILE=/tmp/schwab_tokens.json

# CORS (use * for local development)
ALLOWED_ORIGINS=*
```

No Tiingo API key needed — Saty uses `yfinance` for historical data.

---

## Integration Architecture: Maverick + Saty

The two systems are designed to complement each other at different stages of the trading workflow:

```
┌─────────────────────────────────────────────────────────┐
│              MAVERICK MCP (Strategic Layer)              │
│                                                         │
│  • Screen 520 S&P 500 stocks for Maverick Bullish/Bear  │
│  • Supply/demand breakout candidates                    │
│  • Fundamental + macroeconomic context (FRED API)       │
│  • Portfolio P&L and position management                │
│  • AI research (OpenRouter 400+ models)                 │
└──────────────────────┬──────────────────────────────────┘
                       │ "These are the candidates"
                       ↓
┌─────────────────────────────────────────────────────────┐
│               SATY API (Tactical Layer)                  │
│                                                         │
│  • Is the ribbon stacked? (trend confirmation)          │
│  • Has the trigger been hit? (±23.6% ATR)              │
│  • Is structure cleared? (PDH/PDL/PMH/PML)             │
│  • Is momentum firing? (Phase Oscillator green/red)     │
│  • Grade: A+ (full size) / A / B / skip                │
└─────────────────────────────────────────────────────────┘
```

**Planned combined workflows**:

1. **Screening → Timing**: Maverick finds high-momentum S&P 500 stocks → Saty `/trade-plan` grades each candidate for same-day entry
2. **Portfolio → Position Sizing**: Maverick portfolio P&L → Saty Green Flag score → position size via Rule of 10
3. **Macro → Bias**: Maverick FRED macro data + VIX → Saty VIX bias filter → directional bias for session
4. **Backtesting Saty Setups**: Feed Maverick VectorBT engine with Saty indicator signals to backtest the 9 setups historically

**Independent operation**: Each system is fully self-contained. Maverick runs on port 8003 (MCP/SSE). Saty runs on port 8080 (REST). Neither requires the other to be running.

---

## Development Commands

### Running the Servers

```bash
# ── Maverick MCP Server (port 8003) ──────────────────────────────────────────
make dev                    # SSE transport (default, recommended for Claude Desktop)
make dev-http               # Streamable-HTTP transport (for testing with curl/Postman)
make dev-stdio              # STDIO transport (direct connection)

# Alternative: Direct commands (manual)
uv run python -m maverick_mcp.api.server --transport sse --port 8003
uv run python -m maverick_mcp.api.server --transport streamable-http --port 8003
uv run python -m maverick_mcp.api.server --transport stdio

# ── Saty API Server (port 8080) ───────────────────────────────────────────────
venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# ── Run both simultaneously ───────────────────────────────────────────────────
make dev &   # Maverick on 8003 (background)
venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload  # Saty on 8080
```

**When to use each Maverick transport:**
- **SSE** (`make dev` or `make dev-sse`): Best for Claude Desktop - tested and stable
- **Streamable-HTTP** (`make dev-http`): Ideal for testing with curl/Postman, debugging transport issues
- **STDIO** (`make dev-stdio`): Direct connection without network layer, good for development

### Testing

```bash
# ── Saty tests (no containers, fast ~0.5s) ────────────────────────────────────
venv/bin/pytest tests/satyland/ -v                    # All 115 satyland tests
venv/bin/pytest tests/satyland/test_green_flag.py -v  # Bug regressions + grading
venv/bin/pytest tests/satyland/test_endpoints.py -v   # API endpoint tests

# ── Maverick tests ────────────────────────────────────────────────────────────
make test                  # Unit tests only (5-10 seconds)
make test-specific TEST=test_name  # Run specific test
make test-watch           # Auto-run on changes

# Using uv (recommended for Maverick)
uv run pytest                    # Manual pytest execution
uv run pytest --cov=maverick_mcp # With coverage
uv run pytest -m integration    # Integration tests (requires PostgreSQL/Redis)

# Alternative: Direct pytest (if activated in venv)
pytest                    # Manual pytest execution
pytest --cov=maverick_mcp # With coverage
pytest -m integration    # Integration tests (requires PostgreSQL/Redis)
```

**Note on test isolation**: Saty tests in `tests/satyland/` run independently without testcontainers, PostgreSQL, or Redis. Maverick integration tests require containers. The root `tests/conftest.py` is guarded so Saty tests can always run.

### Code Quality

```bash
# Automated quality checks
make format               # Auto-format with ruff
make lint                 # Check code quality with ruff
make typecheck            # Type check with ty (Astral's modern type checker)
make check                # Run all checks

# Using uv (recommended)
uv run ruff check .       # Linting
uv run ruff format .      # Formatting
uv run ty check .         # Type checking (Astral's modern type checker)

# Ultra-fast one-liner (no installation needed)
uvx ty check .            # Run ty directly without installing

# Alternative: Direct commands (if activated in venv)
ruff check .             # Linting
ruff format .            # Formatting
ty check .               # Type checking
```

## Configuration

### Database Options

**SQLite (Default - No Setup Required, includes S&P 500 data)**:

```bash
# Uses SQLite automatically with S&P 500 data seeding on first run
make dev
```

**PostgreSQL (Optional - Better Performance)**:

```bash
# In .env file
DATABASE_URL=postgresql://localhost/maverick_mcp

# Create database
createdb maverick_mcp
make migrate
```

### Caching Options

**No Caching (Default)**:

- Works out of the box, uses in-memory caching

**Redis Caching (Optional - Better Performance)**:

```bash
# Install and start Redis
brew install redis
brew services start redis

# Or use make command
make redis-start

# Server automatically detects Redis and uses it
```

## Code Guidelines

### General Principles

- Python 3.12+ with modern features
- Type hints for all functions
- Google-style docstrings for public APIs
- Comprehensive error handling
- Performance-first design with caching

### Financial Analysis (Maverick)

- Use pandas_ta for technical indicators
- Document all financial calculations
- Validate input data ranges
- Cache expensive computations
- Use vectorized operations for performance

### MCP Integration (Maverick)

- Register tools with `@mcp.tool()` decorator
- Return JSON-serializable results
- Implement graceful error handling
- Use database caching for persistence
- Follow FastMCP 2.0 patterns

### Saty Indicator Development

- **Pine Script parity is non-negotiable**: Every indicator must match `docs/*_pine_script.txt` exactly
- **ATR source**: Always use Wilder ATR with `ewm(alpha=1/period, adjust=False)` — NOT `ewm(span=period)`
- **EMA source**: Use `ewm(span=N, adjust=False)` for all ribbon EMAs — NOT Wilder
- **ATR and PDC are always from `iloc[-2]`** (previous settled bar, not the forming bar)
- **Compression tracker is stateful**: Must use a bar-by-bar `for` loop — vectorized boolean ops give wrong results
- **Phase strings**: `"green"` / `"red"` / `"compression"` — never `"firing_up"` / `"firing_down"`
- **call_trigger / put_trigger**: Always expose as top-level keys in the atr dict, not nested under `levels`
- **Minimum bars**: Raise `ValueError` with clear message when input df is too short
- **Test first**: Any change to an indicator file must be verified against `tests/satyland/`
- **No yfinance in indicator files**: Indicators take a pre-fetched `pd.DataFrame` — I/O stays in the endpoint layer

## Troubleshooting

### Saty API Issues

**Saty tests fail to import (`ModuleNotFoundError: api`)**:
```bash
# Run from project root — api/ is a top-level package
cd /Users/krishnaeedula/claude/trend-trading-mcp
venv/bin/pytest tests/satyland/ -v
```

**`/trade-plan` returns 500 with KeyError**:
- Likely a new key was added to an indicator that green_flag.py doesn't handle
- Run `venv/bin/pytest tests/satyland/test_green_flag.py -v` — regression tests will catch it

**yfinance returns empty DataFrame (400 from endpoint)**:
- Ticker may be invalid or delisted
- Intraday data (1m/5m) only available for recent days — use `timeframe="1d"` for older data
- Some tickers require exchange suffix (e.g., `TSLA` not `TSLA.US`)

**Saty root `conftest.py` blocks satyland tests**:
```bash
# Root conftest requires testcontainers — satyland tests are guarded by _MAVERICK_AVAILABLE
# If you see ImportError from root conftest, check that _MAVERICK_AVAILABLE guard is in place
```

### Common Maverick Issues

**Server won't start**:

```bash
make stop          # Stop any running processes
make clean         # Clean temporary files
make dev           # Restart
```

**Port already in use**:

```bash
lsof -i :8003      # Find what's using port 8003
make stop          # Stop MaverickMCP services
```

**Redis connection errors** (optional):

```bash
brew services start redis    # Start Redis
# Or disable caching by not setting REDIS_HOST
```

**Database errors**:

```bash
# Use SQLite (no setup required)
unset DATABASE_URL
make dev

# Or fix PostgreSQL
createdb maverick_mcp
make migrate
```

**Claude Desktop not connecting**:

1. Verify server is running: `lsof -i :8003` (check if port 8003 is in use)
2. Check `claude_desktop_config.json` syntax and correct port (8003)
3. **Use the tested SSE configuration**: `http://localhost:8003/sse` with mcp-remote
4. Restart Claude Desktop completely
5. Test with: "Get AAPL stock data"

**Tools appearing then disappearing**:

1. **FIXED**: Server now accepts both `/sse` and `/sse/` without 307 redirects
2. Use the recommended SSE configuration with mcp-remote bridge
3. Ensure you're using the exact configuration shown above
4. The SSE + mcp-remote setup has been tested and prevents tool disappearing
5. **No trailing slash required**: Server automatically handles path normalization

**Research Tool Issues**:

1. **Timeouts**: Research tools have adaptive timeouts (120s-600s)
2. Deep research may take 2-10 minutes depending on complexity
3. Monitor progress in server logs with `make tail-log`
4. Ensure `OPENROUTER_API_KEY` and `EXA_API_KEY` are set for full functionality

**Missing S&P 500 screening data**:

```bash
# Manually seed S&P 500 database if needed
uv run python scripts/seed_sp500.py
```

### Performance Tips

- **Use Redis caching** for better performance
- **PostgreSQL over SQLite** for larger datasets
- **Parallel screening** is enabled by default (4x speedup)
- **Parallel research** achieves 7-256x speedup with agent orchestration
- **In-memory caching** reduces API calls
- **Smart model selection** reduces costs by 40-60% with OpenRouter

## Quick Testing

Test the server is working:

```bash
# Test server is running
lsof -i :8003

# Test MCP endpoint (after connecting with mcp-remote)
# Use Claude Desktop with: "List available tools"
```

### Test Backtesting Features

Once connected to Claude Desktop, test the backtesting framework:

```
# Basic backtest
"Run a backtest on SPY using the momentum strategy for 2024"

# Strategy comparison
"Compare RSI vs MACD strategies on AAPL for the last year"

# ML strategy test
"Test the adaptive ML strategy on tech sector stocks"

# Performance analysis
"Show me detailed metrics for a mean reversion strategy on QQQ"
```

## Recent Updates

### Saty Trading System Integration

- **Exact Pine Script Ports**: Three core indicators verified against Pine Script ground truth files
  - `atr_levels.py`: Wilder ATR14 + PDC-anchored Fibonacci levels (ATR settled from previous bar)
  - `pivot_ribbon.py`: EMA 8/13/21/48/200 + stateful compression tracker (2.0×ATR14 threshold)
  - `phase_oscillator.py`: `EMA3(((close-EMA21)/(3×ATR14))×100)` + zone cross signals
- **Green Flag Checklist**: A+/A/B/skip trade grading with 10 confirmation flags; 4 KeyError bugs fixed
- **Price Structure Levels**: PDH/PDL/PMH/PML structural bias engine
- **Full REST API**: FastAPI server at port 8080, deployable to Railway with `requirements.txt`
- **115 Tests**: Complete test suite in `tests/satyland/` — no external dependencies, runs in ~0.5s
- **Schwab Integration**: OAuth2 + real-time quotes + options chain via schwab-py
- **Options Analytics**: ATM straddle / expected move + GEX by strike

### Production-Ready Backtesting Framework

- **VectorBT Integration**: High-performance vectorized backtesting engine
- **15+ Built-in Strategies**: Including ML-powered adaptive, ensemble, and regime-aware algorithms
- **Parallel Processing**: 7-256x speedup for multi-strategy evaluation
- **Advanced Analytics**: Sharpe, Sortino, Calmar ratios, maximum drawdown, win rate analysis
- **Walk-Forward Optimization**: Out-of-sample testing with parameter tuning
- **Monte Carlo Simulations**: Robustness testing with confidence intervals
- **LangGraph Workflow**: Multi-agent orchestration for intelligent strategy selection
- **Comprehensive Reporting**: HTML reports with interactive visualizations

### Advanced Research Agents (Major Feature Release)

- **Parallel Research Execution**: Achieved 7-256x speedup (exceeded 2x target) with intelligent agent orchestration
- **Adaptive Timeout Protection**: Dynamic timeouts (120s-600s) based on research depth and complexity
- **Intelligent Model Selection**: OpenRouter integration with 400+ models, 40-60% cost reduction
- **Comprehensive Error Handling**: Circuit breakers, retry logic, and graceful degradation
- **Early Termination**: Confidence-based stopping to optimize time and costs
- **Content Filtering**: High-credibility source prioritization for quality results
- **Multi-Agent Orchestration**: Supervisor pattern for complex research coordination
- **New Research Tools**: `research_comprehensive`, `research_company`, `analyze_market_sentiment`, `coordinate_agents`

### Performance Improvements

- **Parallel Agent Execution**: Increased concurrent agents from 4 to 6
- **Optimized Semaphores**: BoundedSemaphore for better resource management
- **Reduced Rate Limiting**: Delays decreased from 0.5s to 0.05s
- **Batch Processing**: Improved throughput for multiple research tasks
- **Smart Caching**: Redis-powered with in-memory fallback
- **Stock Screening**: 4x faster with parallel processing

### Testing & Quality

- **84% Test Coverage**: 93 tests with comprehensive coverage
- **Zero Linting Errors**: Fixed 947 issues for clean codebase
- **Full Type Annotations**: Complete type coverage for research components
- **Error Recovery Testing**: Comprehensive failure scenario coverage

### Personal Use Optimization

- **No Authentication/Billing**: Completely removed for personal use simplicity
- **Pre-seeded S&P 500 Database**: 520 stocks with comprehensive screening data on first startup
- **Simplified Architecture**: Clean, focused codebase without commercial complexity
- **Multi-Transport Support**: HTTP, SSE, and STDIO for all MCP clients
- **SQLite Default**: No database setup required, PostgreSQL optional for performance

### AI/LLM Integration

- **OpenRouter Integration**: Access to 400+ AI models with intelligent cost optimization
- **Smart Model Selection**: Automatic model selection based on task requirements (sentiment analysis, market research, technical analysis)
- **Cost-Efficient by Default**: Prioritizes cost-effectiveness while maintaining quality, 40-60% cost savings over premium-only approaches
- **Multiple Model Support**: Claude Opus 4.1, Claude Sonnet 4, Claude 3.5 Haiku, GPT-5, GPT-5 Nano, Gemini 2.5 Pro, DeepSeek R1, and more

### Developer Experience

- Comprehensive Makefile for all common tasks
- Smart error handling with automatic fix suggestions
- Hot reload development mode
- Extensive test suite with quick unit tests
- Type checking with ty (Astral's extremely fast type checker) for better IDE support

## Additional Resources

### Saty System
- **Full Saty skill reference**: `docs/saty_trading_skill.md` — complete trading methodology, all 9 setups, entry/exit rules, strike selection, risk management
- **Pine Script ground truth**: `docs/saty_atr_levels_pine_script.txt`, `docs/pivot_ribbon_pine_script.txt`, `docs/phase_oscillator_pine_script.txt`
- **Saty test suite**: `tests/satyland/` — 115 tests, no external dependencies

### Maverick System
- **Architecture docs**: `docs/` directory
- **Portfolio Guide**: `docs/PORTFOLIO.md` - Complete guide to portfolio features
- **Backtesting Guide**: `docs/BACKTESTING.md`
- **Test examples**: `tests/` directory
- **Development tools**: `tools/` directory
- **Example scripts**: `scripts/` directory

---

**Note**: This project is designed for personal use. It provides two complementary trading systems:
1. **Maverick MCP**: Powerful stock analysis and screening for Claude Desktop with pre-seeded S&P 500 data
2. **Saty API**: Rules-based indicator system for precise trade timing, exact Python ports of the Saty Pine Scripts

Use them independently or together — Maverick for candidate selection, Saty for entry grading and timing.
