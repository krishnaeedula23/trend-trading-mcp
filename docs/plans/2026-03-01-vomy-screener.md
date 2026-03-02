# VOMY / iVOMY Screener Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a VOMY/iVOMY trend-transition screener that scans for EMA ribbon flips across selectable timeframes, with ATR context for hits.

**Architecture:** Inline EMA computation in the screener endpoint (no separate indicator file). Per-ticker async processing with Semaphore(10). EMA check is cheap; ATR context fetched only for hits. Frontend follows the existing golden gate tab pattern.

**Tech Stack:** Python (pandas ewm), FastAPI, Next.js 16, React 19, shadcn/ui, Vitest

---

### Task 1: TypeScript types for VOMY scanner

**Files:**
- Modify: `frontend/src/lib/types.ts` (append after line 416)

**Step 1: Add VOMY types to types.ts**

Append after the GoldenGateScanResponse interface (end of file):

```typescript
// ---------------------------------------------------------------------------
// VOMY / iVOMY Scanner
// ---------------------------------------------------------------------------

export type VomySignalType = "vomy" | "ivomy" | "both"

export type VomyTimeframe = "1h" | "4h" | "1d" | "1w"

export interface VomyHit {
  ticker: string
  last_close: number
  signal: "vomy" | "ivomy"
  ema13: number
  ema21: number
  ema34: number
  ema48: number
  distance_from_ema48_pct: number
  atr: number
  pdc: number
  atr_status: AtrStatus
  atr_covered_pct: number
  trend: Trend
  trading_mode: TradingMode
  timeframe: VomyTimeframe
}

export interface VomyScanRequest {
  universes: string[]
  timeframe: VomyTimeframe
  signal_type: VomySignalType
  min_price: number
  custom_tickers?: string[]
  include_premarket: boolean
}

export interface VomyScanResponse {
  hits: VomyHit[]
  total_scanned: number
  total_hits: number
  total_errors: number
  skipped_low_price: number
  scan_duration_seconds: number
  signal_type: VomySignalType
  timeframe: VomyTimeframe
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds (types only, no consumers yet)

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add TypeScript types for VOMY/iVOMY scanner"
```

---

### Task 2: Backend VOMY scan endpoint + tests

**Files:**
- Modify: `api/endpoints/screener.py` (append after golden gate section, ~line 745)
- Create: `tests/api/test_vomy_scan.py`

**Step 1: Write the test file**

Create `tests/api/test_vomy_scan.py`:

