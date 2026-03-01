# Golden Gate Scanner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Golden Gate scanner screener tab that identifies stocks in the ATR "golden gate zone" (38.2% Fibonacci), matching the TOS Saty ATR Levels Signals scanner.

**Architecture:** Per-ticker ATR calculation using existing `atr_levels()` indicator with `asyncio.Semaphore(10)` concurrency. Reuses `_fetch_atr_source()`, `_fetch_premarket()`, and `_load_universe()` from existing endpoints. Frontend mirrors the momentum scanner tab pattern.

**Tech Stack:** Python/FastAPI backend, yfinance, pandas, Next.js 16 frontend, React 19, Tailwind 4, shadcn/ui

---

## Task 1: Add TypeScript types for Golden Gate scanner

**Files:**
- Modify: `frontend/src/lib/types.ts` (append after MomentumScanResponse block, line ~367)

**Step 1: Add types at the end of `types.ts`**

After the `MomentumScanResponse` interface (line ~367), add:

```typescript
// ---------------------------------------------------------------------------
// Golden Gate Scanner
// ---------------------------------------------------------------------------

export type GoldenGateSignalType = "golden_gate" | "call_trigger" | "put_trigger"

export interface GoldenGateHit {
  ticker: string
  last_close: number
  signal: GoldenGateSignalType
  direction: "bullish" | "bearish"
  pdc: number
  atr: number
  gate_level: number
  midrange_level: number
  distance_pct: number
  atr_status: AtrStatus
  atr_covered_pct: number
  trend: Trend
  trading_mode: TradingMode
  premarket_high: number | null
  premarket_low: number | null
}

export interface GoldenGateScanRequest {
  universes: string[]
  trading_mode: TradingMode
  signal_type: GoldenGateSignalType
  min_price: number
  custom_tickers?: string[]
  include_premarket: boolean
}

export interface GoldenGateScanResponse {
  hits: GoldenGateHit[]
  total_scanned: number
  total_hits: number
  total_errors: number
  skipped_low_price: number
  scan_duration_seconds: number
  signal_type: GoldenGateSignalType
  trading_mode: TradingMode
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add TypeScript types for Golden Gate scanner"
```

---

## Task 2: Add Golden Gate scan backend endpoint

**Files:**
- Modify: `api/endpoints/screener.py` (add after momentum scan section, line ~430)

**Step 1: Add `_fetch_premarket` to imports**

At the top of `api/endpoints/screener.py`, add `_fetch_premarket` to the satyland import:

```python
from api.endpoints.satyland import (
    TIMEFRAME_TO_MODE,
    _fetch_atr_source,
    _fetch_daily,
    _fetch_intraday,
    _fetch_mtf_ribbons,
    _fetch_premarket,    # NEW
)
```

Also add `Literal` to typing import:

```python
from typing import Any, Literal
```

**Step 2: Add Pydantic models after the momentum scan section**

After `momentum_scan` endpoint (around line ~430), add a new section:

```python
# ---------------------------------------------------------------------------
# Golden Gate Scanner — replicates TOS "Saty ATR Levels Signals" scanner
# ---------------------------------------------------------------------------

# TOS formula:
#   golden_gate_up <= high AND midrange_up > high AND pivot <= close
# Matches stocks that have entered the golden gate zone (38.2% Fibonacci)
# from below, haven't reached midrange (61.8%), and are above PDC.


class GoldenGateScanRequest(BaseModel):
    """Request for the Golden Gate ATR scanner."""

    universes: list[str] = Field(
        default=["sp500", "nasdaq100"],
        description="Universe keys: sp500, nasdaq100, russell2000, or all",
    )
    trading_mode: Literal["day", "multiday", "swing", "position"] = Field(
        default="day", description="ATR trading mode"
    )
    signal_type: Literal["golden_gate", "call_trigger", "put_trigger"] = Field(
        default="golden_gate", description="Signal type to scan for"
    )
    min_price: float = Field(default=4.0, ge=0, description="Minimum price filter")
    custom_tickers: list[str] | None = Field(
        default=None, max_length=500, description="Extra tickers to include",
    )
    include_premarket: bool = Field(
        default=True, description="Use premarket high/low for Day mode",
    )


class GoldenGateHit(BaseModel):
    """A stock that triggered a golden gate / trigger signal."""

    ticker: str
    last_close: float
    signal: str
    direction: str
    pdc: float
    atr: float
    gate_level: float
    midrange_level: float
    distance_pct: float
    atr_status: str
    atr_covered_pct: float
    trend: str
    trading_mode: str
    premarket_high: float | None = None
    premarket_low: float | None = None


class GoldenGateScanResponse(BaseModel):
    """Response for the Golden Gate scanner."""

    hits: list[GoldenGateHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    signal_type: str
    trading_mode: str
```

