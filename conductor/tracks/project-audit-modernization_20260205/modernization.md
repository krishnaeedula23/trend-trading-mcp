# Modernization Roadmap

**Track ID:** project-audit-modernization_20260205
**Updated:** 2026-02-05

## Goals

- Reduce architecture drift by choosing and documenting a single “golden path”
- Make MCP transports/tool registration robust without embedded hacks
- Improve maintainability by modularizing the largest files and removing global side effects
- Align with current MCP/FastMCP best practices (transports, tooling, resource/prompt patterns)

## Proposed Sequencing

1. **Decide scope**: recommendations-only vs “quick wins” implementation in this track.
2. **Server/transport decision**: choose the primary transport(s) and primary entrypoint module(s).
3. **Tool registration strategy**: choose direct registration vs router mounting, and codify it.
4. **Architecture consolidation**: pick provider abstraction (interfaces/adapters) and deprecate alternatives.
5. **Modularize hotspots**: split `api/server.py` and `agents/deep_research.py` once architecture decisions are made.
6. **Cleanups**: remove module-level `basicConfig()` / `load_dotenv()` patterns; centralize startup config.

## Safe Wins (First Implementation Session)

These should be the first changes when you start implementation work (aim: low risk, high clarity):

1. **Choose the golden path** and encode it in docs + Make targets:
   - Decide whether Claude Desktop will be supported via `streamable-http` (likely) and/or SSE.
   - Reconcile the current contradiction between `CLAUDE.md` and `maverick_mcp/README.md`.
2. **Upgrade FastMCP within stable 2.x**, then re-test transports/tool registration:
   - Re-evaluate whether `maverick_mcp/api/server.py` still needs the SSE trailing-slash monkey-patch.
3. **Centralize startup side effects**:
   - Remove module-level `logging.basicConfig()` and `load_dotenv()` calls from library modules.
   - Keep all environment loading and logging configuration in one bootstrap path.
4. **Canonicalize routers**:
   - Choose canonical router modules (e.g., “enhanced” becomes default) and mark others legacy.
5. **Adopt background tasks** where appropriate:
   - Convert long-running tools (deep research, heavy backtests) to protocol-native background tasks to improve responsiveness and reduce timeouts.

## Refactor Backlog

P0 (highest impact / lowest regret)

- Unify entrypoint(s): define a single supported way to run the MCP server and mark others as legacy (`maverick_mcp/api/server.py`, `maverick_mcp/api/api_server.py`, `maverick_mcp/api/simple_sse.py`, inspector variants).
- Remove/relocate global side effects (`logging.basicConfig`, `load_dotenv`) to a single startup/bootstrap location (`maverick_mcp/providers/stock_data.py`, `maverick_mcp/config/settings.py`).
- Establish “canonical routers” and deprecate variants (`maverick_mcp/api/routers/*_enhanced.py`, `*_ddd.py`, `*_parallel.py`) with a short migration plan.
- Upgrade `fastmcp` within the stable 2.x line and re-validate transport behavior to remove hacks (see `mcp-fastmcp-research.md`).
- Align HTTP transports with MCP spec guidance (notably Origin validation if exposed beyond localhost).

P1

- Modularize `maverick_mcp/api/server.py` (bootstrap vs resources/tools vs prompts vs shutdown).
- Modularize `maverick_mcp/agents/deep_research.py` (providers, policies, graph wiring, output formatting).
- Consolidate provider strategy: either (a) finish migrating to interfaces/adapters or (b) keep concrete providers and delete adapter layer. Current hybrid increases cost.
- Adopt FastMCP background tasks for long-running tools (deep research, parallel screening, backtests) to improve responsiveness and reduce timeouts.

P2

- Consolidate tests location / test suite tiers (fast vs slow), if not already formalized.
- Clean up unfinished registry/init TODOs: `maverick_mcp/langchain_tools/registry.py`.

## Frontend & UI Roadmap

The frontend (`frontend/`) is a Next.js 15 app deployed on Vercel. Current pages: dashboard, analyze, ideas. The following items expand it into a complete trading workstation.

### Missing Pages

| Route | Purpose | Priority |
|-------|---------|----------|
| `/screener` | Scan universe with Saty indicators, rank by grade | P0 (see Screener section below) |
| `/alerts` | Manage price/indicator alerts linked to ideas | P1 |
| `/watchlists` | CRUD watchlists, batch calculate indicators | P1 |
| `/settings` | API keys, default timeframe, notification prefs | P2 |
| `/backtest` | Display VectorBT backtest results from Maverick | P2 |

