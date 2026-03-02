# VOMY 13/48 Conviction Crossover Design

## Goal

Add EMA 13/48 conviction crossover detection to the VOMY/iVOMY scanner. This enriches every hit with crossover data and lets users filter to conviction-confirmed signals only.

## Background

The TOS "Saty's Momentum Scanner" includes a 13/48 EMA crossover filter:

```
MovingAvgCrossover(length1 = 13, length2 = 48, averageType1 = "EXPONENTIAL",
                   averageType2 = "EXPONENTIAL") within 4 bars
```

"Within 4 bars" means the EMA13/EMA48 crossover occurred in the last 4 bars. The same crossover logic already exists in `api/indicators/satyland/pivot_ribbon.py` as the "conviction arrow."

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Filter vs enrichment | Both — enrichment + frontend toggle | All hits get conviction fields; users toggle to filter client-side |
| Direction alignment | Aligned only | VOMY (bearish) confirmed by bearish crossover; iVOMY by bullish crossover |
| Lookback window | Fixed at 4 bars | Matches TOS scanner exactly |
| Implementation approach | Inline in VOMY scanner | ~8 lines of code; VOMY scanner already has EMA13/EMA48 series computed |

## Backend Changes

### New fields on `VomyHit` (`api/endpoints/screener.py`)

```python
conviction_type: str | None       # "bullish_crossover" | "bearish_crossover" | None
conviction_bars_ago: int | None   # 1-4 or None (no crossover in window)
conviction_confirmed: bool        # True when conviction aligns with signal direction
```

### Conviction detection logic

After detecting a VOMY/iVOMY hit, keep the full EMA13 and EMA48 series (instead of only `.iloc[-1]`) and scan backward through 4 bars:

```python
ema13_series = close_series.ewm(span=13, adjust=False).mean()
ema48_series = close_series.ewm(span=48, adjust=False).mean()

conviction_type = None
conviction_bars_ago = None
for i in range(1, 5):  # bars_ago 1..4
    idx = -1 - i
    prev_above = ema13_series.iloc[idx] >= ema48_series.iloc[idx]
    curr_above = ema13_series.iloc[idx + 1] >= ema48_series.iloc[idx + 1]
    if not prev_above and curr_above:
        conviction_type = "bullish_crossover"
        conviction_bars_ago = i
        break
    elif prev_above and not curr_above:
        conviction_type = "bearish_crossover"
        conviction_bars_ago = i
        break

conviction_confirmed = (
    (signal == "vomy" and conviction_type == "bearish_crossover")
    or (signal == "ivomy" and conviction_type == "bullish_crossover")
)
```

No new request parameters. Conviction is always computed and returned.

## Frontend Changes

### TypeScript types (`frontend/src/lib/types.ts`)

Add to `VomyHit` interface:

```typescript
conviction_type: string | null
conviction_bars_ago: number | null
conviction_confirmed: boolean
```

### Results table (`vomy-results-table.tsx`)

- New "Conviction" column between ATR and Trend
- Badge rendering:
  - Confirmed bullish crossover: green badge `"Conv ↑ (Xb)"`
  - Confirmed bearish crossover: red badge `"Conv ↓ (Xb)"`
  - Unconfirmed crossover: gray badge with direction
  - No crossover: `"—"`
- "Conviction Only" filter toggle at top of table (local state, like sort state)
- `conviction` as sortable column (confirmed first, then by bars_ago)

### No changes needed

- **Controls** (`vomy-controls.tsx`): conviction toggle is a display filter, not a scan parameter
- **Hook** (`use-vomy-scan.ts`): passes through new fields
- **API route** (`vomy-scan/route.ts`): proxies request/response unchanged

## Files to Modify

| File | Action |
|------|--------|
| `api/endpoints/screener.py` | Add 3 fields to VomyHit, add conviction detection in `_process_ticker` |
| `frontend/src/lib/types.ts` | Add 3 fields to VomyHit interface |
| `frontend/src/components/screener/vomy-results-table.tsx` | Add conviction column, filter toggle, sort key |
| `tests/api/test_vomy_scan.py` | Add conviction-related test cases |

## Test Cases

| Test | Verifies |
|------|----------|
| `test_conviction_bullish_crossover_detected` | EMA13 crosses above EMA48 within 4 bars → bullish_crossover |
| `test_conviction_bearish_crossover_detected` | EMA13 crosses below EMA48 within 4 bars → bearish_crossover |
| `test_conviction_confirmed_ivomy_bullish` | iVOMY + bullish_crossover → confirmed=True |
| `test_conviction_confirmed_vomy_bearish` | VOMY + bearish_crossover → confirmed=True |
| `test_conviction_not_confirmed_mismatch` | VOMY + bullish_crossover → confirmed=False |
| `test_no_conviction_outside_window` | Crossover at bar 5+ → conviction_type=None |
| `test_conviction_bars_ago_correct` | Crossover at bar 2 → bars_ago=2 |
