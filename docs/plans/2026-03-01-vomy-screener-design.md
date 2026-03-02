# VOMY / iVOMY Screener Design

## Overview

Scan for trend transitions using the VOMY (bullish → bearish flip) and iVOMY
(bearish → bullish flip) EMA conditions. Inline EMA computation in the screener
endpoint (Approach A) — no separate indicator file.

## TOS Source

**VOMY** (bearish flip):

```
EMA(13) >= close          -- price dropped below short EMA
EMA(48) <= close          -- price still above long EMA
EMA(13) >= EMA(21)        -- ribbon stacked bearish
EMA(21) >= EMA(34)
EMA(34) >= EMA(48)
```

**iVOMY** (bullish flip): exact inverse of all comparisons.

## Backend

### Endpoint

`POST /api/screener/vomy-scan` in `api/endpoints/screener.py`.

### Request — `VomyScanRequest`

| Field              | Type                                     | Default      |
|--------------------|------------------------------------------|--------------|
| universes          | list[str]                                | required     |
| timeframe          | Literal["1h", "4h", "1d", "1w"]         | "1d"         |
| signal_type        | Literal["vomy", "ivomy", "both"]         | "both"       |
| min_price          | float (>= 0)                            | 4.0          |
| custom_tickers     | list[str] \| None                        | None         |
| include_premarket  | bool                                     | True         |

### Per-ticker scan logic

1. `_fetch_intraday(ticker, timeframe)` — get OHLCV at selected timeframe.
2. Compute 4 EMAs on close: `ewm(span=N, adjust=False)` for N = 13, 21, 34, 48.
3. Evaluate last bar values for VOMY / iVOMY conditions.
4. **Hits only**: enrich with ATR context via `_fetch_atr_source()` + `atr_levels()`
   using `_MODE_DEFAULT_TF` reverse mapping for the trading mode.
5. Concurrency: `asyncio.Semaphore(10)`, `asyncio.to_thread` for blocking calls.

### VOMY condition (last bar)

```python
ema13 >= close and ema48 <= close and ema13 >= ema21 >= ema34 >= ema48
```

### iVOMY condition (last bar)

```python
ema13 <= close and ema48 >= close and ema13 <= ema21 <= ema34 <= ema48
```

### Response — `VomyScanResponse`

```
hits: list[VomyHit]
total_scanned, total_hits, total_errors, skipped_low_price
scan_duration_seconds, signal_type, timeframe
```

### VomyHit fields

ticker, last_close, signal (vomy/ivomy), ema13, ema21, ema34, ema48,
distance_from_ema48_pct, atr, pdc, atr_status, atr_covered_pct,
trend, trading_mode, timeframe.

### Sorting

By `distance_from_ema48_pct` ascending — freshest transitions first.

## Frontend

### New tab

"VOMY" tab in the screener page alongside Golden Gate and Momentum.

### Files

| File                          | Purpose                              |
|-------------------------------|--------------------------------------|
| `use-vomy-scan.ts`           | Hook: sessionStorage, abort, SSR     |
| `vomy-controls.tsx`          | Signal type, timeframe, universes    |
| `vomy-results-table.tsx`     | Sortable table with signal badges    |
| `vomy-scan/route.ts`         | Next.js API proxy                    |

### Controls

- Signal type toggle: VOMY / iVOMY / Both (default: Both)
- Timeframe buttons: 1h, 4h, Daily, Weekly (default: Daily)
- Universe toggles + watchlist toggles
- Min price input
- Premarket toggle (visible for 1h/4h only)
- Run / Cancel button + status bar

### Results table columns

Ticker, Close, Signal (badge), EMA13, EMA21, EMA34, EMA48,
Distance%, ATR Status, Trend. Save as Idea button per row.

### Signal badges

- VOMY: red/orange (`bg-red-600/20 text-red-400`)
- iVOMY: green/teal (`bg-teal-600/20 text-teal-400`)

### Types (in `types.ts`)

- `VomySignalType = "vomy" | "ivomy" | "both"`
- `VomyHit`, `VomyScanResponse`, `VomyScanConfig` interfaces

## Testing

`tests/api/test_vomy_scan.py` following golden gate test pattern.

### Synthetic data helpers

- `_make_vomy_daily()` — last bar satisfies VOMY EMA conditions
- `_make_ivomy_daily()` — last bar satisfies iVOMY conditions

### Mock pattern

Patch `_fetch_intraday`, `_fetch_atr_source`, `_fetch_premarket`,
`resolve_use_current_close` (4-mock pattern from golden gate tests).

### Test cases

1. Returns 200 with valid request
2. Response shape validation
3. VOMY signal detected with correct fields
4. iVOMY signal detected
5. "both" mode returns mixed signals
6. Price filter excludes cheap stocks
7. Custom tickers merged
8. Timeframe parameter passed through
9. Fetch error counted gracefully