**Step 3: Add the signal checking helper**

```python
def _check_golden_gate_signal(
    atr_result: dict,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    signal_type: str,
) -> list[dict]:
    """Check if a ticker matches the golden gate / trigger signal.

    Returns list of signal dicts (can have both bull and bear for golden_gate).
    Each dict has keys: signal, direction, gate_level, midrange_level.
    """
    levels = atr_result["levels"]
    pdc = atr_result["pdc"]
    signals: list[dict] = []

    if signal_type == "golden_gate":
        # Bull: golden_gate_bull <= bar_high AND midrange_bull > bar_high AND pdc <= bar_close
        gg_bull = levels["golden_gate_bull"]["price"]
        mr_bull = levels["mid_range_bull"]["price"]
        if gg_bull <= bar_high and mr_bull > bar_high and pdc <= bar_close:
            signals.append({
                "signal": "golden_gate",
                "direction": "bullish",
                "gate_level": gg_bull,
                "midrange_level": mr_bull,
            })

        # Bear: golden_gate_bear >= bar_low AND midrange_bear < bar_low AND pdc >= bar_close
        gg_bear = levels["golden_gate_bear"]["price"]
        mr_bear = levels["mid_range_bear"]["price"]
        if gg_bear >= bar_low and mr_bear < bar_low and pdc >= bar_close:
            signals.append({
                "signal": "golden_gate",
                "direction": "bearish",
                "gate_level": gg_bear,
                "midrange_level": mr_bear,
            })

    elif signal_type == "call_trigger":
        # Bull only: call_trigger <= bar_high AND golden_gate_bull > bar_high AND pdc <= bar_close
        ct = levels["trigger_bull"]["price"]
        gg_bull = levels["golden_gate_bull"]["price"]
        if ct <= bar_high and gg_bull > bar_high and pdc <= bar_close:
            signals.append({
                "signal": "call_trigger",
                "direction": "bullish",
                "gate_level": ct,
                "midrange_level": gg_bull,
            })

    elif signal_type == "put_trigger":
        # Bear only: put_trigger >= bar_low AND golden_gate_bear < bar_low AND pdc >= bar_close
        pt = levels["trigger_bear"]["price"]
        gg_bear = levels["golden_gate_bear"]["price"]
        if pt >= bar_low and gg_bear < bar_low and pdc >= bar_close:
            signals.append({
                "signal": "put_trigger",
                "direction": "bearish",
                "gate_level": pt,
                "midrange_level": gg_bear,
            })

    return signals
```

**Step 4: Add the endpoint**

