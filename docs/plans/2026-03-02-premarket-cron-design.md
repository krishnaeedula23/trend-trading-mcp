# Premarket Daily Cron — Design

**Date**: 2026-03-02
**Status**: Approved

## Goal

A single daily cron job at 6:00 AM PST (14:00 UTC, weekdays) that pre-runs all
screeners and regenerates the daily trade plan. Results persist in Supabase so
the frontend shows cached data on load — no manual scan needed each morning.
Users can still run a live scan manually at any time.

## Scan Configurations

The cron runs these scans sequentially to avoid overloading Railway:

| Scanner         | Config                                               |
|-----------------|------------------------------------------------------|
| VOMY 1h         | `timeframe: "1h", signal_type: "both"`               |
| VOMY 1d         | `timeframe: "1d", signal_type: "both"`               |
| Golden Gate day | `trading_mode: "day", signal_type: "golden_gate"`    |
| Golden Gate multiday | `trading_mode: "multiday", signal_type: "golden_gate"` |
| Momentum        | default (no mode/timeframe params)                   |
| Daily Trade Plan | SPY + SPX, premarket session                        |

All screener scans use `universes: ["sp500", "nasdaq100"]`, `min_price: 4.0`,
`include_premarket: true`.

## Storage: `cached_scans` Supabase Table

```sql
CREATE TABLE cached_scans (
  id         uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  scan_type  text NOT NULL,
  scan_key   text NOT NULL,
  results    jsonb NOT NULL,
  scanned_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(scan_key)
);

-- Enable RLS (service role bypasses, anon can read)
ALTER TABLE cached_scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read" ON cached_scans FOR SELECT USING (true);
```

### Scan keys

- `vomy:1h:both`
- `vomy:1d:both`
- `golden_gate:day:golden_gate`
- `golden_gate:multiday:golden_gate`
- `momentum:default`

Each cron run upserts (INSERT ... ON CONFLICT (scan_key) DO UPDATE). Always
exactly one row per scan config. No cleanup needed.

## Cron Route: `GET /api/cron/daily-screeners`

Replaces the existing `GET /api/cron/daily-plan` route.

- Authenticated via `CRON_SECRET` Bearer token
- Runs each scan by calling Railway backend directly via `railwayFetch`
- Writes each result to `cached_scans` via upsert
- Then calls `generateDailyPlan("premarket")` for the trade plan
- Returns JSON summary: scans succeeded/failed, total duration

## Read Route: `GET /api/screener/cached?scan_key=...`

- Reads single row from `cached_scans` by `scan_key`
- Returns `{ results, scanned_at }` or `{ results: null }` if no cache
- Cache-Control: `s-maxage=60, stale-while-revalidate=300`

## Frontend Hook Changes

Each hook (`useVomyScan`, `useGoldenGateScan`, `useMomentumScan`) adds:

1. **On mount**: Fetch cached results from `GET /api/screener/cached?scan_key=...`
2. **Display cached data** immediately with a timestamp banner
3. **Manual scan** still works (runs live scan, updates sessionStorage only)
4. **Refresh from cache** button re-fetches from Supabase

### Scan key mapping per hook

- `useMomentumScan` → `momentum:default`
- `useGoldenGateScan` → `golden_gate:{trading_mode}:{signal_type}`
- `useVomyScan` → `vomy:{timeframe}:{signal_type}`

Only the default configs have cached data. Other combos fall back to manual scan.

## UI: Cached Data Banner

Shown at the top of each screener tab when displaying cached data:

```
┌──────────────────────────────────────────────────┐
│ Premarket scan · Mar 3, 6:00 AM PST             │
│ [Refresh from cache]  [Run live scan]            │
└──────────────────────────────────────────────────┘
```

- `scanned_at` timestamp from Supabase
- "Refresh from cache" re-reads Supabase
- "Run live scan" runs the normal manual scan flow (sessionStorage only)
- Banner disappears when a live scan is active/completed

## vercel.json

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-screeners",
      "schedule": "0 14 * * 1-5"
    }
  ]
}
```

6:00 AM PST = 14:00 UTC. Weekdays only.

## Files Changed

### New files
- `frontend/src/app/api/cron/daily-screeners/route.ts` — cron handler
- `frontend/src/app/api/screener/cached/route.ts` — cache read endpoint
- `frontend/src/lib/run-screener-scans.ts` — shared scan execution logic

### Modified files
- `frontend/vercel.json` — replace old cron with new
- `frontend/src/hooks/use-vomy-scan.ts` — add cache hydration
- `frontend/src/hooks/use-golden-gate-scan.ts` — add cache hydration
- `frontend/src/hooks/use-momentum-scan.ts` — add cache hydration
- `frontend/src/components/screener/cached-scan-banner.tsx` — new UI component
- `frontend/src/app/screener/page.tsx` — integrate banner

### Removed files
- `frontend/src/app/api/cron/daily-plan/route.ts` — replaced by daily-screeners

## Supabase Migration

Run via Supabase dashboard or migration tool:

```sql
CREATE TABLE cached_scans (
  id         uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  scan_type  text NOT NULL,
  scan_key   text NOT NULL,
  results    jsonb NOT NULL,
  scanned_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(scan_key)
);

ALTER TABLE cached_scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read" ON cached_scans FOR SELECT USING (true);
```