### shadcn Component Additions

| Component | Use Case |
|-----------|----------|
| `data-table` | Screener results, ideas list, watchlist tickers |
| `command` | Global ticker search (Cmd+K) |
| `sonner` | Toast notifications (already added to project) |
| `chart` | Recharts wrapper for Phase Oscillator gauge |
| `calendar` / `date-picker` | Backtest date range selection |

### Lightweight Charts Integration

Add TradingView Lightweight Charts to `/analyze/[ticker]` for:
- Candlestick chart with ATR level overlays (call/put triggers, Fib levels)
- EMA ribbon overlay (8/13/21/48/200)
- Phase Oscillator as a sub-chart pane

### UI Approach

No design skills or Figma needed. Use:
- shadcn blocks and pre-built component patterns
- Claude Code for rapid iteration
- Existing dark theme (`frontend/src/app/globals.css`)
- Consistent with current layout (sidebar + header from `frontend/src/components/layout/`)

---

## Screener Feature (New)

### Motivation

thinkorswim custom screeners cannot be pulled via Schwab API (no endpoint exists). This feature replaces that workflow by running Saty indicators server-side against a stock universe and returning ranked results.

### Step 1: Wire Up Unused `schwab-py` Methods

`schwab-py` v1.5.1 is already installed. These methods exist in `schwab.client.Client` but aren't exposed in our wrapper:

| Method | What It Provides | Wrapper File |
|--------|-----------------|--------------|
| `get_movers(index)` | Top 10 gainers/losers/volume for `$SPX`/`$DJI`/`$COMPX` | `api/integrations/schwab/client.py` |
| `get_quotes(symbols)` | Bulk quotes (we currently only do single via `get_quote`) | `api/integrations/schwab/client.py` |
| `get_instruments(symbols, 'fundamental')` | P/E, market cap, dividend yield | `api/integrations/schwab/client.py` |

### Step 2: New API Endpoints

| Endpoint | Method | File | Purpose |
|----------|--------|------|---------|
| `/api/schwab/movers` | GET | `api/endpoints/schwab.py` | Expose movers by index |
| `/api/schwab/quotes` | GET | `api/endpoints/schwab.py` | Bulk quotes |
| `/api/schwab/fundamentals` | GET | `api/endpoints/schwab.py` | Fundamentals lookup |
| `/api/screener/scan` | POST | `api/endpoints/screener.py` (new) | Orchestrator endpoint |

### Step 3: Screener Logic (`POST /api/screener/scan`)

```
Request: { universe: "sp500" | "watchlist" | "movers", direction: "bullish" | "bearish",
           timeframe: "5m" | "15m" | "1h" | "1d", min_grade: "B", sector?: "Technology" }

1. Resolve stock universe:
   - "sp500"     → Query Maverick DB (520 tickers)
   - "watchlist" → Fetch user watchlist from Supabase
   - "movers"    → Call Schwab get_movers($SPX)

2. Fetch bulk price history via Schwab (or yfinance fallback)

3. Run Saty indicators per ticker:
   - ATR Levels  (atr_levels.py)
   - Pivot Ribbon (pivot_ribbon.py)
   - Phase Oscillator (phase_oscillator.py)

4. Grade each with Green Flag (green_flag.py)

5. Filter by min_grade and optional sector

6. Return ranked list sorted by grade (A+ first), then score descending

Response: { results: [{ ticker, grade, score, direction, atr_status,
            ribbon_state, bias_candle, phase, call_trigger, put_trigger }], count, scanned }
```

### Step 4: Frontend (`/screener`)

- **Filters panel**: direction, timeframe, min grade, sector (collapsible)
- **Results table**: shadcn `data-table` with sortable columns
- **Row click** → navigates to `/analyze/[ticker]`
- **Actions per row**: save to watchlist, create idea from result
- **Loading state**: skeleton rows while scan runs (can take 10-30s for large universes)

### Reuse Existing Code

| What | Where |
|------|-------|
| All 5 Saty indicators | `api/indicators/satyland/*` |
| Calculate/trade-plan patterns | `api/endpoints/satyland.py` |
| Grade badge component | `frontend/src/components/ideas/grade-badge.tsx` |
| SWR fetch pattern | `frontend/src/hooks/use-trade-plan.ts` |
| Idea card layout | `frontend/src/components/ideas/idea-card.tsx` |
| Railway fetch wrapper | `frontend/src/lib/railway.ts` |

---

## MCP/FastMCP Alignment Notes

See `mcp-fastmcp-research.md` for up-to-date research findings and the recommended transport/tool patterns to adopt.