```python
@router.post("/golden-gate-scan")
async def golden_gate_scan(request: GoldenGateScanRequest) -> GoldenGateScanResponse:
    """Scan universe for Golden Gate / trigger signals using ATR Levels.

    For each ticker, computes ATR Levels at the requested trading mode,
    then checks whether the bar's high/low/close crosses the signal level.
    Day mode can optionally use premarket data for the bar comparison.
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
        "Golden Gate scan: %d tickers, mode=%s, signal=%s",
        len(tickers), request.trading_mode, request.signal_type,
    )

    ucc = resolve_use_current_close()
    sem = asyncio.Semaphore(10)
    hits: list[GoldenGateHit] = []
    errors = 0
    skipped_low_price = 0

    async def _process_ticker(ticker: str) -> GoldenGateHit | None:
        nonlocal errors, skipped_low_price
        async with sem:
            try:
                # Fetch ATR source data
                atr_source_df = await asyncio.to_thread(
                    _fetch_atr_source, ticker, request.trading_mode,
                )

                # Compute ATR Levels
                atr_result = atr_levels(
                    atr_source_df,
                    trading_mode=request.trading_mode,
                    use_current_close=ucc,
                )

                last_close = atr_result["current_price"]

                # Price filter
                if last_close < request.min_price:
                    skipped_low_price += 1
                    return None

                # Determine bar high/low/close for signal comparison
                bar_high = float(atr_source_df["high"].iloc[-1])
                bar_low = float(atr_source_df["low"].iloc[-1])
                bar_close = last_close
                pm_high: float | None = None
                pm_low: float | None = None

                # For day mode, optionally use premarket data
                if request.trading_mode == "day" and request.include_premarket:
                    pm_df = await asyncio.to_thread(_fetch_premarket, ticker)
                    if pm_df is not None and not pm_df.empty:
                        pm_high = float(pm_df["high"].max())
                        pm_low = float(pm_df["low"].min())
                        pm_close = float(pm_df["close"].iloc[-1])
                        # Use whichever high/low is more extreme
                        bar_high = max(bar_high, pm_high)
                        bar_low = min(bar_low, pm_low)
                        bar_close = pm_close

                # Check signal
                matched = _check_golden_gate_signal(
                    atr_result, bar_high, bar_low, bar_close, request.signal_type,
                )

                if not matched:
                    return None

                # Use first signal match (bull preferred)
                sig = matched[0]
                gate = sig["gate_level"]
                distance = ((bar_close - gate) / gate) * 100 if gate > 0 else 0.0

                return GoldenGateHit(
                    ticker=ticker.upper(),
                    last_close=round(bar_close, 2),
                    signal=sig["signal"],
                    direction=sig["direction"],
                    pdc=atr_result["pdc"],
                    atr=atr_result["atr"],
                    gate_level=round(gate, 4),
                    midrange_level=round(sig["midrange_level"], 4),
                    distance_pct=round(distance, 2),
                    atr_status=atr_result["atr_status"],
                    atr_covered_pct=atr_result["atr_covered_pct"],
                    trend=atr_result["trend"],
                    trading_mode=request.trading_mode,
                    premarket_high=round(pm_high, 4) if pm_high else None,
                    premarket_low=round(pm_low, 4) if pm_low else None,
                )

            except Exception as exc:
                logger.debug("Golden Gate scan error for %s: %s", ticker, exc)
                errors += 1
                return None

    results = await asyncio.gather(*(_process_ticker(t) for t in tickers))
    hits = [r for r in results if r is not None]

    # Sort by distance_pct ascending (closest to signal level first)
    hits.sort(key=lambda h: abs(h.distance_pct))

    elapsed = round(time.monotonic() - t0, 2)

    return GoldenGateScanResponse(
        hits=hits,
        total_scanned=len(tickers),
        total_hits=len(hits),
        total_errors=errors,
        skipped_low_price=skipped_low_price,
        scan_duration_seconds=elapsed,
        signal_type=request.signal_type,
        trading_mode=request.trading_mode,
    )
```

**Step 5: Commit**

```bash
git add api/endpoints/screener.py
git commit -m "feat: add Golden Gate scanner endpoint POST /api/screener/golden-gate-scan"
```

---

## Task 3: Add backend unit tests

**Files:**
- Create: `tests/api/test_golden_gate_scan.py`

**Step 1: Create test file**