```python
"""Tests for the VOMY / iVOMY scanner endpoint."""

import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Universe fixture data
# ---------------------------------------------------------------------------

UNIVERSE = {
    "sp500": ["AAPL", "MSFT"],
    "nasdaq100": ["AAPL", "TSLA"],
    "all_unique": ["AAPL", "MSFT", "TSLA"],
    "counts": {"sp500": 2, "nasdaq100": 2, "all_unique": 3},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """FastAPI test client."""
    from api.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_schwab_token():
    """Skip the Schwab token check for all VOMY tests."""
    with patch("api.endpoints.schwab.token_exists", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_universe(tmp_path):
    """Write a small test universe.json and patch UNIVERSE_PATH."""
    universe_file = tmp_path / "universe.json"
    universe_file.write_text(json.dumps(UNIVERSE))

    with patch("api.endpoints.screener.UNIVERSE_PATH", universe_file):
        yield universe_file


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------


def _make_daily_df(
    base_price: float = 100.0, days: int = 60, growth: float = 0.0
) -> pd.DataFrame:
    """Generate synthetic daily OHLCV with optional linear growth."""
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    growth_arr = np.linspace(0, growth, days)
    prices = np.full(days, base_price) + growth_arr

    return pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )


def _make_vomy_daily(base_price: float = 100.0, days: int = 60) -> pd.DataFrame:
    """Build daily data where the last bar triggers a VOMY (bearish flip) signal.

    VOMY: EMA13 >= close AND EMA48 <= close AND EMA13 >= EMA21 >= EMA34 >= EMA48

    Strategy: flat prices so all EMAs converge near base_price, then drop the
    last bar's close slightly below EMA13 but above EMA48.
    With flat data, EMAs converge to base_price (shorter EMAs converge faster).
    After convergence: EMA13 ≈ EMA21 ≈ EMA34 ≈ EMA48 ≈ base_price.
    A tiny downtrend makes shorter EMAs slightly higher (they react faster to
    the dip and overshoot less), so EMA13 >= EMA21 >= EMA34 >= EMA48.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    # Slight downtrend in last few bars so shorter EMAs > longer EMAs
    prices = np.full(days, base_price)
    # Add a mild decline in the last 10 bars
    for i in range(max(0, days - 10), days):
        offset = (i - (days - 10)) * 0.05
        prices[i] = base_price + offset  # goes from 100 to 99.55

    df = pd.DataFrame(
        {
            "open": prices * 1.001,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Compute EMAs to verify and adjust last bar
    close = df["close"]
    ema13 = float(close.ewm(span=13, adjust=False).mean().iloc[-1])
    ema48 = float(close.ewm(span=48, adjust=False).mean().iloc[-1])

    # Set last bar close between EMA48 and EMA13 but below EMA13
    # close < ema13 (so ema13 >= close) and close > ema48 (so ema48 <= close)
    target_close = (ema13 + ema48) / 2 - 0.1  # slightly below midpoint
    if target_close >= ema13:
        target_close = ema13 - 0.05
    if target_close <= ema48:
        target_close = ema48 + 0.05

    df.iloc[-1, df.columns.get_loc("close")] = target_close

    return df


def _make_ivomy_daily(base_price: float = 100.0, days: int = 60) -> pd.DataFrame:
    """Build daily data where the last bar triggers an iVOMY (bullish flip) signal.

    iVOMY: EMA13 <= close AND EMA48 >= close AND EMA13 <= EMA21 <= EMA34 <= EMA48

    Strategy: flat prices with slight uptrend at end, then set close above EMA13
    but below EMA48.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.full(days, base_price)
    # Add a mild incline in the last 10 bars
    for i in range(max(0, days - 10), days):
        offset = (i - (days - 10)) * 0.05
        prices[i] = base_price - offset  # goes from 100 to 100.45

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Compute EMAs to verify and adjust last bar
    close = df["close"]
    ema13 = float(close.ewm(span=13, adjust=False).mean().iloc[-1])
    ema48 = float(close.ewm(span=48, adjust=False).mean().iloc[-1])

    # Set last bar close between EMA13 and EMA48 but above EMA13
    target_close = (ema13 + ema48) / 2 + 0.1
    if target_close <= ema13:
        target_close = ema13 + 0.05
    if target_close >= ema48:
        target_close = ema48 - 0.05

    df.iloc[-1, df.columns.get_loc("close")] = target_close

    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVomyScan:
    """Tests for POST /api/screener/vomy-scan."""

    def _mock_fetch(
        self, intraday_df: pd.DataFrame, atr_source_df: pd.DataFrame | None = None
    ):
        """Return context managers that patch data-fetching helpers."""
        if atr_source_df is None:
            atr_source_df = intraday_df
        return (
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=lambda ticker, tf: intraday_df,
            ),
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=lambda ticker, mode: atr_source_df,
            ),
            patch(
                "api.endpoints.screener._fetch_premarket",
                side_effect=lambda ticker: None,
            ),
            patch(
                "api.endpoints.screener.resolve_use_current_close",
                return_value=False,
            ),
        )

    # 1. Happy path returns 200
    def test_returns_200(self, client):
        daily = _make_daily_df(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        assert resp.status_code == 200

    # 2. Response shape
    def test_response_shape(self, client):
        daily = _make_daily_df(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        data = resp.json()
        for field in [
            "hits",
            "total_scanned",
            "total_hits",
            "total_errors",
            "skipped_low_price",
            "scan_duration_seconds",
            "signal_type",
            "timeframe",
        ]:
            assert field in data, f"Missing top-level field: {field}"

    # 3. VOMY signal detected
    def test_vomy_signal_detected(self, client):
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "vomy",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "vomy"
        assert data["total_hits"] > 0
        hit = data["hits"][0]
        assert hit["signal"] == "vomy"
        for field in [
            "ticker",
            "last_close",
            "ema13",
            "ema21",
            "ema34",
            "ema48",
            "distance_from_ema48_pct",
            "atr",
            "pdc",
            "atr_status",
            "atr_covered_pct",
            "trend",
            "trading_mode",
            "timeframe",
        ]:
            assert field in hit, f"Missing hit field: {field}"

    # 4. iVOMY signal detected
    def test_ivomy_signal_detected(self, client):
        daily = _make_ivomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "ivomy",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "ivomy"
        assert data["total_hits"] > 0
        for hit in data["hits"]:
            assert hit["signal"] == "ivomy"

    # 5. "both" mode returns mixed signals
    def test_signal_type_both(self, client):
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "both",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "both"
        # Should find hits (at least vomy from our synthetic data)
        for hit in data["hits"]:
            assert hit["signal"] in ("vomy", "ivomy")

    # 6. Price filter
    def test_price_filter(self, client):
        daily = _make_daily_df(base_price=2.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "min_price": 4.0},
            )

        data = resp.json()
        assert data["total_hits"] == 0
        assert data["skipped_low_price"] > 0

    # 7. Custom tickers merged
    def test_custom_tickers_merged(self, client):
        daily = _make_daily_df(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "custom_tickers": ["NVDA", "GOOG"],
                },
            )

        data = resp.json()
        # sp500 has 2 unique + 2 custom = 4 total
        assert data["total_scanned"] == 4

    # 8. Timeframe parameter passed through
    def test_timeframe_passed(self, client):
        daily = _make_daily_df(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "timeframe": "1h"},
            )

        data = resp.json()
        assert data["timeframe"] == "1h"

    # 9. Fetch error counted gracefully
    def test_fetch_error_counted(self, client):
        with (
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=RuntimeError("yfinance down"),
            ),
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=RuntimeError("yfinance down"),
            ),
            patch(
                "api.endpoints.screener._fetch_premarket",
                side_effect=lambda ticker: None,
            ),
            patch(
                "api.endpoints.screener.resolve_use_current_close",
                return_value=False,
            ),
        ):
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        data = resp.json()
        assert data["total_errors"] > 0
        assert data["total_hits"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `/Users/krishnaeedula/claude/trend-trading-mcp/.venv/bin/python -m pytest tests/api/test_vomy_scan.py -v --noconftest`
Expected: FAIL — endpoint `/api/screener/vomy-scan` does not exist (404)

**Step 3: Write the backend endpoint**

Append to `api/endpoints/screener.py` after line 745 (end of golden gate section):

```python
# ---------------------------------------------------------------------------
# VOMY / iVOMY Scanner — EMA ribbon flip detection
# ---------------------------------------------------------------------------


