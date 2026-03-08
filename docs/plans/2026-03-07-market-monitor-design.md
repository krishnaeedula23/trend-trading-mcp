# Market Monitor — Breadth Heat Map + Theme Tracker

**Date**: 2026-03-07
**Inspired by**: Pradeep Bonde's Stockbee Market Monitor, rebuilt by Ariel Hernandez (@RealSimpleAriel) with interactive drill-down

## Overview

A `/market-monitor` page that displays market breadth as a color-coded heat map grid. Counts stocks making extreme percentage moves across daily, monthly, intermediate, and quarterly timeframes. Click any cell to see contributing tickers with charts and key levels. Below the heat map, a Theme Tracker ranks GICS sectors by net breadth across multiple periods to reveal rotation.

## Universe

- **All US common stocks with market cap > $1B** (~2,000–2,500 tickers)
- Sourced from Schwab screener API (`get_instruments` with fundamental projection)
- Stored in Supabase `monitor_universe` table with sector/industry metadata
- Refreshed weekly via cron

## Data Model

### Table: `monitor_universe`

| Column | Type | Notes |
|--------|------|-------|
| symbol | TEXT PK | Ticker symbol |
| name | TEXT | Company name |
| market_cap | BIGINT | Market cap in USD |
| sector | TEXT | GICS sector |
| industry | TEXT | GICS industry group |
| refreshed_at | TIMESTAMPTZ | Last enrichment time |

### Table: `breadth_snapshots`

One row per trading day. JSONB payloads hold scan counts + contributing ticker lists.

| Column | Type | Notes |
|--------|------|-------|
| date | DATE PK | Trading day |
| universe | TEXT | "large_cap_1b" |
| scans | JSONB | 10 breadth scan results |
| theme_tracker | JSONB | Sector rankings across periods |
| computed_at | TIMESTAMPTZ | When snapshot was generated |

### Scans JSONB Structure

10 keys, each with count + ticker list:

| Key | Threshold | Lookback (trading days) |
|-----|-----------|------------------------|
| `4pct_up_1d` | +4% daily | 1 |
| `4pct_down_1d` | -4% daily | 1 |
| `25pct_up_20d` | +25% from 20d low | 20 |
| `25pct_down_20d` | -25% from 20d high | 20 |
| `50pct_up_20d` | +50% from 20d low | 20 |
| `50pct_down_20d` | -50% from 20d high | 20 |
| `13pct_up_34d` | +13% from 34d low | 34 |
| `13pct_down_34d` | -13% from 34d high | 34 |
| `25pct_up_65d` | +25% from 65d low | 65 |
| `25pct_down_65d` | -25% from 65d high | 65 |

Each value shape:
```json
{
  "count": 47,
  "tickers": [
    { "symbol": "FSLY", "pct_change": 8.2, "close": 24.50, "sector": "Technology" },
    { "symbol": "AOI",  "pct_change": 6.1, "close": 12.30, "sector": "Industrials" }
  ]
}
```

Scan logic (matches Stockbee formulas):
- **Up scans**: `(close - min_close_over_N_days) / min_close_over_N_days >= threshold`
- **Down scans**: `(close - max_close_over_N_days) / max_close_over_N_days <= -threshold`
- **Volume filter**: avg(close, 20) * avg(volume, 20) >= $250,000

### Theme Tracker JSONB Structure

Keyed by GICS sector (~11 sectors):
```json
{
  "Technology": {
    "gainers_1d": 45, "losers_1d": 12, "net_1d": 33,
    "gainers_1w": 50, "losers_1w": 8,  "net_1w": 42,
    "gainers_1m": 48, "losers_1m": 10, "net_1m": 38,
    "gainers_3m": 44, "losers_3m": 14, "net_3m": 30,
    "rank_1d": 2, "rank_1w": 1, "rank_1m": 3, "rank_3m": 5,
    "stock_count": 57,
    "top_gainers": [{ "symbol": "NVDA", "pct_1d": 4.8 }],
    "top_losers":  [{ "symbol": "INTC", "pct_1d": -3.2 }]
  }
}
```

Ranking: sectors ranked by `net_Nd = gainers_Nd - losers_Nd` for each period. Gainers/losers defined as stocks with positive/negative % change for that period.

## API Endpoints

All under `api/endpoints/market_monitor.py`:

### `POST /api/market-monitor/compute`
Compute today's breadth snapshot. Called by daily cron.
- Reads universe from `monitor_universe`
- Fetches 65-day price history per ticker via Schwab (semaphore=10)
- Computes all 10 scan thresholds + theme tracker
- Upserts into `breadth_snapshots`
- Returns summary (counts, duration, errors)

### `GET /api/market-monitor/snapshots?days=30`
Returns last N days of breadth snapshots (scans with counts only, no ticker lists).
Used to render the heat map grid.

### `GET /api/market-monitor/drill-down?date=2026-03-07&scan=4pct_up_1d`
Returns the full ticker list for a specific scan + date.
Used when user clicks a heat map cell.

### `GET /api/market-monitor/theme-tracker?date=2026-03-07`
Returns the theme tracker for a specific date (or latest).
Used to render the sector rotation table.

### `GET /api/market-monitor/sector-stocks?date=2026-03-07&sector=Technology`
Returns all stocks in a sector with their % changes across periods.
Used when user clicks a sector row in the theme tracker.

### `POST /api/market-monitor/backfill?days=65`
One-time: compute snapshots for last N trading days.
Same logic as compute but iterates over historical dates.

### `POST /api/market-monitor/refresh-universe`
Refresh the $1B+ market cap universe from Schwab. Called by weekly cron.