```python
"""Tests for the Golden Gate scanner endpoint."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _make_daily_df(
    base_price: float = 100.0,
    days: int = 30,
    growth: float = 0.0,
) -> pd.DataFrame:
    """Build synthetic daily OHLCV DataFrame.

    Args:
        base_price: Starting close price.
        days: Number of bars.
        growth: Total % growth over the period (e.g. 0.15 = 15%).
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.linspace(base_price, base_price * (1 + growth), days)
    return pd.DataFrame(
        {
            "open": prices * 0.998,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )


def _make_premarket_df(
    high: float = 105.0,
    low: float = 99.0,
    close: float = 103.0,
) -> pd.DataFrame:
    """Build synthetic 1-min premarket DataFrame."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    today = datetime.now(ET).strftime("%Y-%m-%d")
    idx = pd.date_range(f"{today} 04:00", f"{today} 09:29", freq="1min", tz=ET)
    n = len(idx)
    return pd.DataFrame(
        {
            "open": np.linspace(low, close, n),
            "high": np.full(n, high),
            "low": np.full(n, low),
            "close": np.linspace(low, close, n),
            "volume": [10_000] * n,
        },
        index=idx,
    )


UNIVERSE = {"sp500": ["AAPL", "MSFT"], "nasdaq100": ["AAPL", "TSLA"],
            "all_unique": ["AAPL", "MSFT", "TSLA"],
            "counts": {"sp500": 2, "nasdaq100": 2, "all_unique": 3}}


@pytest.fixture(autouse=True)
def mock_universe(tmp_path: Path):
    """Write a small test universe and patch UNIVERSE_PATH."""
    uni_file = tmp_path / "universe.json"
    uni_file.write_text(json.dumps(UNIVERSE))
    with patch("api.endpoints.screener.UNIVERSE_PATH", uni_file):
        yield


@pytest.fixture()
def mock_atr_source():
    """Patch _fetch_atr_source to return synthetic daily data."""
    df = _make_daily_df(base_price=100.0, days=30, growth=0.05)
    with patch("api.endpoints.screener._fetch_atr_source", return_value=df) as m:
        yield m


@pytest.fixture()
def mock_premarket():
    """Patch _fetch_premarket to return synthetic premarket data."""
    df = _make_premarket_df(high=105.0, low=99.0, close=103.0)
    with patch("api.endpoints.screener._fetch_premarket", return_value=df) as m:
        yield m


class TestGoldenGateScan:
    """Tests for POST /api/screener/golden-gate-scan."""

    def test_returns_200(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
            "trading_mode": "day",
            "signal_type": "golden_gate",
        })
        assert res.status_code == 200
        data = res.json()
        assert "hits" in data
        assert "total_scanned" in data
        assert "scan_duration_seconds" in data

    def test_response_shape(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
        })
        data = res.json()
        assert isinstance(data["hits"], list)
        assert isinstance(data["total_scanned"], int)
        assert isinstance(data["total_hits"], int)
        assert isinstance(data["total_errors"], int)
        assert isinstance(data["skipped_low_price"], int)
        assert isinstance(data["scan_duration_seconds"], float)
        assert data["signal_type"] == "golden_gate"
        assert data["trading_mode"] == "day"

    def test_hit_has_expected_fields(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
        })
        data = res.json()
        if data["hits"]:
            hit = data["hits"][0]
            assert "ticker" in hit
            assert "last_close" in hit
            assert "signal" in hit
            assert "direction" in hit
            assert "pdc" in hit
            assert "atr" in hit
            assert "gate_level" in hit
            assert "midrange_level" in hit
            assert "distance_pct" in hit
            assert "atr_status" in hit
            assert "trend" in hit
            assert "trading_mode" in hit

    def test_price_filter(self, mock_premarket):
        """Stocks below min_price should be excluded."""
        cheap_df = _make_daily_df(base_price=2.50, days=30)
        with patch("api.endpoints.screener._fetch_atr_source", return_value=cheap_df):
            res = client.post("/api/screener/golden-gate-scan", json={
                "universes": ["sp500"],
                "min_price": 4.0,
            })
            data = res.json()
            assert data["skipped_low_price"] > 0
            assert data["total_hits"] == 0

    def test_custom_tickers_merged(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
            "custom_tickers": ["GOOG", "AMZN"],
        })
        data = res.json()
        # Should scan sp500 (2) + custom (2) = 4 unique tickers
        assert data["total_scanned"] == 4

    def test_signal_type_call_trigger(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
            "signal_type": "call_trigger",
        })
        data = res.json()
        assert data["signal_type"] == "call_trigger"
        for hit in data["hits"]:
            assert hit["signal"] == "call_trigger"
            assert hit["direction"] == "bullish"

    def test_signal_type_put_trigger(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": ["sp500"],
            "signal_type": "put_trigger",
        })
        data = res.json()
        assert data["signal_type"] == "put_trigger"
        for hit in data["hits"]:
            assert hit["signal"] == "put_trigger"
            assert hit["direction"] == "bearish"

    def test_trading_mode_swing(self, mock_premarket):
        df = _make_daily_df(base_price=100.0, days=30, growth=0.05)
        with patch("api.endpoints.screener._fetch_atr_source", return_value=df):
            res = client.post("/api/screener/golden-gate-scan", json={
                "universes": ["sp500"],
                "trading_mode": "swing",
            })
            data = res.json()
            assert data["trading_mode"] == "swing"

    def test_premarket_disabled(self, mock_atr_source):
        """When include_premarket=False, _fetch_premarket should not be called."""
        with patch("api.endpoints.screener._fetch_premarket") as mock_pm:
            res = client.post("/api/screener/golden-gate-scan", json={
                "universes": ["sp500"],
                "include_premarket": False,
            })
            mock_pm.assert_not_called()
            assert res.status_code == 200

    def test_empty_universe_returns_zero(self, mock_atr_source, mock_premarket):
        res = client.post("/api/screener/golden-gate-scan", json={
            "universes": [],
            "custom_tickers": [],
        })
        data = res.json()
        assert data["total_scanned"] == 0
        assert data["total_hits"] == 0

    def test_fetch_error_counted(self, mock_premarket):
        """When _fetch_atr_source raises, ticker is counted as error."""
        with patch("api.endpoints.screener._fetch_atr_source",
                   side_effect=ValueError("No data")):
            res = client.post("/api/screener/golden-gate-scan", json={
                "universes": ["sp500"],
            })
            data = res.json()
            assert data["total_errors"] == 2  # AAPL + MSFT
            assert data["total_hits"] == 0
```