class VomyScanRequest(BaseModel):
    """Request for the VOMY/iVOMY trend-transition scanner."""

    universes: list[str] = Field(
        default=["sp500", "nasdaq100"],
        description="Universe keys: sp500, nasdaq100, russell2000, or all",
    )
    timeframe: Literal["1h", "4h", "1d", "1w"] = Field(
        default="1d",
        description="Chart timeframe to compute EMAs on",
    )
    signal_type: Literal["vomy", "ivomy", "both"] = Field(
        default="both",
        description="Signal type: vomy (bearish flip), ivomy (bullish flip), or both",
    )
    min_price: float = Field(default=4.0, ge=0, description="Minimum price filter")
    custom_tickers: list[str] | None = Field(
        default=None,
        max_length=500,
        description="Extra tickers to include",
    )
    include_premarket: bool = Field(
        default=True,
        description="Use premarket close for intraday timeframes",
    )


class VomyHit(BaseModel):
    """A stock that triggered a VOMY or iVOMY signal."""

    ticker: str
    last_close: float
    signal: str  # "vomy" or "ivomy"
    ema13: float
    ema21: float
    ema34: float
    ema48: float
    distance_from_ema48_pct: float
    atr: float
    pdc: float
    atr_status: str
    atr_covered_pct: float
    trend: str
    trading_mode: str
    timeframe: str