## Cron Jobs

### Daily breadth compute
- **Schedule**: `5 21 * * 1-5` (21:05 UTC = 1:05 PM PST, 5 min after market close)
- **Route**: `POST /api/cron/market-monitor`
- **Steps**: refresh universe (if stale > 7 days) → compute today's snapshot
- **Expected duration**: ~3-5 min for ~2,500 tickers

### Added to `vercel.json`:
```json
{
  "crons": [
    { "path": "/api/cron/daily-screeners", "schedule": "0 14 * * 1-5" },
    { "path": "/api/cron/market-monitor", "schedule": "5 21 * * 1-5" }
  ]
}
```

## Frontend

### Route: `/market-monitor`

#### Header Bar
- Title: "Market Monitor"
- Subtitle: "Breadth of $1B+ stocks making extreme moves"
- Last updated timestamp
- "Force Recompute" button (triggers compute endpoint, shows spinner)

#### Breadth Heat Map (top section)

Grouped by timeframe in horizontal bands (Ariel-style):

```
┌─ DAILY ──────────────────────────────────────────────┐
│  ▲ 4%  │  12 │  47 │  52 │  38 │  41 │ ... │  47  │
│  ▼ 4%  │   8 │   3 │   8 │  12 │   5 │ ... │   3  │
├─ MONTHLY (20 days) ──────────────────────────────────┤
│  ▲ 25% │  78 │  89 │  91 │  87 │  85 │ ... │  89  │
│  ▼ 25% │  22 │  14 │  12 │  18 │  22 │ ... │  14  │
│  ▲ 50% │  19 │  23 │  25 │  21 │  19 │ ... │  23  │
│  ▼ 50% │   6 │   2 │   1 │   4 │   6 │ ... │   2  │
├─ INTERMEDIATE (34 days) ─────────────────────────────┤
│  ▲ 13% │  63 │  67 │  70 │  65 │  63 │ ... │  67  │
│  ▼ 13% │  18 │  11 │   9 │  15 │  18 │ ... │  11  │
├─ QUARTERLY (65 days) ────────────────────────────────┤
│  ▲ 25% │ 135 │ 142 │ 145 │ 139 │ 135 │ ... │ 142  │
│  ▼ 25% │  15 │   8 │   6 │  12 │  15 │ ... │   8  │
└──────────────────────────────────────────────────────┘
  Columns = last 30 trading days, most recent on right
```

**Color scale**:
- Up rows (▲): neutral → green (intensity scales relative to row's historical range)
- Down rows (▼): neutral → red/orange (same relative scaling)
- Cell hover: tooltip with date + exact count

**Click cell** → opens side panel

#### Side Panel (slide-out, ~400px from right)

- Header: scan label + date + count
- Sortable ticker list: symbol, % change, close, sector badge
- Click ticker → inline expand:
  - Mini candlestick chart (lightweight-charts, 30 days)
  - ATR key levels (from existing Saty endpoint)
  - Link to `/analyze/[ticker]`
- Arrow key navigation between tickers

#### Theme Tracker (below heat map)

Sortable table of GICS sectors:

| Sector | 1D Rank | 1W Rank | 1M Rank | 3M Rank | Stocks |
|--------|---------|---------|---------|---------|--------|
| Technology | #2 | #1 | #3 | #5 | 57 |
| Healthcare | #1 | #4 | #2 | #3 | 42 |

- Rank color: #1-3 bright green, #4-6 light green, #7-8 neutral, #9+ orange/red
- Click sector → side panel with all sector stocks, sortable by % gain, closing range, or worst closes
- Rotation divergence highlight: sector that was top-3 in one period but bottom-5 in another gets a visual indicator

### Frontend Components

```
frontend/src/app/market-monitor/
  page.tsx                          -- main page layout
frontend/src/components/market-monitor/
  breadth-heat-map.tsx              -- the grid with timeframe bands
  heat-map-cell.tsx                 -- individual clickable cell
  drill-down-panel.tsx              -- slide-out side panel
  ticker-row.tsx                    -- row in drill-down list
  ticker-detail.tsx                 -- expanded ticker with chart
  theme-tracker-table.tsx           -- sector rotation table
  sector-drill-down.tsx             -- sector stock list in side panel
  force-recompute-button.tsx        -- triggers manual recompute
```

### Hook: `useMarketMonitor()`

Follows existing `useCachedScan` pattern:
- Fetches snapshots (last 30 days) on mount
- Fetches theme tracker for latest date
- Manages selected cell state (scan + date) for drill-down
- Lazy-loads drill-down ticker list only when cell is clicked
- Supports force-recompute with polling for completion

## Tech Stack

- **Backend**: FastAPI endpoint in `api/endpoints/market_monitor.py`
- **Data**: Schwab `get_price_history` (1d frequency, 65-day lookback)
- **Universe**: Schwab `get_instruments` with fundamental projection for market cap + sector
- **Storage**: Supabase (breadth_snapshots + monitor_universe tables)
- **Frontend**: Next.js page, Recharts (heat map), lightweight-charts (mini charts), shadcn/ui (table, sheet, badge)
- **Cron**: Vercel cron at 21:05 UTC (1:05 PM PST) weekdays

## Key Signals (for reference)

From Stockbee methodology:
- 700+ stocks down 4% in a day → potential larger correction
- Quarterly 25% up below 300 → bearish extreme
- 5-day ratio (breakouts/breakdowns) below 0.5 or above 2.0 → reversal signal
- Extreme bearish breadth → strong bullish signal (mean reversion)