**Step 2: Run tests**

```bash
venv/bin/pytest tests/api/test_golden_gate_scan.py -v
```

**Step 3: Commit**

```bash
git add tests/api/test_golden_gate_scan.py
git commit -m "test: add Golden Gate scanner unit tests"
```

---

## Task 4: Create frontend API route proxy

**Files:**
- Create: `frontend/src/app/api/screener/golden-gate-scan/route.ts`

**Step 1: Create the route file**

Mirror the momentum-scan route exactly:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';
import { RailwayError } from '@/lib/errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await railwayFetch('/api/screener/golden-gate-scan', body);
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
    console.error('Screener golden-gate-scan error:', error);
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'NETWORK_ERROR' },
      { status: 502 }
    );
  }
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/api/screener/golden-gate-scan/route.ts
git commit -m "feat: add Golden Gate scan API route proxy"
```

---

## Task 5: Create `useGoldenGateScan` hook

**Files:**
- Create: `frontend/src/hooks/use-golden-gate-scan.ts`

**Step 1: Create the hook**

Mirror `use-momentum-scan.ts` pattern with golden-gate-specific config:

```typescript
"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type {
  GoldenGateScanRequest,
  GoldenGateScanResponse,
  GoldenGateHit,
  GoldenGateSignalType,
  TradingMode,
} from "@/lib/types"

export interface GoldenGateScanConfig {
  universes: string[]
  trading_mode: TradingMode
  signal_type: GoldenGateSignalType
  min_price: number
  include_premarket: boolean
  custom_tickers?: string[]
}

interface UseGoldenGateScanReturn {
  hits: GoldenGateHit[]
  scanning: boolean
  response: GoldenGateScanResponse | null
  config: GoldenGateScanConfig
  error: string | null
  runScan: (config: GoldenGateScanConfig) => void
  cancelScan: () => void
}

const STORAGE_KEY = "golden_gate_scan_results"
const CONFIG_KEY = "golden_gate_scan_config"

const DEFAULT_CONFIG: GoldenGateScanConfig = {
  universes: ["sp500", "nasdaq100"],
  trading_mode: "day",
  signal_type: "golden_gate",
  min_price: 4.0,
  include_premarket: true,
}

// --- Session storage helpers ---

function saveResponse(data: GoldenGateScanResponse | null) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResponse(): GoldenGateScanResponse | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as GoldenGateScanResponse
  } catch {
    return null
  }
}

function saveConfig(config: GoldenGateScanConfig) {
  try {
    const { custom_tickers: _, ...persistable } = config
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(persistable))
  } catch {
    // ignore
  }
}

function loadConfig(): GoldenGateScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return DEFAULT_CONFIG
    return JSON.parse(raw) as GoldenGateScanConfig
  } catch {
    return DEFAULT_CONFIG
  }
}

// --- Hook ---

export function useGoldenGateScan(): UseGoldenGateScanReturn {
  const [hits, setHits] = useState<GoldenGateHit[]>([])
  const [scanning, setScanning] = useState(false)
  const [response, setResponse] = useState<GoldenGateScanResponse | null>(null)
  const [config, setConfig] = useState<GoldenGateScanConfig>(DEFAULT_CONFIG)
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
    async (newConfig: GoldenGateScanConfig) => {
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
        const body: GoldenGateScanRequest = {
          universes: newConfig.universes,
          trading_mode: newConfig.trading_mode,
          signal_type: newConfig.signal_type,
          min_price: newConfig.min_price,
          include_premarket: newConfig.include_premarket,
          ...(newConfig.custom_tickers?.length && { custom_tickers: newConfig.custom_tickers }),
        }

        const res = await fetch("/api/screener/golden-gate-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Unknown error" }))
          const msg = err.error ?? `HTTP ${res.status}`
          console.error("Golden Gate scan failed:", msg)
          setError(msg)
          return
        }

        const data: GoldenGateScanResponse = await res.json()
        setHits(data.hits)
        setResponse(data)
        saveResponse(data)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        const msg = err instanceof Error ? err.message : "Network error"
        console.error("Golden Gate scan failed:", msg)
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