class VomyScanResponse(BaseModel):
    """Response for the VOMY/iVOMY scanner."""

    hits: list[VomyHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    signal_type: str
    timeframe: str


def _check_vomy_signal(
    close: float,
    ema13: float,
    ema21: float,
    ema34: float,
    ema48: float,
    signal_type: str,
) -> str | None:
    """Check if EMA values satisfy VOMY or iVOMY conditions.

    VOMY (bearish flip):
      EMA13 >= close AND EMA48 <= close AND EMA13 >= EMA21 >= EMA34 >= EMA48
    iVOMY (bullish flip):
      EMA13 <= close AND EMA48 >= close AND EMA13 <= EMA21 <= EMA34 <= EMA48

    Returns "vomy", "ivomy", or None.
    """
    if signal_type in ("vomy", "both"):
        if (
            ema13 >= close
            and ema48 <= close
            and ema13 >= ema21 >= ema34 >= ema48
        ):
            return "vomy"

    if signal_type in ("ivomy", "both"):
        if (
            ema13 <= close
            and ema48 >= close
            and ema13 <= ema21 <= ema34 <= ema48
        ):
            return "ivomy"

    return None


# Timeframe → default ATR trading mode for enrichment
_VOMY_TF_TO_MODE: dict[str, str] = {
    "1h": "multiday",
    "4h": "multiday",
    "1d": "swing",
    "1w": "position",
}


@router.post("/vomy-scan")
async def vomy_scan(request: VomyScanRequest) -> VomyScanResponse:
    """Scan universe for VOMY/iVOMY trend-transition signals.

    For each ticker, computes EMA(13,21,34,48) on the selected timeframe
    and checks for ribbon flip conditions. Hits are enriched with ATR
    context for trend/status information.
    """
    t0 = time.monotonic()

    # Build ticker list
    tickers = await asyncio.to_thread(_load_universe, request.universes)
    if request.custom_tickers:
        existing = set(tickers)
        for t in request.custom_tickers:
            upper = t.strip().upper()
            if upper and upper not in existing:
                tickers.append(upper)
                existing.add(upper)

    logger.info(
        "VOMY scan: %d tickers, tf=%s, signal=%s",
        len(tickers),
        request.timeframe,
        request.signal_type,
    )

    ucc = resolve_use_current_close()
    sem = asyncio.Semaphore(10)
    hits: list[VomyHit] = []
    errors = 0
    skipped_low_price = 0
    trading_mode = _VOMY_TF_TO_MODE.get(request.timeframe, "swing")

    async def _process_ticker(ticker: str) -> VomyHit | None:
        nonlocal errors, skipped_low_price
        async with sem:
            try:
                # 1. Fetch OHLCV at selected timeframe
                intraday_df = await asyncio.to_thread(
                    _fetch_intraday, ticker, request.timeframe
                )

                # 2. Compute 4 EMAs on close
                close_series = intraday_df["close"]
                ema13_s = close_series.ewm(span=13, adjust=False).mean()
                ema21_s = close_series.ewm(span=21, adjust=False).mean()
                ema34_s = close_series.ewm(span=34, adjust=False).mean()
                ema48_s = close_series.ewm(span=48, adjust=False).mean()

                last_close = float(close_series.iloc[-1])
                ema13 = float(ema13_s.iloc[-1])
                ema21 = float(ema21_s.iloc[-1])
                ema34 = float(ema34_s.iloc[-1])
                ema48 = float(ema48_s.iloc[-1])

                # Price filter
                if last_close < request.min_price:
                    skipped_low_price += 1
                    return None

                # 3. Check VOMY/iVOMY condition
                signal = _check_vomy_signal(
                    last_close, ema13, ema21, ema34, ema48, request.signal_type
                )
                if signal is None:
                    return None

                # 4. Enrich hits with ATR context
                atr_source_df = await asyncio.to_thread(
                    _fetch_atr_source, ticker, trading_mode
                )
                atr_result = atr_levels(
                    atr_source_df,
                    intraday_df=intraday_df,
                    trading_mode=trading_mode,
                    use_current_close=ucc,
                )

                # Distance from EMA48
                dist = ((last_close - ema48) / ema48) * 100 if ema48 > 0 else 0.0

                return VomyHit(
                    ticker=ticker.upper(),
                    last_close=round(last_close, 2),
                    signal=signal,
                    ema13=round(ema13, 4),
                    ema21=round(ema21, 4),
                    ema34=round(ema34, 4),
                    ema48=round(ema48, 4),
                    distance_from_ema48_pct=round(dist, 2),
                    atr=atr_result["atr"],
                    pdc=atr_result["pdc"],
                    atr_status=atr_result["atr_status"],
                    atr_covered_pct=atr_result["atr_covered_pct"],
                    trend=atr_result["trend"],
                    trading_mode=trading_mode,
                    timeframe=request.timeframe,
                )
            except Exception as exc:
                logger.debug("VOMY scan error for %s: %s", ticker, exc)
                errors += 1
                return None

    results = await asyncio.gather(*(_process_ticker(t) for t in tickers))
    hits = [r for r in results if r is not None]
    hits.sort(key=lambda h: abs(h.distance_from_ema48_pct))
    elapsed = round(time.monotonic() - t0, 2)

    return VomyScanResponse(
        hits=hits,
        total_scanned=len(tickers),
        total_hits=len(hits),
        total_errors=errors,
        skipped_low_price=skipped_low_price,
        scan_duration_seconds=elapsed,
        signal_type=request.signal_type,
        timeframe=request.timeframe,
    )
```

**Step 4: Run tests to verify they pass**

Run: `/Users/krishnaeedula/claude/trend-trading-mcp/.venv/bin/python -m pytest tests/api/test_vomy_scan.py -v --noconftest`
Expected: All 9 tests PASS

Note: the synthetic data helpers may need fine-tuning to ensure VOMY/iVOMY conditions
are reliably met. If `test_vomy_signal_detected` or `test_ivomy_signal_detected` fail,
adjust the price trajectory in `_make_vomy_daily` / `_make_ivomy_daily` to ensure
the EMA ordering condition is satisfied. Debug by printing the 4 EMA values and close.

**Step 5: Run lint**

Run: `uv tool run ruff check api/endpoints/screener.py tests/api/test_vomy_scan.py && uv tool run ruff format --check api/endpoints/screener.py tests/api/test_vomy_scan.py`
Expected: All checks passed

**Step 6: Commit**

```bash
git add api/endpoints/screener.py tests/api/test_vomy_scan.py
git commit -m "feat: add VOMY/iVOMY scanner endpoint POST /api/screener/vomy-scan"
```

---

### Task 3: Next.js API route proxy

**Files:**
- Create: `frontend/src/app/api/screener/vomy-scan/route.ts`

**Step 1: Create the proxy route**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';
import { RailwayError } from '@/lib/errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await railwayFetch('/api/screener/vomy-scan', body);
    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json(
        { error: error.detail, code: error.code },
        { status: error.status }
      );
    }
    console.error('Screener vomy-scan error:', error);
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'NETWORK_ERROR' },
      { status: 502 }
    );
  }
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/app/api/screener/vomy-scan/route.ts
git commit -m "feat: add VOMY scan API route proxy"
```

---

### Task 4: useVomyScan hook

**Files:**
- Create: `frontend/src/hooks/use-vomy-scan.ts`

**Step 1: Create the hook**

Model after `use-golden-gate-scan.ts` with sessionStorage persistence, AbortController, SSR-safe hydration:

```typescript
"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type {
  VomyScanRequest,
  VomyScanResponse,
  VomyHit,
  VomySignalType,
  VomyTimeframe,
} from "@/lib/types"

export interface VomyScanConfig {
  universes: string[]
  timeframe: VomyTimeframe
  signal_type: VomySignalType
  min_price: number
  include_premarket: boolean
  custom_tickers?: string[]
}

interface UseVomyScanReturn {
  hits: VomyHit[]
  scanning: boolean
  response: VomyScanResponse | null
  config: VomyScanConfig
  error: string | null
  runScan: (config: VomyScanConfig) => void
  cancelScan: () => void
}

const STORAGE_KEY = "vomy_scan_results"
const CONFIG_KEY = "vomy_scan_config"

const DEFAULT_CONFIG: VomyScanConfig = {
  universes: ["sp500", "nasdaq100"],
  timeframe: "1d",
  signal_type: "both",
  min_price: 4.0,
  include_premarket: true,
}

// --- Session storage helpers ---

function saveResponse(data: VomyScanResponse | null) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResponse(): VomyScanResponse | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as VomyScanResponse
  } catch {
    return null
  }
}

function saveConfig(config: VomyScanConfig) {
  try {
    const { custom_tickers: _, ...persistable } = config
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(persistable))
  } catch {
    // ignore
  }
}

function loadConfig(): VomyScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return DEFAULT_CONFIG
    return JSON.parse(raw) as VomyScanConfig
  } catch {
    return DEFAULT_CONFIG
  }
}

// --- Hook ---

export function useVomyScan(): UseVomyScanReturn {
  const [hits, setHits] = useState<VomyHit[]>([])
  const [scanning, setScanning] = useState(false)
  const [response, setResponse] = useState<VomyScanResponse | null>(null)
  const [config, setConfig] = useState<VomyScanConfig>(DEFAULT_CONFIG)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const hydrated = useRef(false)

  // Hydrate from sessionStorage on mount
  useEffect(() => {
    if (hydrated.current) return
    hydrated.current = true
    const saved = loadResponse()
    if (saved) {
      setHits(saved.hits)
      setResponse(saved)
    }
    setConfig(loadConfig())
  }, [])

  const runScan = useCallback(
    async (newConfig: VomyScanConfig) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setConfig(newConfig)
      saveConfig(newConfig)

      setHits([])
      setResponse(null)
      setError(null)
      saveResponse(null)
      setScanning(true)

      try {
        const body: VomyScanRequest = {
          universes: newConfig.universes,
          timeframe: newConfig.timeframe,
          signal_type: newConfig.signal_type,
          min_price: newConfig.min_price,
          include_premarket: newConfig.include_premarket,
          ...(newConfig.custom_tickers?.length && { custom_tickers: newConfig.custom_tickers }),
        }

        const res = await fetch("/api/screener/vomy-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Unknown error" }))
          const msg = err.error ?? `HTTP ${res.status}`
          console.error("VOMY scan failed:", msg)
          setError(msg)
          return
        }

        const data: VomyScanResponse = await res.json()
        setHits(data.hits)
        setResponse(data)
        saveResponse(data)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        const msg = err instanceof Error ? err.message : "Network error"
        console.error("VOMY scan failed:", msg)
        setError(msg)
      } finally {
        setScanning(false)
      }
    },
    []
  )

  const cancelScan = useCallback(() => {
    abortRef.current?.abort()
    setScanning(false)
  }, [])

  return { hits, scanning, response, config, error, runScan, cancelScan }
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/hooks/use-vomy-scan.ts
git commit -m "feat: add useVomyScan hook with sessionStorage persistence"
```

---

### Task 5: VOMY controls component

**Files:**
- Create: `frontend/src/components/screener/vomy-controls.tsx`

**Step 1: Create the controls component**

Model after `golden-gate-controls.tsx` — signal type, timeframe, universes, watchlists, min price, premarket toggle, run/cancel, status bar:

```typescript
"use client"

import { useState } from "react"
import { Play, Square, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type {
  VomyScanResponse,
  VomySignalType,
  VomyTimeframe,
  Watchlist,
} from "@/lib/types"

interface VomyControlsProps {
  scanning: boolean
  response: VomyScanResponse | null
  error: string | null
  watchlists: Watchlist[]
  initialUniverses: string[]
  initialMinPrice: number
  initialTimeframe: VomyTimeframe
  initialSignalType: VomySignalType
  initialIncludePremarket: boolean
  onScan: (config: {
    universes: string[]
    timeframe: VomyTimeframe
    signal_type: VomySignalType
    min_price: number
    include_premarket: boolean
    custom_tickers?: string[]
  }) => void
  onCancel: () => void
}

const UNIVERSE_OPTIONS = [
  { key: "sp500", label: "S&P 500" },
  { key: "nasdaq100", label: "Nasdaq 100" },
  { key: "russell2000", label: "Russell 2000" },
] as const

const TIMEFRAME_OPTIONS: { key: VomyTimeframe; label: string }[] = [
  { key: "1h", label: "1H" },
  { key: "4h", label: "4H" },
  { key: "1d", label: "Daily" },
  { key: "1w", label: "Weekly" },
]

const SIGNAL_TYPE_OPTIONS: { key: VomySignalType; label: string }[] = [
  { key: "both", label: "Both" },
  { key: "vomy", label: "VOMY" },
  { key: "ivomy", label: "iVOMY" },
]

const SIGNAL_LABEL: Record<VomySignalType, string> = {
  both: "VOMY + iVOMY",
  vomy: "VOMY",
  ivomy: "iVOMY",
}

const TF_LABEL: Record<VomyTimeframe, string> = {
  "1h": "1H",
  "4h": "4H",
  "1d": "Daily",
  "1w": "Weekly",
}

export function VomyControls({
  scanning,
  response,
  error,
  watchlists,
  initialUniverses,
  initialMinPrice,
  initialTimeframe,
  initialSignalType,
  initialIncludePremarket,
  onScan,
  onCancel,
}: VomyControlsProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initialUniverses))
  const [selectedWatchlists, setSelectedWatchlists] = useState<Set<string>>(new Set())
  const [minPrice, setMinPrice] = useState(initialMinPrice)
  const [timeframe, setTimeframe] = useState<VomyTimeframe>(initialTimeframe)
  const [signalType, setSignalType] = useState<VomySignalType>(initialSignalType)
  const [includePremarket, setIncludePremarket] = useState(initialIncludePremarket)

  function toggleUniverse(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleWatchlist(id: string) {
    setSelectedWatchlists((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleRun() {
    if (selected.size === 0 && selectedWatchlists.size === 0) return

    const customTickers = watchlists
      .filter((w) => selectedWatchlists.has(w.id))
      .flatMap((w) => w.tickers)
    const unique = [...new Set(customTickers)]

    onScan({
      universes: Array.from(selected),
      timeframe,
      signal_type: signalType,
      min_price: minPrice,
      include_premarket: includePremarket,
      ...(unique.length > 0 && { custom_tickers: unique }),
    })
  }

  const sourceLabels = [
    ...UNIVERSE_OPTIONS.filter((u) => selected.has(u.key)).map((u) => u.label),
    ...watchlists.filter((w) => selectedWatchlists.has(w.id)).map((w) => w.name),
  ].join(" + ")

  const showPremarket = timeframe === "1h" || timeframe === "4h"

  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* Signal Type */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Signal</Label>
          <div className="flex gap-1.5">
            {SIGNAL_TYPE_OPTIONS.map((s) => (
              <Button
                key={s.key}
                size="sm"
                variant={signalType === s.key ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => setSignalType(s.key)}
                disabled={scanning}
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Timeframe */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Timeframe</Label>
          <div className="flex gap-1.5">
            {TIMEFRAME_OPTIONS.map((tf) => (
              <Button
                key={tf.key}
                size="sm"
                variant={timeframe === tf.key ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => setTimeframe(tf.key)}
                disabled={scanning}
              >
                {tf.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Universe toggles */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Universe</Label>
          <div className="flex gap-1.5">
            {UNIVERSE_OPTIONS.map((u) => (
              <Button
                key={u.key}
                size="sm"
                variant={selected.has(u.key) ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => toggleUniverse(u.key)}
                disabled={scanning}
              >
                {u.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Watchlist toggles */}
        {watchlists.length > 0 && (
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Watchlists</Label>
            <div className="flex gap-1.5 flex-wrap">
              {watchlists.map((w) => (
                <Button
                  key={w.id}
                  size="sm"
                  variant={selectedWatchlists.has(w.id) ? "default" : "outline"}
                  className="h-7 text-xs"
                  onClick={() => toggleWatchlist(w.id)}
                  disabled={scanning}
                >
                  {w.name}
                  <span className="ml-1 text-muted-foreground">({w.tickers.length})</span>
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Min price */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Min Price</Label>
          <Input
            type="number"
            value={minPrice}
            onChange={(e) => setMinPrice(Number(e.target.value))}
            className="h-7 w-20 text-xs"
            min={0}
            step={1}
            disabled={scanning}
          />
        </div>

        {/* Pre-Market toggle (intraday only) */}
        {showPremarket && (
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Pre-Market</Label>
            <Button
              size="sm"
              variant={includePremarket ? "default" : "outline"}
              className="h-7 text-xs"
              onClick={() => setIncludePremarket((p) => !p)}
              disabled={scanning}
            >
              {includePremarket ? "On" : "Off"}
            </Button>
          </div>
        )}

        {/* Run / Cancel */}
        <div className="flex gap-2">
          {scanning ? (
            <Button size="sm" variant="destructive" className="h-7 text-xs" onClick={onCancel}>
              <Square className="mr-1 size-3" /> Cancel
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={handleRun}
              disabled={selected.size === 0 && selectedWatchlists.size === 0}
            >
              <Play className="mr-1 size-3" /> Run Scan
            </Button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {scanning && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          Scanning {sourceLabels} for {SIGNAL_LABEL[signalType]} ({TF_LABEL[timeframe]})...
        </div>
      )}
      {error && !scanning && (
        <div className="flex items-center gap-2 text-xs text-red-400">
          <AlertCircle className="size-3" />
          Scan failed: {error}
        </div>
      )}
      {response && !scanning && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>{response.total_hits} hits</span>
          <span>&middot;</span>
          <span>{response.total_scanned} scanned</span>
          <span>&middot;</span>
          <span>{response.skipped_low_price} below ${minPrice}</span>
          <span>&middot;</span>
          <span>{response.total_errors} errors</span>
          <span>&middot;</span>
          <span>{response.scan_duration_seconds}s</span>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/screener/vomy-controls.tsx
git commit -m "feat: add VOMY controls component"
```

---

### Task 6: VOMY results table component

**Files:**
- Create: `frontend/src/components/screener/vomy-results-table.tsx`

**Step 1: Create the results table**

Model after `golden-gate-results-table.tsx` with sortable columns, signal badges, Save as Idea:

```typescript
"use client"

import { useState, useMemo } from "react"
import { ArrowUpDown, Save, Loader2, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { VomyHit, AtrStatus, Trend } from "@/lib/types"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

type SortKey = "ticker" | "last_close" | "distance" | "atr_covered" | "ema13" | "trend"

// --- Badge helpers ---

function signalBadge(signal: "vomy" | "ivomy"): { text: string; color: string } {
  switch (signal) {
    case "vomy":
      return { text: "VOMY", color: "bg-red-600/20 text-red-400 border-red-600/30" }
    case "ivomy":
      return { text: "iVOMY", color: "bg-teal-600/20 text-teal-400 border-teal-600/30" }
  }
}

function atrStatusBadge(status: AtrStatus): { text: string; color: string } {
  switch (status) {
    case "green":
      return { text: "Room", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    case "orange":
      return { text: "Warning", color: "bg-amber-600/20 text-amber-400 border-amber-600/30" }
    case "red":
      return { text: "Extended", color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
}

function trendColor(trend: Trend): string {
  switch (trend) {
    case "bullish":
      return "text-emerald-400"
    case "bearish":
      return "text-red-400"
    case "neutral":
      return "text-zinc-400"
  }
}

function trendLabel(trend: Trend): string {
  switch (trend) {
    case "bullish":
      return "Bull"
    case "bearish":
      return "Bear"
    case "neutral":
      return "Neutral"
  }
}

// --- Save as Idea button ---

function SaveButton({ hit }: { hit: VomyHit }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: hit.ticker,
        direction: hit.signal === "ivomy" ? "bullish" : "bearish",
        timeframe: hit.timeframe,
        status: "watching",
        current_price: hit.last_close,
        tags: [
          "source:screener",
          "screener:vomy",
          `signal:${hit.signal}`,
          `atr:${hit.atr_status}`,
        ],
        source: "screener",
        notes: `${hit.signal.toUpperCase()} scanner hit — EMA ribbon flip on ${hit.timeframe}, dist ${hit.distance_from_ema48_pct > 0 ? "+" : ""}${hit.distance_from_ema48_pct.toFixed(1)}% from EMA48, ATR ${hit.atr_covered_pct.toFixed(0)}% (${hit.atr_status})`,
      })
      setSaved(true)
      toast.success(`${hit.ticker} saved as idea`)
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Button
      size="sm"
      variant="ghost"
      className="h-7 w-7 p-0"
      disabled={saving || saved}
      onClick={handleSave}
      title={saved ? "Saved" : "Save as idea"}
    >
      {saving ? (
        <Loader2 className="size-3.5 animate-spin" />
      ) : saved ? (
        <CheckCircle2 className="size-3.5 text-emerald-400" />
      ) : (
        <Save className="size-3.5" />
      )}
    </Button>
  )
}

// --- Main table ---

export function VomyResultsTable({ hits }: { hits: VomyHit[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("distance")
  const [sortAsc, setSortAsc] = useState(true)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((p) => !p)
    else {
      setSortKey(key)
      setSortAsc(key === "distance")
    }
  }

  const sorted = useMemo(() => {
    const arr = [...hits]
    const dir = sortAsc ? 1 : -1
    arr.sort((a, b) => {
      switch (sortKey) {
        case "ticker":
          return dir * a.ticker.localeCompare(b.ticker)
        case "last_close":
          return dir * (a.last_close - b.last_close)
        case "distance":
          return dir * (Math.abs(a.distance_from_ema48_pct) - Math.abs(b.distance_from_ema48_pct))
        case "atr_covered":
          return dir * (a.atr_covered_pct - b.atr_covered_pct)
        case "ema13":
          return dir * (a.ema13 - b.ema13)
        case "trend": {
          const order: Record<Trend, number> = { bullish: 0, neutral: 1, bearish: 2 }
          return dir * (order[a.trend] - order[b.trend])
        }
        default:
          return 0
      }
    })
    return arr
  }, [hits, sortKey, sortAsc])

  if (hits.length === 0) return null

  const SortHeader = ({ label, k }: { label: string; k: SortKey }) => (
    <TableHead className="cursor-pointer select-none" onClick={() => toggleSort(k)}>
      <div className="flex items-center gap-1 text-xs">
        {label}
        <ArrowUpDown className="size-3 text-muted-foreground" />
      </div>
    </TableHead>
  )

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortHeader label="Ticker" k="ticker" />
            <SortHeader label="Price" k="last_close" />
            <TableHead className="text-xs">Signal</TableHead>
            <SortHeader label="EMA13" k="ema13" />
            <TableHead className="text-xs">EMA21</TableHead>
            <TableHead className="text-xs">EMA34</TableHead>
            <TableHead className="text-xs">EMA48</TableHead>
            <SortHeader label="Dist %" k="distance" />
            <SortHeader label="ATR %" k="atr_covered" />
            <TableHead className="text-xs">ATR</TableHead>
            <SortHeader label="Trend" k="trend" />
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((hit) => {
            const sig = signalBadge(hit.signal as "vomy" | "ivomy")
            const atr = atrStatusBadge(hit.atr_status)
            const distColor = hit.distance_from_ema48_pct >= 0 ? "text-emerald-400" : "text-red-400"

            return (
              <TableRow key={hit.ticker}>
                <TableCell className="font-mono text-xs font-medium">{hit.ticker}</TableCell>
                <TableCell className="text-xs">${hit.last_close.toFixed(2)}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${sig.color}`}>
                    {sig.text}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{hit.ema13.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema21.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema34.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema48.toFixed(2)}</TableCell>
                <TableCell className={`text-xs font-medium ${distColor}`}>
                  {hit.distance_from_ema48_pct > 0 ? "+" : ""}
                  {hit.distance_from_ema48_pct.toFixed(1)}%
                </TableCell>
                <TableCell className="text-xs">{hit.atr_covered_pct.toFixed(0)}%</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${atr.color}`}>
                    {atr.text}
                  </Badge>
                </TableCell>
                <TableCell className={`text-xs font-medium ${trendColor(hit.trend)}`}>
                  {trendLabel(hit.trend)}
                </TableCell>
                <TableCell>
                  <SaveButton hit={hit} />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
```

**Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/screener/vomy-results-table.tsx
git commit -m "feat: add VOMY results table component"
```

---

### Task 7: Wire VOMY tab into screener page

**Files:**
- Modify: `frontend/src/app/screener/page.tsx`

**Step 1: Add VOMY imports and hook**

Add to imports:
```typescript
import { VomyControls } from "@/components/screener/vomy-controls"
import { VomyResultsTable } from "@/components/screener/vomy-results-table"
import { useVomyScan } from "@/hooks/use-vomy-scan"
```

Add hook call inside `ScreenerPage()`:
```typescript
const vomy = useVomyScan()
```

**Step 2: Replace the "Squeeze" tab trigger with "VOMY" tab**

Replace the disabled Squeeze TabsTrigger with an enabled VOMY one:
```typescript
<TabsTrigger value="vomy">VOMY</TabsTrigger>
```

**Step 3: Replace the Squeeze TabsContent with VOMY content**

Replace the Squeeze TabsContent:
```typescript
<TabsContent value="vomy" className="space-y-4">
  <VomyControls
    scanning={vomy.scanning}
    response={vomy.response}
    error={vomy.error}
    watchlists={watchlists}
    initialUniverses={vomy.config.universes}
    initialMinPrice={vomy.config.min_price}
    initialTimeframe={vomy.config.timeframe}
    initialSignalType={vomy.config.signal_type}
    initialIncludePremarket={vomy.config.include_premarket}
    onScan={vomy.runScan}
    onCancel={vomy.cancelScan}
  />
  <VomyResultsTable hits={vomy.hits} />
</TabsContent>
```

**Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds clean

**Step 5: Run all backend tests**

Run: `/Users/krishnaeedula/claude/trend-trading-mcp/.venv/bin/python -m pytest tests/api/test_vomy_scan.py tests/api/test_golden_gate_scan.py tests/api/test_momentum_scan.py -v --noconftest`
Expected: All tests PASS (9 vomy + 14 golden gate + 11 momentum = 34 tests)

**Step 6: Run lint on all modified files**

Run: `uv tool run ruff check api/endpoints/screener.py tests/api/test_vomy_scan.py && uv tool run ruff format --check api/endpoints/screener.py tests/api/test_vomy_scan.py`
Expected: All checks passed

**Step 7: Commit**

```bash
git add frontend/src/app/screener/page.tsx
git commit -m "feat: wire VOMY tab into screener page"
```

**Step 8: Push all commits**

```bash
git push
```
