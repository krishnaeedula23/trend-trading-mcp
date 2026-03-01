# Golden Gate Scanner Design

## Context

The TOS Stock Hacker has a Saty ATR Levels Signals scanner that identifies stocks in the "golden gate zone" — the 38.2% Fibonacci ATR level above PDC. This is the primary entry zone for bullish trades. We want to replicate this as a screener tab alongside the existing momentum scanner.

**TOS scanner formula:**
```
Saty_ATR_Levels_Signals()."golden_gate_up" <= high
AND Saty_ATR_Levels_Signals()."midrange_up" > high
AND Saty_ATR_Levels_Signals()."pivot" <= close
```

**Translation:** Stock's high has reached/crossed the golden gate bull level (38.2%), hasn't reached midrange (61.8%), and current price is above PDC. The stock just entered the bullish "sweet spot" zone.

## Requirements

- **Default mode**: Day levels (daily ATR/PDC for intraday charts)
- **All modes**: Day, Multiday, Swing, Position
- **Signal types**: Golden Gate, Call Trigger, Put Trigger
- **Pre-market support**: Extended hours data for Day mode (4:00–9:30 AM ET)
- **Universe**: S&P 500 + Nasdaq 100 + Russell 2000 + custom watchlist tickers

## Signal Definitions

### Golden Gate Signal
| Direction | Condition |
|-----------|-----------|
| Bullish | `golden_gate_bull <= bar_high AND midrange_bull > bar_high AND pdc <= bar_close` |
| Bearish | `golden_gate_bear >= bar_low AND midrange_bear < bar_low AND pdc >= bar_close` |

### Call Trigger Signal
| Direction | Condition |
|-----------|-----------|
| Bullish | `call_trigger <= bar_high AND golden_gate_bull > bar_high AND pdc <= bar_close` |

### Put Trigger Signal
| Direction | Condition |
|-----------|-----------|
| Bearish | `put_trigger >= bar_low AND golden_gate_bear < bar_low AND pdc >= bar_close` |

Where `bar_high`/`bar_low`/`bar_close` come from:
- **Day mode + premarket**: premarket high/low/last (if available), else forming daily bar
- **Day mode (RTH)**: forming daily bar from `atr_source_df.iloc[-1]`
- **Other modes**: forming bar from ATR source data

## Architecture

### Backend: `POST /api/screener/golden-gate-scan`

**Approach**: Per-ticker ATR calculation using existing `atr_levels()` indicator. Unlike the momentum scanner (bulk yfinance download + vectorized math), golden gate needs the full ATR Levels stack per ticker. Pattern matches the existing `/scan` endpoint with `asyncio.Semaphore(10)`.

**Data flow per ticker:**
1. `_fetch_atr_source(ticker, mode)` → daily/weekly/monthly/quarterly bars
2. If day mode + `include_premarket`: `_fetch_premarket(ticker)` → 1-min extended hours bars
3. `atr_levels(atr_source_df)` → ATR, PDC, all Fibonacci levels
4. Extract bar_high/bar_low/bar_close from premarket data or forming bar
5. Apply signal formula → hit or skip

### Models

```python
class GoldenGateScanRequest(BaseModel):
    universes: list[str] = ["sp500", "nasdaq100"]
    trading_mode: Literal["day", "multiday", "swing", "position"] = "day"
    signal_type: Literal["golden_gate", "call_trigger", "put_trigger"] = "golden_gate"
    min_price: float = 4.0
    custom_tickers: list[str] | None = None
    include_premarket: bool = True  # Day mode only

class GoldenGateHit(BaseModel):
    ticker: str
    last_close: float
    signal: str           # "golden_gate" | "call_trigger" | "put_trigger"
    direction: str        # "bullish" | "bearish"
    pdc: float
    atr: float
    gate_level: float     # The signal level price
    midrange_level: float # Next resistance/support
    distance_pct: float   # % distance from signal level
    atr_status: str       # green/orange/red
    atr_covered_pct: float
    trend: str            # bullish/bearish/neutral
    trading_mode: str
    premarket_high: float | None = None
    premarket_low: float | None = None

class GoldenGateScanResponse(BaseModel):
    hits: list[GoldenGateHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    signal_type: str
    trading_mode: str
```

### Frontend

Follow the momentum scanner tab pattern:

| File | Purpose |
|------|---------|
| `hooks/use-golden-gate-scan.ts` | State + API call + sessionStorage persistence |
| `components/screener/golden-gate-controls.tsx` | Trading mode, signal type, universe, watchlist, premarket toggles |
| `components/screener/golden-gate-results-table.tsx` | Sortable results with signal info |
| `app/api/screener/golden-gate-scan/route.ts` | Proxy to Railway backend |
| `lib/types.ts` | TypeScript type additions |
| `app/screener/page.tsx` | Enable Golden Gate tab |

### Pre-market Data Strategy

For Day mode with `include_premarket=True`:
- Use `_fetch_premarket(ticker)` from `satyland.py` (already handles ^GSPC exclusion)
- ATR and PDC still come from **previous settled daily bar** (`iloc[-2]`)
- The `bar_high` for signal comparison = `premarket_df["high"].max()`
- The `bar_close` for signal comparison = `premarket_df["close"].iloc[-1]` (last tick)
- Graceful fallback: if no premarket data, use daily forming bar

## Performance

- Universe of ~700 tickers (SP500 + NASDAQ100)
- Semaphore(10) → ~70 batches of network calls
- Each ticker: 1 yfinance call for ATR source + 1 optional premarket call
- Estimated: 30–60 seconds for full scan
- Pre-market fetch adds ~5-10s overhead for day mode

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/endpoints/screener.py` | MODIFY — add golden gate scan models + endpoint |
| `frontend/src/lib/types.ts` | MODIFY — add GoldenGate TS types |
| `frontend/src/hooks/use-golden-gate-scan.ts` | CREATE |
| `frontend/src/components/screener/golden-gate-controls.tsx` | CREATE |
| `frontend/src/components/screener/golden-gate-results-table.tsx` | CREATE |
| `frontend/src/app/api/screener/golden-gate-scan/route.ts` | CREATE |
| `frontend/src/app/screener/page.tsx` | MODIFY — enable Golden Gate tab |
| `tests/api/test_golden_gate_scan.py` | CREATE |