**Step 2: Commit**

```bash
git add frontend/src/hooks/use-golden-gate-scan.ts
git commit -m "feat: add useGoldenGateScan hook with sessionStorage persistence"
```

---

## Task 6: Create Golden Gate controls and results table

**Files:**
- Create: `frontend/src/components/screener/golden-gate-controls.tsx`
- Create: `frontend/src/components/screener/golden-gate-results-table.tsx`

**Step 1: Create golden-gate-controls.tsx**

```typescript
"use client"

import { useState } from "react"
import { Play, Square, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type {
  GoldenGateScanResponse,
  GoldenGateSignalType,
  TradingMode,
  Watchlist,
} from "@/lib/types"

interface GoldenGateControlsProps {
  scanning: boolean
  response: GoldenGateScanResponse | null
  error: string | null
  watchlists: Watchlist[]
  initialUniverses: string[]
  initialMinPrice: number
  initialTradingMode: TradingMode
  initialSignalType: GoldenGateSignalType
  initialIncludePremarket: boolean
  onScan: (config: {
    universes: string[]
    trading_mode: TradingMode
    signal_type: GoldenGateSignalType
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

const TRADING_MODES: { key: TradingMode; label: string }[] = [
  { key: "day", label: "Day" },
  { key: "multiday", label: "Multiday" },
  { key: "swing", label: "Swing" },
  { key: "position", label: "Position" },
]

const SIGNAL_TYPES: { key: GoldenGateSignalType; label: string }[] = [
  { key: "golden_gate", label: "Golden Gate" },
  { key: "call_trigger", label: "Call Trigger" },
  { key: "put_trigger", label: "Put Trigger" },
]

export function GoldenGateControls({
  scanning,
  response,
  error,
  watchlists,
  initialUniverses,
  initialMinPrice,
  initialTradingMode,
  initialSignalType,
  initialIncludePremarket,
  onScan,
  onCancel,
}: GoldenGateControlsProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initialUniverses))
  const [selectedWatchlists, setSelectedWatchlists] = useState<Set<string>>(new Set())
  const [minPrice, setMinPrice] = useState(initialMinPrice)
  const [tradingMode, setTradingMode] = useState<TradingMode>(initialTradingMode)
  const [signalType, setSignalType] = useState<GoldenGateSignalType>(initialSignalType)
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
      trading_mode: tradingMode,
      signal_type: signalType,
      min_price: minPrice,
      include_premarket: includePremarket,
      ...(unique.length > 0 && { custom_tickers: unique }),
    })
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* Trading Mode */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Trading Mode</Label>
          <div className="flex gap-1.5">
            {TRADING_MODES.map((m) => (
              <Button
                key={m.key}
                size="sm"
                variant={tradingMode === m.key ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => setTradingMode(m.key)}
                disabled={scanning}
              >
                {m.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Signal Type */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Signal</Label>
          <div className="flex gap-1.5">
            {SIGNAL_TYPES.map((s) => (
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

        {/* Pre-market toggle (only for Day mode) */}
        {tradingMode === "day" && (
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
          Scanning{" "}
          {[
            ...UNIVERSE_OPTIONS.filter((u) => selected.has(u.key)).map((u) => u.label),
            ...watchlists.filter((w) => selectedWatchlists.has(w.id)).map((w) => w.name),
          ].join(" + ")}{" "}
          for {SIGNAL_TYPES.find((s) => s.key === signalType)?.label} ({TRADING_MODES.find((m) => m.key === tradingMode)?.label} levels)...
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
          <span>{response.total_scanned} scanned</span>
          <span>{response.skipped_low_price} below ${minPrice}</span>
          <span>{response.total_errors} errors</span>
          <span>{response.scan_duration_seconds}s</span>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Create golden-gate-results-table.tsx**

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
import type { GoldenGateHit } from "@/lib/types"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

type SortKey = "ticker" | "last_close" | "distance" | "atr_covered" | "gate" | "trend"

function signalBadge(signal: string, direction: string) {
  const colors: Record<string, string> = {
    golden_gate_bullish: "bg-amber-600/20 text-amber-400 border-amber-600/30",
    golden_gate_bearish: "bg-purple-600/20 text-purple-400 border-purple-600/30",
    call_trigger_bullish: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
    put_trigger_bearish: "bg-red-600/20 text-red-400 border-red-600/30",
  }
  const labels: Record<string, string> = {
    golden_gate: "Golden Gate",
    call_trigger: "Call Trigger",
    put_trigger: "Put Trigger",
  }
  const key = `${signal}_${direction}`
  return {
    text: labels[signal] ?? signal,
    color: colors[key] ?? "bg-zinc-600/20 text-zinc-400 border-zinc-600/30",
  }
}

function directionBadge(direction: string) {
  if (direction === "bullish")
    return { text: "Bull", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
  return { text: "Bear", color: "bg-red-600/20 text-red-400 border-red-600/30" }
}

function atrStatusBadge(status: string) {
  const map: Record<string, { text: string; color: string }> = {
    green: { text: "Room", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" },
    orange: { text: "Warning", color: "bg-amber-600/20 text-amber-400 border-amber-600/30" },
    red: { text: "Extended", color: "bg-red-600/20 text-red-400 border-red-600/30" },
  }
  return map[status] ?? { text: status, color: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30" }
}

function trendBadge(trend: string) {
  const map: Record<string, { text: string; color: string }> = {
    bullish: { text: "Bull", color: "text-emerald-400" },
    bearish: { text: "Bear", color: "text-red-400" },
    neutral: { text: "Neutral", color: "text-zinc-400" },
  }
  return map[trend] ?? { text: trend, color: "text-zinc-400" }
}

// --- Save as Idea button ---

function SaveButton({ hit }: { hit: GoldenGateHit }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: hit.ticker,
        direction: hit.direction as "bullish" | "bearish",
        timeframe: "1d",
        status: "watching",
        current_price: hit.last_close,
        call_trigger: hit.signal === "call_trigger" ? hit.gate_level : undefined,
        put_trigger: hit.signal === "put_trigger" ? hit.gate_level : undefined,
        tags: [
          "source:screener",
          `screener:golden_gate`,
          `signal:${hit.signal}`,
          `atr:${hit.atr_status}`,
        ],
        source: "screener",
        notes: `${hit.signal === "golden_gate" ? "Golden Gate" : hit.signal === "call_trigger" ? "Call Trigger" : "Put Trigger"} ${hit.direction} — Gate: $${hit.gate_level.toFixed(2)}, Midrange: $${hit.midrange_level.toFixed(2)}, ATR: ${hit.atr_status}`,
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

export function GoldenGateResultsTable({ hits }: { hits: GoldenGateHit[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("distance")
  const [sortAsc, setSortAsc] = useState(true)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((p) => !p)
    else {
      setSortKey(key)
      setSortAsc(key === "ticker") // alphabetical ascending, numbers ascending
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
          return dir * (Math.abs(a.distance_pct) - Math.abs(b.distance_pct))
        case "atr_covered":
          return dir * (a.atr_covered_pct - b.atr_covered_pct)
        case "gate":
          return dir * (a.gate_level - b.gate_level)
        case "trend":
          return dir * a.trend.localeCompare(b.trend)
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
            <SortHeader label="Gate" k="gate" />
            <SortHeader label="Dist %" k="distance" />
            <SortHeader label="ATR %" k="atr_covered" />
            <TableHead className="text-xs">ATR</TableHead>
            <SortHeader label="Trend" k="trend" />
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((hit) => {
            const sig = signalBadge(hit.signal, hit.direction)
            const dir = directionBadge(hit.direction)
            const atr = atrStatusBadge(hit.atr_status)
            const trd = trendBadge(hit.trend)
            return (
              <TableRow key={`${hit.ticker}-${hit.direction}`}>
                <TableCell className="font-mono text-xs font-medium">{hit.ticker}</TableCell>
                <TableCell className="text-xs">${hit.last_close.toFixed(2)}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Badge variant="outline" className={`text-[10px] ${sig.color}`}>
                      {sig.text}
                    </Badge>
                    <Badge variant="outline" className={`text-[10px] ${dir.color}`}>
                      {dir.text}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell className="text-xs font-mono">${hit.gate_level.toFixed(2)}</TableCell>
                <TableCell className="text-xs">
                  <span className={hit.distance_pct >= 0 ? "text-emerald-400" : "text-red-400"}>
                    {hit.distance_pct > 0 ? "+" : ""}
                    {hit.distance_pct.toFixed(1)}%
                  </span>
                </TableCell>
                <TableCell className="text-xs">{hit.atr_covered_pct.toFixed(0)}%</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${atr.color}`}>
                    {atr.text}
                  </Badge>
                </TableCell>
                <TableCell className={`text-xs ${trd.color}`}>{trd.text}</TableCell>
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

**Step 3: Commit**

```bash
git add frontend/src/components/screener/golden-gate-controls.tsx frontend/src/components/screener/golden-gate-results-table.tsx
git commit -m "feat: add Golden Gate controls and results table components"
```

---

## Task 7: Wire Golden Gate tab into screener page

**Files:**
- Modify: `frontend/src/app/screener/page.tsx`

**Step 1: Update imports and add Golden Gate tab content**

Replace the page with:

```typescript
"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { MomentumControls } from "@/components/screener/momentum-controls"
import { MomentumResultsTable } from "@/components/screener/momentum-results-table"
import { GoldenGateControls } from "@/components/screener/golden-gate-controls"
import { GoldenGateResultsTable } from "@/components/screener/golden-gate-results-table"
import { useMomentumScan } from "@/hooks/use-momentum-scan"
import { useGoldenGateScan } from "@/hooks/use-golden-gate-scan"
import { useWatchlists } from "@/hooks/use-watchlists"

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-8 text-center">
      <p className="text-sm text-muted-foreground">{name} screener coming soon</p>
    </div>
  )
}

export default function ScreenerPage() {
  const momentum = useMomentumScan()
  const goldenGate = useGoldenGateScan()
  const { watchlists } = useWatchlists()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Screener</h1>
        <p className="text-xs text-muted-foreground">
          Scan the market for momentum, squeeze, and setup opportunities
        </p>
      </div>

      <Tabs defaultValue="momentum" className="space-y-4">
        <TabsList>
          <TabsTrigger value="momentum">Momentum</TabsTrigger>
          <TabsTrigger value="golden-gate">Golden Gate</TabsTrigger>
          <TabsTrigger value="squeeze" disabled>
            Squeeze <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
          <TabsTrigger value="mean-reversion" disabled>
            Mean Reversion <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="momentum" className="space-y-4">
          <MomentumControls
            scanning={momentum.scanning}
            response={momentum.response}
            error={momentum.error}
            watchlists={watchlists}
            initialUniverses={momentum.config.universes}
            initialMinPrice={momentum.config.min_price}
            onScan={momentum.runScan}
            onCancel={momentum.cancelScan}
          />
          <MomentumResultsTable hits={momentum.hits} />
        </TabsContent>

        <TabsContent value="golden-gate" className="space-y-4">
          <GoldenGateControls
            scanning={goldenGate.scanning}
            response={goldenGate.response}
            error={goldenGate.error}
            watchlists={watchlists}
            initialUniverses={goldenGate.config.universes}
            initialMinPrice={goldenGate.config.min_price}
            initialTradingMode={goldenGate.config.trading_mode}
            initialSignalType={goldenGate.config.signal_type}
            initialIncludePremarket={goldenGate.config.include_premarket}
            onScan={goldenGate.runScan}
            onCancel={goldenGate.cancelScan}
          />
          <GoldenGateResultsTable hits={goldenGate.hits} />
        </TabsContent>

        <TabsContent value="squeeze">
          <ComingSoon name="Squeeze" />
        </TabsContent>

        <TabsContent value="mean-reversion">
          <ComingSoon name="Mean Reversion" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/screener/page.tsx
git commit -m "feat: wire Golden Gate tab into screener page"
```

---

## Task 8: Build verification and full test suite

**Step 1: Run backend tests**

```bash
venv/bin/pytest tests/api/test_golden_gate_scan.py -v
venv/bin/pytest tests/ -v
```

**Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

**Step 3: Run linting**

```bash
make check
```

**Step 4: Fix any issues and commit**

```bash
git add -A
git commit -m "fix: address build/lint issues from Golden Gate scanner"
```
