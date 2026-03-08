# Market Monitor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a `/market-monitor` page with a Stockbee-style breadth heat map (10 scans × 30 days), click-to-drill-down side panel, and a full Theme Tracker for sector rotation.

**Architecture:** Railway backend computes daily breadth snapshots (yfinance bulk download for ~2,500 $1B+ stocks, Schwab for universe enrichment). Snapshots stored in Supabase. Frontend renders heat map grid with slide-out drill-down panel. Daily cron at 1:05 PM PST appends each day's snapshot. One-time backfill script populates historical data.

**Tech Stack:** FastAPI, yfinance (bulk download), Schwab API (universe/sector), Supabase (storage), Next.js, shadcn/ui Sheet + Table, lightweight-charts (mini charts), Tailwind 4

---

## Task 1: Supabase Tables — `monitor_universe` + `breadth_snapshots`

**Files:**
- Create: `alembic/versions/015_add_market_monitor_tables.py`

**Step 1: Write migration**

```python
"""Add market monitor tables

Revision ID: 015_add_market_monitor_tables
Revises: 014_add_portfolio_models
Create Date: 2026-03-07

Tables:
1. monitor_universe — $1B+ market cap stocks with sector metadata
2. breadth_snapshots — daily breadth scan results + theme tracker
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "015_add_market_monitor_tables"
down_revision = "014_add_portfolio_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitor_universe",
        sa.Column("symbol", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_monitor_universe_sector", "monitor_universe", ["sector"])
    op.create_index("idx_monitor_universe_market_cap", "monitor_universe", ["market_cap"])

    op.create_table(
        "breadth_snapshots",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("universe", sa.String(50), nullable=False, server_default="large_cap_1b"),
        sa.Column("scans", postgresql.JSONB(), nullable=False),
        sa.Column("theme_tracker", postgresql.JSONB(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("breadth_snapshots")
    op.drop_table("monitor_universe")
```

**Step 2: Apply migration**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/alembic upgrade head`
Expected: Tables created successfully.

**Step 3: Commit**

```bash
git add alembic/versions/015_add_market_monitor_tables.py
git commit -m "feat(db): add monitor_universe and breadth_snapshots tables"
```

---

## Task 2: Universe Refresh Endpoint — `POST /api/market-monitor/refresh-universe`

**Files:**
- Create: `api/endpoints/market_monitor.py`
- Modify: `api/main.py` (add router)

**Step 1: Write tests for universe refresh**

Create: `tests/market_monitor/test_universe.py`

```python
"""Tests for monitor universe refresh logic."""

import pytest
from api.endpoints.market_monitor import _filter_large_cap, _enrich_with_sectors


def test_filter_large_cap_excludes_small():
    """Only stocks >= $1B market cap pass."""
    quotes = {
        "AAPL": {"quote": {"AAPL": {"fundamental": {"marketCap": 3_000_000_000_000}}}},
        "TINY": {"quote": {"TINY": {"fundamental": {"marketCap": 500_000_000}}}},
        "MID":  {"quote": {"MID":  {"fundamental": {"marketCap": 1_000_000_000}}}},
    }
    result = _filter_large_cap(quotes, min_cap=1_000_000_000)
    symbols = {r["symbol"] for r in result}
    assert "AAPL" in symbols
    assert "MID" in symbols
    assert "TINY" not in symbols


def test_filter_large_cap_extracts_sector():
    """Sector and industry are extracted from fundamental data."""
    quotes = {
        "AAPL": {
            "quote": {
                "AAPL": {
                    "fundamental": {
                        "marketCap": 3_000_000_000_000,
                        "declarationDate": "",  # noise field
                    },
                    "reference": {
                        "description": "Apple Inc",
                    },
                }
            },
            "fundamental": {
                "AAPL": {
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                },
            },
        },
    }
    result = _filter_large_cap(quotes, min_cap=1_000_000_000)
    assert len(result) == 1
    assert result[0]["sector"] == "Technology"
    assert result[0]["industry"] == "Consumer Electronics"
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/market_monitor/test_universe.py -v`
Expected: FAIL — `api.endpoints.market_monitor` does not exist yet.

**Step 3: Write the market monitor endpoint file**

Create: `api/endpoints/market_monitor.py`

```python
"""
Market Monitor endpoints.

Breadth heat map: counts stocks making extreme % moves across timeframes.
Theme Tracker: sector rotation rankings.
Universe: $1B+ market cap stocks refreshed weekly via Schwab.
"""

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.integrations.schwab.client import get_instruments, get_quotes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-monitor", tags=["market-monitor"])

# ── Constants ────────────────────────────────────────────────────────────────

MIN_MARKET_CAP = 1_000_000_000  # $1B
MIN_DOLLAR_VOLUME = 250_000     # avg(close,20) * avg(vol,20)

# Stockbee-style scan definitions
SCAN_DEFS = [
    {"key": "4pct_up_1d",      "direction": "up",   "threshold": 0.04, "lookback": 1},
    {"key": "4pct_down_1d",    "direction": "down", "threshold": 0.04, "lookback": 1},
    {"key": "25pct_up_20d",    "direction": "up",   "threshold": 0.25, "lookback": 20},
    {"key": "25pct_down_20d",  "direction": "down", "threshold": 0.25, "lookback": 20},
    {"key": "50pct_up_20d",    "direction": "up",   "threshold": 0.50, "lookback": 20},
    {"key": "50pct_down_20d",  "direction": "down", "threshold": 0.50, "lookback": 20},
    {"key": "13pct_up_34d",    "direction": "up",   "threshold": 0.13, "lookback": 34},
    {"key": "13pct_down_34d",  "direction": "down", "threshold": 0.13, "lookback": 34},
    {"key": "25pct_up_65d",    "direction": "up",   "threshold": 0.25, "lookback": 65},
    {"key": "25pct_down_65d",  "direction": "down", "threshold": 0.25, "lookback": 65},
]

THEME_PERIODS = {
    "1d": 1,
    "1w": 5,
    "1m": 20,
    "3m": 65,
}


# ── Pydantic Models ──────────────────────────────────────────────────────────

class UniverseRefreshResponse(BaseModel):
    total_symbols: int
    sectors: dict[str, int]
    duration_seconds: float


class ComputeResponse(BaseModel):
    date: str
    scans_computed: int
    theme_sectors: int
    total_tickers: int
    errors: int
    duration_seconds: float


class SnapshotSummary(BaseModel):
    date: str
    scans: dict[str, int]  # scan_key -> count only (no ticker lists)


class DrillDownResponse(BaseModel):
    date: str
    scan_key: str
    count: int
    tickers: list[dict[str, Any]]


class ThemeTrackerResponse(BaseModel):
    date: str
    sectors: dict[str, Any]


class SectorStocksResponse(BaseModel):
    date: str
    sector: str
    stocks: list[dict[str, Any]]


# ── Universe helpers ─────────────────────────────────────────────────────────

def _filter_large_cap(
    quotes: dict[str, Any], min_cap: int = MIN_MARKET_CAP
) -> list[dict[str, Any]]:
    """Filter batch quote results to stocks with market cap >= min_cap.

    Extracts symbol, name, market_cap, sector, industry from Schwab response.
    """
    results = []
    for symbol, data in quotes.items():
        try:
            # Schwab get_quotes returns nested structure
            quote_data = data if "fundamental" not in data else data
            fund = None
            ref = None

            # Navigate Schwab response structure
            if "quote" in data and symbol in data["quote"]:
                inner = data["quote"][symbol]
                fund = inner.get("fundamental", {})
                ref = inner.get("reference", {})
            elif "fundamental" in data:
                fund = data.get("fundamental", {}).get(symbol, {})
                ref = data.get("reference", {}).get(symbol, {})

            if not fund:
                continue

            mcap = fund.get("marketCap", 0)
            if not mcap or mcap < min_cap:
                continue

            sector = ""
            industry = ""
            if "fundamental" in data and symbol in data["fundamental"]:
                sector = data["fundamental"][symbol].get("sector", "")
                industry = data["fundamental"][symbol].get("industry", "")

            results.append({
                "symbol": symbol,
                "name": ref.get("description", "") if ref else "",
                "market_cap": int(mcap),
                "sector": sector,
                "industry": industry,
            })
        except Exception:
            logger.debug("Skipping %s in universe filter", symbol)
            continue
    return results
```

**Step 4: Register router in `api/main.py`**

Add import and include_router:

```python
from api.endpoints import iv_metrics, options, satyland, schwab, screener, market_monitor

# ... existing routers ...
app.include_router(market_monitor.router)
```

**Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/market_monitor/test_universe.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add api/endpoints/market_monitor.py api/main.py tests/market_monitor/
git commit -m "feat(api): add market monitor endpoint with universe refresh"
```

---

## Task 3: Breadth Compute Logic — `_compute_breadth_scans` + `_compute_theme_tracker`

**Files:**
- Modify: `api/endpoints/market_monitor.py`
- Create: `tests/market_monitor/test_breadth.py`

**Step 1: Write tests for breadth computation**

```python
"""Tests for breadth scan computation."""

import numpy as np
import pandas as pd
import pytest
from api.endpoints.market_monitor import _compute_breadth_scans, _compute_theme_tracker, SCAN_DEFS


def _make_price_df(tickers: list[str], days: int = 70) -> pd.DataFrame:
    """Build a synthetic multi-ticker OHLCV DataFrame matching yfinance format."""
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=days)
    arrays = {}
    for t in tickers:
        base = 100.0
        closes = [base]
        for _ in range(days - 1):
            closes.append(closes[-1] * (1 + np.random.uniform(-0.02, 0.02)))
        closes = np.array(closes)
        arrays[t] = {
            "Open": closes * 0.99,
            "High": closes * 1.01,
            "Low": closes * 0.98,
            "Close": closes,
            "Volume": np.full(days, 1_000_000),
        }
    # yfinance multi-ticker format: MultiIndex columns (Price, Ticker)
    cols = pd.MultiIndex.from_tuples(
        [(price, ticker) for ticker in tickers for price in ["Open", "High", "Low", "Close", "Volume"]],
        names=["Price", "Ticker"],
    )
    data = np.column_stack(
        [arrays[t][p] for t in tickers for p in ["Open", "High", "Low", "Close", "Volume"]]
    )
    return pd.DataFrame(data, index=dates, columns=cols)


def test_compute_breadth_scans_returns_all_keys():
    """Should return exactly 10 scan keys."""
    df = _make_price_df(["AAPL", "MSFT", "GOOG"], days=70)
    sectors = {"AAPL": "Technology", "MSFT": "Technology", "GOOG": "Communication Services"}
    result = _compute_breadth_scans(df, sectors)
    assert set(result.keys()) == {s["key"] for s in SCAN_DEFS}
    for key, val in result.items():
        assert "count" in val
        assert "tickers" in val
        assert isinstance(val["count"], int)
        assert isinstance(val["tickers"], list)


def test_4pct_up_detects_big_mover():
    """A stock that jumps 5% in one day should appear in 4pct_up_1d."""
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=70)
    closes = np.full(70, 100.0)
    closes[-1] = 106.0  # 6% jump on last day
    volume = np.full(70, 1_000_000)

    cols = pd.MultiIndex.from_tuples(
        [(p, "JUMP") for p in ["Open", "High", "Low", "Close", "Volume"]],
        names=["Price", "Ticker"],
    )
    data = np.column_stack([closes * 0.99, closes * 1.01, closes * 0.98, closes, volume])
    df = pd.DataFrame(data, index=dates, columns=cols)

    result = _compute_breadth_scans(df, {"JUMP": "Technology"})
    assert result["4pct_up_1d"]["count"] == 1
    assert result["4pct_up_1d"]["tickers"][0]["symbol"] == "JUMP"


def test_compute_theme_tracker_ranks_sectors():
    """Sectors should be ranked by net breadth."""
    df = _make_price_df(["AAPL", "MSFT", "XOM", "CVX"], days=70)
    sectors = {"AAPL": "Technology", "MSFT": "Technology", "XOM": "Energy", "CVX": "Energy"}
    result = _compute_theme_tracker(df, sectors)
    assert "Technology" in result
    assert "Energy" in result
    assert "rank_1d" in result["Technology"]
    assert "stock_count" in result["Technology"]
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/market_monitor/test_breadth.py -v`
Expected: FAIL — `_compute_breadth_scans` not defined yet.

**Step 3: Implement breadth computation**

Add to `api/endpoints/market_monitor.py`:

```python
# ── Breadth computation ──────────────────────────────────────────────────────

def _compute_breadth_scans(
    raw_df: pd.DataFrame,
    sectors: dict[str, str],
) -> dict[str, Any]:
    """Compute all 10 Stockbee-style breadth scans from a yfinance bulk DataFrame.

    Args:
        raw_df: MultiIndex DataFrame from yf.download (columns: Price x Ticker).
        sectors: Mapping of symbol -> GICS sector name.

    Returns:
        Dict keyed by scan name, each with count + ticker list.
    """
    results: dict[str, Any] = {}

    # Extract per-ticker close and volume Series
    try:
        close_df = raw_df["Close"]
        volume_df = raw_df["Volume"]
    except KeyError:
        # Single ticker edge case
        close_df = raw_df[["Close"]].rename(columns={"Close": raw_df.columns[0][1]})
        volume_df = raw_df[["Volume"]].rename(columns={"Volume": raw_df.columns[0][1]})

    tickers = list(close_df.columns)

    # Precompute dollar volume filter: avg(close,20) * avg(vol,20) >= $250k
    avg_close_20 = close_df.rolling(20).mean().iloc[-1]
    avg_vol_20 = volume_df.rolling(20).mean().iloc[-1]
    dollar_vol = avg_close_20 * avg_vol_20
    eligible = set(t for t in tickers if pd.notna(dollar_vol.get(t, 0)) and dollar_vol[t] >= MIN_DOLLAR_VOLUME)

    for scan_def in SCAN_DEFS:
        key = scan_def["key"]
        direction = scan_def["direction"]
        threshold = scan_def["threshold"]
        lookback = scan_def["lookback"]

        hits = []
        for ticker in tickers:
            if ticker not in eligible:
                continue
            closes = close_df[ticker].dropna()
            if len(closes) < lookback + 1:
                continue

            current_close = closes.iloc[-1]

            if lookback == 1:
                # Daily: compare to previous close
                prev_close = closes.iloc[-2]
                if prev_close <= 0:
                    continue
                pct = (current_close - prev_close) / prev_close
            else:
                # Multi-day: compare to min/max over lookback
                window = closes.iloc[-(lookback + 1):-1]
                if direction == "up":
                    ref = window.min()
                    if ref <= 0:
                        continue
                    pct = (current_close - ref) / ref
                else:
                    ref = window.max()
                    if ref <= 0:
                        continue
                    pct = (current_close - ref) / ref

            if direction == "up" and pct >= threshold:
                hits.append({
                    "symbol": ticker,
                    "pct_change": round(float(pct * 100), 2),
                    "close": round(float(current_close), 2),
                    "sector": sectors.get(ticker, "Unknown"),
                })
            elif direction == "down" and pct <= -threshold:
                hits.append({
                    "symbol": ticker,
                    "pct_change": round(float(pct * 100), 2),
                    "close": round(float(current_close), 2),
                    "sector": sectors.get(ticker, "Unknown"),
                })

        # Sort by magnitude (biggest movers first)
        hits.sort(key=lambda h: abs(h["pct_change"]), reverse=True)
        results[key] = {"count": len(hits), "tickers": hits}

    return results


def _compute_theme_tracker(
    raw_df: pd.DataFrame,
    sectors: dict[str, str],
) -> dict[str, Any]:
    """Compute sector rotation rankings across multiple periods.

    Args:
        raw_df: MultiIndex DataFrame from yf.download.
        sectors: Mapping of symbol -> GICS sector name.

    Returns:
        Dict keyed by sector name with gainers/losers/rank per period.
    """
    try:
        close_df = raw_df["Close"]
    except KeyError:
        close_df = raw_df[["Close"]].rename(columns={"Close": raw_df.columns[0][1]})

    tickers = list(close_df.columns)

    # Build per-sector stats
    sector_stats: dict[str, dict[str, Any]] = {}
    unique_sectors = set(sectors.values())
    for sec in unique_sectors:
        sector_stats[sec] = {"stock_count": 0}
        for period_key in THEME_PERIODS:
            sector_stats[sec][f"gainers_{period_key}"] = 0
            sector_stats[sec][f"losers_{period_key}"] = 0
            sector_stats[sec][f"net_{period_key}"] = 0

    for ticker in tickers:
        sec = sectors.get(ticker)
        if not sec or sec not in sector_stats:
            continue
        closes = close_df[ticker].dropna()
        if len(closes) < 2:
            continue

        sector_stats[sec]["stock_count"] += 1

        for period_key, lookback in THEME_PERIODS.items():
            if len(closes) < lookback + 1:
                continue
            current = closes.iloc[-1]
            past = closes.iloc[-(lookback + 1)]
            if past <= 0:
                continue
            pct = (current - past) / past
            if pct > 0:
                sector_stats[sec][f"gainers_{period_key}"] += 1
            elif pct < 0:
                sector_stats[sec][f"losers_{period_key}"] += 1
            sector_stats[sec][f"net_{period_key}"] = (
                sector_stats[sec][f"gainers_{period_key}"]
                - sector_stats[sec][f"losers_{period_key}"]
            )

    # Compute rankings per period
    for period_key in THEME_PERIODS:
        net_key = f"net_{period_key}"
        rank_key = f"rank_{period_key}"
        sorted_sectors = sorted(
            sector_stats.keys(),
            key=lambda s: sector_stats[s].get(net_key, 0),
            reverse=True,
        )
        for rank, sec in enumerate(sorted_sectors, 1):
            sector_stats[sec][rank_key] = rank

    return sector_stats
```

**Step 4: Run tests to verify they pass**

Run: `venv/bin/pytest tests/market_monitor/test_breadth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/endpoints/market_monitor.py tests/market_monitor/test_breadth.py
git commit -m "feat(api): add breadth scan and theme tracker computation"
```

---

## Task 4: API Endpoints — compute, snapshots, drill-down, theme-tracker, backfill

**Files:**
- Modify: `api/endpoints/market_monitor.py`

**Step 1: Write endpoint integration tests**

Create: `tests/market_monitor/test_endpoints.py`

```python
"""Integration tests for market monitor endpoints (mocked data)."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient
from api.main import app


@pytest.mark.asyncio
async def test_snapshots_endpoint_returns_list():
    """GET /api/market-monitor/snapshots should return a list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/market-monitor/snapshots?days=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_drill_down_requires_params():
    """GET /api/market-monitor/drill-down needs date and scan params."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/market-monitor/drill-down")
    assert resp.status_code == 422  # missing query params
```

**Step 2: Implement all API endpoints**

Add to `api/endpoints/market_monitor.py`:

```python
# ── Supabase helpers ─────────────────────────────────────────────────────────

def _get_supabase():
    """Get Supabase client for server-side operations."""
    import os
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/refresh-universe", response_model=UniverseRefreshResponse)
async def refresh_universe():
    """Refresh the $1B+ market cap universe from Schwab fundamentals."""
    t0 = time.monotonic()
    supabase = _get_supabase()

    # Schwab get_instruments with fundamental projection returns sector data
    # We'll query broad market and filter by market cap
    # For now, use a known large list approach — fetch S&P 500 + Russell 1000
    # which covers the majority of $1B+ stocks
    from api.endpoints.screener import _load_universe
    seed_tickers = _load_universe(["all"])

    # Batch fetch fundamentals via Schwab get_quotes (includes market cap)
    batch_size = 100
    all_stocks = []

    for i in range(0, len(seed_tickers), batch_size):
        batch = seed_tickers[i : i + batch_size]
        try:
            quotes = await asyncio.to_thread(get_quotes, batch)
            for symbol, data in quotes.items():
                try:
                    quote_info = data.get("quote", {})
                    fund = data.get("fundamental", {})
                    ref = data.get("reference", {})
                    mcap = fund.get("marketCap", 0) or quote_info.get("marketCap", 0)
                    if mcap and mcap >= MIN_MARKET_CAP:
                        all_stocks.append({
                            "symbol": symbol,
                            "name": ref.get("description", ""),
                            "market_cap": int(mcap),
                            "sector": fund.get("sector", "Unknown"),
                            "industry": fund.get("industry", "Unknown"),
                            "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Batch quote error at offset %d: %s", i, exc)
            continue

    # Upsert to Supabase
    if all_stocks:
        supabase.table("monitor_universe").upsert(all_stocks, on_conflict="symbol").execute()

    sectors_count: dict[str, int] = {}
    for s in all_stocks:
        sec = s["sector"]
        sectors_count[sec] = sectors_count.get(sec, 0) + 1

    return UniverseRefreshResponse(
        total_symbols=len(all_stocks),
        sectors=sectors_count,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


@router.post("/compute", response_model=ComputeResponse)
async def compute_breadth(target_date: str | None = Query(None)):
    """Compute breadth snapshot for a given date (default: today)."""
    t0 = time.monotonic()
    supabase = _get_supabase()
    snap_date = date.fromisoformat(target_date) if target_date else date.today()

    # Load universe
    resp = supabase.table("monitor_universe").select("symbol, sector").execute()
    universe = resp.data or []
    if not universe:
        raise HTTPException(status_code=400, detail="Universe is empty. Run refresh-universe first.")

    tickers = [u["symbol"] for u in universe]
    sectors = {u["symbol"]: u.get("sector", "Unknown") for u in universe}

    # Bulk download price history (65 trading days + buffer)
    raw_df = await asyncio.to_thread(
        yf.download,
        tickers,
        period="5mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw_df.empty:
        raise HTTPException(status_code=500, detail="yfinance returned no data")

    errors = len(tickers) - len(raw_df.columns.get_level_values("Ticker").unique())

    # Compute breadth scans
    scans = await asyncio.to_thread(_compute_breadth_scans, raw_df, sectors)

    # Compute theme tracker
    theme = await asyncio.to_thread(_compute_theme_tracker, raw_df, sectors)

    # Upsert to Supabase
    supabase.table("breadth_snapshots").upsert({
        "date": snap_date.isoformat(),
        "universe": "large_cap_1b",
        "scans": scans,
        "theme_tracker": theme,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="date").execute()

    return ComputeResponse(
        date=snap_date.isoformat(),
        scans_computed=len(scans),
        theme_sectors=len(theme),
        total_tickers=len(tickers),
        errors=errors,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


@router.get("/snapshots")
async def get_snapshots(days: int = Query(30, ge=1, le=90)):
    """Return last N days of breadth snapshots (counts only, no ticker lists)."""
    supabase = _get_supabase()
    resp = (
        supabase.table("breadth_snapshots")
        .select("date, scans, computed_at")
        .order("date", desc=True)
        .limit(days)
        .execute()
    )

    summaries = []
    for row in reversed(resp.data or []):
        scan_counts = {}
        for key, val in row["scans"].items():
            scan_counts[key] = val["count"] if isinstance(val, dict) else val
        summaries.append({
            "date": row["date"],
            "scans": scan_counts,
            "computed_at": row["computed_at"],
        })
    return summaries


@router.get("/drill-down", response_model=DrillDownResponse)
async def drill_down(
    scan: str = Query(..., description="Scan key like 4pct_up_1d"),
    target_date: str = Query(..., alias="date", description="YYYY-MM-DD"),
):
    """Return ticker list for a specific scan + date."""
    supabase = _get_supabase()
    resp = (
        supabase.table("breadth_snapshots")
        .select("scans")
        .eq("date", target_date)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"No snapshot for {target_date}")

    scan_data = resp.data["scans"].get(scan)
    if not scan_data:
        raise HTTPException(status_code=404, detail=f"Scan {scan} not found for {target_date}")

    return DrillDownResponse(
        date=target_date,
        scan_key=scan,
        count=scan_data["count"],
        tickers=scan_data["tickers"],
    )


@router.get("/theme-tracker", response_model=ThemeTrackerResponse)
async def get_theme_tracker(target_date: str | None = Query(None, alias="date")):
    """Return theme tracker for a specific date (or latest)."""
    supabase = _get_supabase()
    query = supabase.table("breadth_snapshots").select("date, theme_tracker")
    if target_date:
        query = query.eq("date", target_date)
    else:
        query = query.order("date", desc=True).limit(1)

    resp = query.single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="No snapshot found")

    return ThemeTrackerResponse(
        date=resp.data["date"],
        sectors=resp.data["theme_tracker"] or {},
    )


@router.get("/sector-stocks", response_model=SectorStocksResponse)
async def get_sector_stocks(
    sector: str = Query(...),
    target_date: str | None = Query(None, alias="date"),
):
    """Return all stocks in a sector with % changes for drill-down."""
    supabase = _get_supabase()

    # Get the snapshot
    query = supabase.table("breadth_snapshots").select("date, scans")
    if target_date:
        query = query.eq("date", target_date)
    else:
        query = query.order("date", desc=True).limit(1)
    resp = query.single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="No snapshot found")

    # Collect all tickers in the requested sector across all scans
    seen: dict[str, dict] = {}
    for scan_key, scan_data in resp.data["scans"].items():
        for ticker in scan_data.get("tickers", []):
            if ticker.get("sector") == sector and ticker["symbol"] not in seen:
                seen[ticker["symbol"]] = ticker

    stocks = sorted(seen.values(), key=lambda s: abs(s.get("pct_change", 0)), reverse=True)

    return SectorStocksResponse(
        date=resp.data["date"],
        sector=sector,
        stocks=stocks,
    )


@router.post("/backfill")
async def backfill(days: int = Query(65, ge=1, le=120)):
    """One-time: compute snapshots for the last N trading days.

    Uses a single yfinance bulk download, then slices the DataFrame
    for each historical date to compute that day's breadth.
    """
    t0 = time.monotonic()
    supabase = _get_supabase()

    # Load universe
    resp = supabase.table("monitor_universe").select("symbol, sector").execute()
    universe = resp.data or []
    if not universe:
        raise HTTPException(status_code=400, detail="Universe is empty. Run refresh-universe first.")

    tickers = [u["symbol"] for u in universe]
    sectors = {u["symbol"]: u.get("sector", "Unknown") for u in universe}

    # Bulk download enough history (days + 65 day lookback buffer)
    raw_df = await asyncio.to_thread(
        yf.download,
        tickers,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw_df.empty:
        raise HTTPException(status_code=500, detail="yfinance returned no data")

    trading_dates = raw_df.index[-days:]
    snapshots = []
    errors_total = 0

    for snap_date in trading_dates:
        # Slice DataFrame up to this date
        sliced = raw_df.loc[:snap_date]
        if len(sliced) < 66:  # need at least 65 + 1 days
            continue

        scans = _compute_breadth_scans(sliced, sectors)
        theme = _compute_theme_tracker(sliced, sectors)

        snapshots.append({
            "date": snap_date.strftime("%Y-%m-%d"),
            "universe": "large_cap_1b",
            "scans": scans,
            "theme_tracker": theme,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })

    # Batch upsert
    if snapshots:
        supabase.table("breadth_snapshots").upsert(snapshots, on_conflict="date").execute()

    return {
        "days_computed": len(snapshots),
        "total_tickers": len(tickers),
        "duration_seconds": round(time.monotonic() - t0, 2),
    }
```

**Step 3: Run tests**

Run: `venv/bin/pytest tests/market_monitor/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add api/endpoints/market_monitor.py tests/market_monitor/
git commit -m "feat(api): add all market monitor endpoints (snapshots, drill-down, backfill)"
```

---

## Task 5: Vercel Cron Route + vercel.json

**Files:**
- Create: `frontend/src/app/api/cron/market-monitor/route.ts`
- Modify: `frontend/vercel.json`

**Step 1: Create cron route**

```typescript
import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export const maxDuration = 300

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET
  if (!cronSecret) {
    return NextResponse.json({ error: "CRON_SECRET not configured" }, { status: 500 })
  }

  const authHeader = request.headers.get("authorization")
  if (authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const start = Date.now()

  // Compute today's breadth snapshot
  let computeOk = false
  let computeError: string | undefined
  let computeResult: unknown = null

  try {
    const res = await railwayFetch("/api/market-monitor/compute")
    computeResult = await res.json()
    computeOk = true
  } catch (err) {
    computeError = String(err)
  }

  return NextResponse.json({
    success: computeOk,
    compute: { success: computeOk, result: computeResult, error: computeError },
    total_duration_ms: Date.now() - start,
  })
}
```

**Step 2: Update vercel.json**

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-screeners",
      "schedule": "0 14 * * 1-5"
    },
    {
      "path": "/api/cron/market-monitor",
      "schedule": "5 21 * * 1-5"
    }
  ]
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/api/cron/market-monitor/route.ts frontend/vercel.json
git commit -m "feat(cron): add market monitor daily cron at 1:05 PM PST"
```

---

## Task 6: Frontend API Routes (proxy to Railway)

**Files:**
- Create: `frontend/src/app/api/market-monitor/snapshots/route.ts`
- Create: `frontend/src/app/api/market-monitor/drill-down/route.ts`
- Create: `frontend/src/app/api/market-monitor/theme-tracker/route.ts`
- Create: `frontend/src/app/api/market-monitor/sector-stocks/route.ts`
- Create: `frontend/src/app/api/market-monitor/compute/route.ts`

**Step 1: Create snapshot proxy**

`frontend/src/app/api/market-monitor/snapshots/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const days = request.nextUrl.searchParams.get("days") ?? "30"
  const supabase = createServerClient()

  const { data, error } = await supabase
    .from("breadth_snapshots")
    .select("date, scans, computed_at")
    .order("date", { ascending: false })
    .limit(Number(days))

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  // Return counts only (strip ticker lists for performance)
  const summaries = (data ?? []).reverse().map((row) => ({
    date: row.date,
    computed_at: row.computed_at,
    scans: Object.fromEntries(
      Object.entries(row.scans as Record<string, { count: number }>).map(
        ([key, val]) => [key, val.count]
      )
    ),
  }))

  return NextResponse.json(summaries, {
    headers: { "Cache-Control": "s-maxage=60, stale-while-revalidate=300" },
  })
}
```

**Step 2: Create drill-down proxy**

`frontend/src/app/api/market-monitor/drill-down/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const scanKey = request.nextUrl.searchParams.get("scan")
  const targetDate = request.nextUrl.searchParams.get("date")

  if (!scanKey || !targetDate) {
    return NextResponse.json({ error: "scan and date required" }, { status: 400 })
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from("breadth_snapshots")
    .select("scans")
    .eq("date", targetDate)
    .single()

  if (error || !data) {
    return NextResponse.json({ error: "Snapshot not found" }, { status: 404 })
  }

  const scanData = (data.scans as Record<string, any>)[scanKey]
  if (!scanData) {
    return NextResponse.json({ error: `Scan ${scanKey} not found` }, { status: 404 })
  }

  return NextResponse.json({
    date: targetDate,
    scan_key: scanKey,
    count: scanData.count,
    tickers: scanData.tickers,
  })
}
```

**Step 3: Create theme-tracker proxy**

`frontend/src/app/api/market-monitor/theme-tracker/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const targetDate = request.nextUrl.searchParams.get("date")
  const supabase = createServerClient()

  let query = supabase.from("breadth_snapshots").select("date, theme_tracker")
  if (targetDate) {
    query = query.eq("date", targetDate)
  } else {
    query = query.order("date", { ascending: false }).limit(1)
  }

  const { data, error } = await query.single()

  if (error || !data) {
    return NextResponse.json({ error: "No snapshot found" }, { status: 404 })
  }

  return NextResponse.json({
    date: data.date,
    sectors: data.theme_tracker ?? {},
  })
}
```

**Step 4: Create sector-stocks proxy**

`frontend/src/app/api/market-monitor/sector-stocks/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const sector = request.nextUrl.searchParams.get("sector")
  const targetDate = request.nextUrl.searchParams.get("date")

  if (!sector) {
    return NextResponse.json({ error: "sector required" }, { status: 400 })
  }

  const supabase = createServerClient()
  let query = supabase.from("breadth_snapshots").select("date, scans")
  if (targetDate) {
    query = query.eq("date", targetDate)
  } else {
    query = query.order("date", { ascending: false }).limit(1)
  }

  const { data, error } = await query.single()
  if (error || !data) {
    return NextResponse.json({ error: "No snapshot found" }, { status: 404 })
  }

  const seen: Record<string, any> = {}
  for (const scanData of Object.values(data.scans as Record<string, any>)) {
    for (const ticker of scanData.tickers ?? []) {
      if (ticker.sector === sector && !seen[ticker.symbol]) {
        seen[ticker.symbol] = ticker
      }
    }
  }

  const stocks = Object.values(seen).sort(
    (a: any, b: any) => Math.abs(b.pct_change ?? 0) - Math.abs(a.pct_change ?? 0)
  )

  return NextResponse.json({ date: data.date, sector, stocks })
}
```

**Step 5: Create compute (force recompute) proxy**

`frontend/src/app/api/market-monitor/compute/route.ts`:
```typescript
import { NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"
import { RailwayError } from "@/lib/errors"

export const maxDuration = 300

export async function POST() {
  try {
    const res = await railwayFetch("/api/market-monitor/compute")
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json({ error: error.detail }, { status: error.status })
    }
    return NextResponse.json({ error: "Backend unavailable" }, { status: 502 })
  }
}
```

**Step 6: Commit**

```bash
git add frontend/src/app/api/market-monitor/
git commit -m "feat(frontend): add market monitor API proxy routes"
```

---

## Task 7: TypeScript Types + `useMarketMonitor` Hook

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/hooks/use-market-monitor.ts`

**Step 1: Add types to `types.ts`**

```typescript
// ── Market Monitor ──────────────────────────────────────────────────────────

export interface BreadthSnapshotSummary {
  date: string
  computed_at: string
  scans: Record<string, number> // scan_key -> count
}

export interface DrillDownTicker {
  symbol: string
  pct_change: number
  close: number
  sector: string
}

export interface DrillDownResponse {
  date: string
  scan_key: string
  count: number
  tickers: DrillDownTicker[]
}

export interface SectorData {
  gainers_1d: number
  losers_1d: number
  net_1d: number
  gainers_1w: number
  losers_1w: number
  net_1w: number
  gainers_1m: number
  losers_1m: number
  net_1m: number
  gainers_3m: number
  losers_3m: number
  net_3m: number
  rank_1d: number
  rank_1w: number
  rank_1m: number
  rank_3m: number
  stock_count: number
}

export interface ThemeTrackerResponse {
  date: string
  sectors: Record<string, SectorData>
}

export interface SectorStocksResponse {
  date: string
  sector: string
  stocks: DrillDownTicker[]
}
```

**Step 2: Create hook**

`frontend/src/hooks/use-market-monitor.ts`:
```typescript
"use client"

import { useState, useEffect, useCallback } from "react"
import type {
  BreadthSnapshotSummary,
  DrillDownResponse,
  ThemeTrackerResponse,
  SectorStocksResponse,
} from "@/lib/types"

interface SelectedCell {
  scanKey: string
  date: string
}

export function useMarketMonitor() {
  const [snapshots, setSnapshots] = useState<BreadthSnapshotSummary[]>([])
  const [themeTracker, setThemeTracker] = useState<ThemeTrackerResponse | null>(null)
  const [drillDown, setDrillDown] = useState<DrillDownResponse | null>(null)
  const [sectorStocks, setSectorStocks] = useState<SectorStocksResponse | null>(null)
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null)
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [computing, setComputing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch snapshots + theme tracker on mount
  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [snapRes, themeRes] = await Promise.all([
          fetch("/api/market-monitor/snapshots?days=30"),
          fetch("/api/market-monitor/theme-tracker"),
        ])
        if (snapRes.ok) setSnapshots(await snapRes.json())
        if (themeRes.ok) setThemeTracker(await themeRes.json())
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Fetch drill-down when cell is selected
  const selectCell = useCallback(async (scanKey: string, date: string) => {
    setSelectedCell({ scanKey, date })
    setSelectedSector(null)
    setSectorStocks(null)
    setDrillDown(null)
    try {
      const res = await fetch(
        `/api/market-monitor/drill-down?scan=${encodeURIComponent(scanKey)}&date=${encodeURIComponent(date)}`
      )
      if (res.ok) setDrillDown(await res.json())
    } catch {
      // drill-down failed silently
    }
  }, [])

  // Fetch sector stocks when sector is selected
  const selectSector = useCallback(async (sector: string, date?: string) => {
    setSelectedSector(sector)
    setSelectedCell(null)
    setDrillDown(null)
    setSectorStocks(null)
    try {
      const params = new URLSearchParams({ sector })
      if (date) params.set("date", date)
      const res = await fetch(`/api/market-monitor/sector-stocks?${params}`)
      if (res.ok) setSectorStocks(await res.json())
    } catch {
      // sector drill-down failed silently
    }
  }, [])

  // Force recompute
  const forceRecompute = useCallback(async () => {
    setComputing(true)
    try {
      const res = await fetch("/api/market-monitor/compute", { method: "POST" })
      if (res.ok) {
        // Reload snapshots + theme tracker
        const [snapRes, themeRes] = await Promise.all([
          fetch("/api/market-monitor/snapshots?days=30"),
          fetch("/api/market-monitor/theme-tracker"),
        ])
        if (snapRes.ok) setSnapshots(await snapRes.json())
        if (themeRes.ok) setThemeTracker(await themeRes.json())
      }
    } finally {
      setComputing(false)
    }
  }, [])

  const closePanel = useCallback(() => {
    setSelectedCell(null)
    setSelectedSector(null)
    setDrillDown(null)
    setSectorStocks(null)
  }, [])

  const panelOpen = !!(selectedCell || selectedSector)

  return {
    snapshots,
    themeTracker,
    drillDown,
    sectorStocks,
    selectedCell,
    selectedSector,
    loading,
    computing,
    error,
    panelOpen,
    selectCell,
    selectSector,
    closePanel,
    forceRecompute,
  }
}
```

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/hooks/use-market-monitor.ts
git commit -m "feat(frontend): add market monitor types and hook"
```

---

## Task 8: Breadth Heat Map Component

**Files:**
- Create: `frontend/src/components/market-monitor/breadth-heat-map.tsx`
- Create: `frontend/src/components/market-monitor/heat-map-cell.tsx`

**Step 1: Create heat-map-cell**

`frontend/src/components/market-monitor/heat-map-cell.tsx`:
```typescript
"use client"

import { cn } from "@/lib/utils"

interface HeatMapCellProps {
  count: number
  date: string
  direction: "up" | "down"
  min: number
  max: number
  selected: boolean
  onClick: () => void
}

function intensityColor(count: number, min: number, max: number, direction: "up" | "down"): string {
  if (max === min) return "bg-muted"
  const ratio = Math.min((count - min) / (max - min), 1)

  if (direction === "up") {
    if (ratio < 0.2) return "bg-muted"
    if (ratio < 0.4) return "bg-emerald-950"
    if (ratio < 0.6) return "bg-emerald-900"
    if (ratio < 0.8) return "bg-emerald-700"
    return "bg-emerald-500"
  } else {
    if (ratio < 0.2) return "bg-muted"
    if (ratio < 0.4) return "bg-red-950"
    if (ratio < 0.6) return "bg-red-900"
    if (ratio < 0.8) return "bg-red-700"
    return "bg-red-500"
  }
}

export function HeatMapCell({ count, date, direction, min, max, selected, onClick }: HeatMapCellProps) {
  return (
    <button
      onClick={onClick}
      title={`${date}: ${count} stocks`}
      className={cn(
        "w-10 h-8 text-xs font-mono rounded-sm transition-all cursor-pointer",
        "hover:ring-1 hover:ring-white/30",
        intensityColor(count, min, max, direction),
        selected && "ring-2 ring-white"
      )}
    >
      {count}
    </button>
  )
}
```

**Step 2: Create breadth-heat-map**

`frontend/src/components/market-monitor/breadth-heat-map.tsx`:
```typescript
"use client"

import { useMemo } from "react"
import type { BreadthSnapshotSummary } from "@/lib/types"
import { HeatMapCell } from "./heat-map-cell"

interface SelectedCell {
  scanKey: string
  date: string
}

interface BreadthHeatMapProps {
  snapshots: BreadthSnapshotSummary[]
  selectedCell: SelectedCell | null
  onCellClick: (scanKey: string, date: string) => void
}

const SCAN_GROUPS = [
  {
    label: "Daily",
    rows: [
      { key: "4pct_up_1d", label: "▲ 4%", direction: "up" as const },
      { key: "4pct_down_1d", label: "▼ 4%", direction: "down" as const },
    ],
  },
  {
    label: "Monthly (20d)",
    rows: [
      { key: "25pct_up_20d", label: "▲ 25%", direction: "up" as const },
      { key: "25pct_down_20d", label: "▼ 25%", direction: "down" as const },
      { key: "50pct_up_20d", label: "▲ 50%", direction: "up" as const },
      { key: "50pct_down_20d", label: "▼ 50%", direction: "down" as const },
    ],
  },
  {
    label: "Intermediate (34d)",
    rows: [
      { key: "13pct_up_34d", label: "▲ 13%", direction: "up" as const },
      { key: "13pct_down_34d", label: "▼ 13%", direction: "down" as const },
    ],
  },
  {
    label: "Quarterly (65d)",
    rows: [
      { key: "25pct_up_65d", label: "▲ 25%", direction: "up" as const },
      { key: "25pct_down_65d", label: "▼ 25%", direction: "down" as const },
    ],
  },
]

export function BreadthHeatMap({ snapshots, selectedCell, onCellClick }: BreadthHeatMapProps) {
  // Precompute min/max per scan row for color scaling
  const ranges = useMemo(() => {
    const r: Record<string, { min: number; max: number }> = {}
    for (const group of SCAN_GROUPS) {
      for (const row of group.rows) {
        const values = snapshots.map((s) => s.scans[row.key] ?? 0)
        r[row.key] = {
          min: Math.min(...values),
          max: Math.max(...values),
        }
      }
    }
    return r
  }, [snapshots])

  if (snapshots.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-8 text-center">
        No breadth data available. Run a compute or backfill first.
      </div>
    )
  }

  return (
    <div className="space-y-1 overflow-x-auto">
      {SCAN_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium px-1 py-0.5">
            {group.label}
          </div>
          {group.rows.map((row) => (
            <div key={row.key} className="flex items-center gap-0.5">
              <div className="w-16 text-xs text-muted-foreground font-mono shrink-0">
                {row.label}
              </div>
              <div className="flex gap-0.5">
                {snapshots.map((snap) => (
                  <HeatMapCell
                    key={`${row.key}-${snap.date}`}
                    count={snap.scans[row.key] ?? 0}
                    date={snap.date}
                    direction={row.direction}
                    min={ranges[row.key]?.min ?? 0}
                    max={ranges[row.key]?.max ?? 1}
                    selected={
                      selectedCell?.scanKey === row.key && selectedCell?.date === snap.date
                    }
                    onClick={() => onCellClick(row.key, snap.date)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/market-monitor/
git commit -m "feat(frontend): add breadth heat map grid component"
```

---

## Task 9: Drill-Down Side Panel

**Files:**
- Create: `frontend/src/components/market-monitor/drill-down-panel.tsx`

**Step 1: Create panel using shadcn Sheet**

```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { DrillDownResponse, SectorStocksResponse, DrillDownTicker } from "@/lib/types"
import Link from "next/link"

interface DrillDownPanelProps {
  open: boolean
  onClose: () => void
  drillDown: DrillDownResponse | null
  sectorStocks: SectorStocksResponse | null
  selectedSector: string | null
}

function ScanLabel({ scanKey }: { scanKey: string }) {
  const labels: Record<string, string> = {
    "4pct_up_1d": "▲ 4% Daily",
    "4pct_down_1d": "▼ 4% Daily",
    "25pct_up_20d": "▲ 25% Monthly",
    "25pct_down_20d": "▼ 25% Monthly",
    "50pct_up_20d": "▲ 50% Monthly",
    "50pct_down_20d": "▼ 50% Monthly",
    "13pct_up_34d": "▲ 13% Intermediate",
    "13pct_down_34d": "▼ 13% Intermediate",
    "25pct_up_65d": "▲ 25% Quarterly",
    "25pct_down_65d": "▼ 25% Quarterly",
  }
  return <span>{labels[scanKey] ?? scanKey}</span>
}

function TickerRow({ ticker, selected, onSelect }: {
  ticker: DrillDownTicker
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-md transition-colors
        ${selected ? "bg-accent" : "hover:bg-muted"}`}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono font-medium">{ticker.symbol}</span>
        <Badge variant="outline" className="text-[10px]">{ticker.sector}</Badge>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground">${ticker.close}</span>
        <span className={ticker.pct_change >= 0 ? "text-emerald-400" : "text-red-400"}>
          {ticker.pct_change >= 0 ? "+" : ""}{ticker.pct_change}%
        </span>
      </div>
    </button>
  )
}

export function DrillDownPanel({ open, onClose, drillDown, sectorStocks, selectedSector }: DrillDownPanelProps) {
  const [selectedIdx, setSelectedIdx] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)

  const tickers = drillDown?.tickers ?? sectorStocks?.stocks ?? []
  const title = drillDown
    ? `${drillDown.date} — ${drillDown.count} stocks`
    : selectedSector
    ? `${selectedSector} — ${tickers.length} stocks`
    : ""

  // Reset selection when data changes
  useEffect(() => setSelectedIdx(0), [drillDown, sectorStocks])

  // Arrow key navigation
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIdx((i) => Math.min(i + 1, tickers.length - 1))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIdx((i) => Math.max(i - 1, 0))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, tickers.length])

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-[420px] sm:w-[420px] p-0">
        <SheetHeader className="px-4 pt-4 pb-2">
          <SheetTitle className="text-sm">
            {drillDown && <ScanLabel scanKey={drillDown.scan_key} />}
            {selectedSector && selectedSector}
          </SheetTitle>
          <p className="text-xs text-muted-foreground">{title}</p>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-80px)]" ref={listRef}>
          <div className="px-2 pb-4 space-y-0.5">
            {tickers.map((ticker, idx) => (
              <div key={ticker.symbol}>
                <TickerRow
                  ticker={ticker}
                  selected={idx === selectedIdx}
                  onSelect={() => setSelectedIdx(idx)}
                />
                {idx === selectedIdx && (
                  <div className="px-3 py-2 mb-1 rounded-md bg-muted/50 space-y-2">
                    <Link
                      href={`/analyze/${ticker.symbol}`}
                      className="text-xs text-blue-400 hover:underline"
                    >
                      Open full analysis →
                    </Link>
                  </div>
                )}
              </div>
            ))}
            {tickers.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                Loading...
              </p>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/market-monitor/drill-down-panel.tsx
git commit -m "feat(frontend): add drill-down side panel with arrow key navigation"
```

---

## Task 10: Theme Tracker Table Component

**Files:**
- Create: `frontend/src/components/market-monitor/theme-tracker-table.tsx`

**Step 1: Create component**

```typescript
"use client"

import { useMemo } from "react"
import { Badge } from "@/components/ui/badge"
import type { ThemeTrackerResponse } from "@/lib/types"

interface ThemeTrackerTableProps {
  data: ThemeTrackerResponse | null
  onSectorClick: (sector: string) => void
  selectedSector: string | null
}

function rankColor(rank: number): string {
  if (rank <= 3) return "text-emerald-400"
  if (rank <= 6) return "text-emerald-700"
  if (rank <= 8) return "text-muted-foreground"
  return "text-red-400"
}

function hasDivergence(data: Record<string, number>): boolean {
  const ranks = [data.rank_1d, data.rank_1w, data.rank_1m, data.rank_3m].filter(Boolean)
  if (ranks.length < 2) return false
  const hasTop = ranks.some((r) => r <= 3)
  const hasBottom = ranks.some((r) => r >= 9)
  return hasTop && hasBottom
}

export function ThemeTrackerTable({ data, onSectorClick, selectedSector }: ThemeTrackerTableProps) {
  const sortedSectors = useMemo(() => {
    if (!data?.sectors) return []
    return Object.entries(data.sectors)
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => (a.rank_1d ?? 99) - (b.rank_1d ?? 99))
  }, [data])

  if (!data || sortedSectors.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No theme tracker data available.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs">
            <th className="text-left py-2 px-3 font-medium">Sector</th>
            <th className="text-center py-2 px-2 font-medium">1D</th>
            <th className="text-center py-2 px-2 font-medium">1W</th>
            <th className="text-center py-2 px-2 font-medium">1M</th>
            <th className="text-center py-2 px-2 font-medium">3M</th>
            <th className="text-center py-2 px-2 font-medium">Stocks</th>
          </tr>
        </thead>
        <tbody>
          {sortedSectors.map((sector) => (
            <tr
              key={sector.name}
              onClick={() => onSectorClick(sector.name)}
              className={`border-b border-border/50 cursor-pointer transition-colors
                ${selectedSector === sector.name ? "bg-accent" : "hover:bg-muted/50"}`}
            >
              <td className="py-2 px-3 font-medium flex items-center gap-2">
                {sector.name}
                {hasDivergence(sector) && (
                  <Badge variant="outline" className="text-[9px] text-yellow-500 border-yellow-500/30">
                    Rotation
                  </Badge>
                )}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1d)}`}>
                #{sector.rank_1d}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1w)}`}>
                #{sector.rank_1w}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1m)}`}>
                #{sector.rank_1m}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_3m)}`}>
                #{sector.rank_3m}
              </td>
              <td className="text-center py-2 px-2 text-muted-foreground">
                {sector.stock_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/market-monitor/theme-tracker-table.tsx
git commit -m "feat(frontend): add theme tracker sector rotation table"
```

---

## Task 11: Market Monitor Page + Sidebar Nav

**Files:**
- Create: `frontend/src/app/market-monitor/page.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx` (add nav item)

**Step 1: Create the page**

`frontend/src/app/market-monitor/page.tsx`:
```typescript
"use client"

import { Button } from "@/components/ui/button"
import { RefreshCw } from "lucide-react"
import { useMarketMonitor } from "@/hooks/use-market-monitor"
import { BreadthHeatMap } from "@/components/market-monitor/breadth-heat-map"
import { DrillDownPanel } from "@/components/market-monitor/drill-down-panel"
import { ThemeTrackerTable } from "@/components/market-monitor/theme-tracker-table"

export default function MarketMonitorPage() {
  const monitor = useMarketMonitor()

  const lastUpdated = monitor.snapshots.length > 0
    ? monitor.snapshots[monitor.snapshots.length - 1].computed_at
    : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold">Market Monitor</h1>
          <p className="text-xs text-muted-foreground">
            Breadth of $1B+ stocks making extreme moves
            {lastUpdated && (
              <> · Updated {new Date(lastUpdated).toLocaleString()}</>
            )}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={monitor.forceRecompute}
          disabled={monitor.computing}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${monitor.computing ? "animate-spin" : ""}`} />
          {monitor.computing ? "Computing..." : "Force Recompute"}
        </Button>
      </div>

      {/* Loading state */}
      {monitor.loading && (
        <div className="text-sm text-muted-foreground text-center py-12">
          Loading breadth data...
        </div>
      )}

      {/* Error state */}
      {monitor.error && (
        <div className="text-sm text-red-400 text-center py-4">
          {monitor.error}
        </div>
      )}

      {/* Heat Map */}
      {!monitor.loading && (
        <BreadthHeatMap
          snapshots={monitor.snapshots}
          selectedCell={monitor.selectedCell}
          onCellClick={monitor.selectCell}
        />
      )}

      {/* Theme Tracker */}
      {!monitor.loading && (
        <div>
          <h2 className="text-sm font-semibold mb-2">Theme Tracker</h2>
          <ThemeTrackerTable
            data={monitor.themeTracker}
            onSectorClick={(sector) => monitor.selectSector(sector)}
            selectedSector={monitor.selectedSector}
          />
        </div>
      )}

      {/* Drill-down side panel */}
      <DrillDownPanel
        open={monitor.panelOpen}
        onClose={monitor.closePanel}
        drillDown={monitor.drillDown}
        sectorStocks={monitor.sectorStocks}
        selectedSector={monitor.selectedSector}
      />
    </div>
  )
}
```

**Step 2: Add to sidebar nav**

In `frontend/src/components/layout/sidebar.tsx`, add to `navItems`:

```typescript
import { Activity } from "lucide-react"

// Add to navItems array after "Screener":
{ label: "Market Monitor", href: "/market-monitor", icon: Activity },
```

**Step 3: Verify build**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npx tsc --noEmit`
Expected: No new errors.

**Step 4: Commit**

```bash
git add frontend/src/app/market-monitor/ frontend/src/components/layout/sidebar.tsx
git commit -m "feat(frontend): add /market-monitor page with heat map and theme tracker"
```

---

## Task 12: Backfill + Smoke Test

**Step 1: Deploy backend to Railway**

Push all backend changes. Verify `/api/market-monitor/compute` shows in Railway `/docs`.

**Step 2: Run universe refresh**

```bash
curl -X POST https://<railway-url>/api/market-monitor/refresh-universe
```

Verify: returns `total_symbols` > 1500 with sector breakdown.

**Step 3: Run backfill**

```bash
curl -X POST "https://<railway-url>/api/market-monitor/backfill?days=30"
```

Verify: returns `days_computed: 30` (or close).

**Step 4: Deploy frontend to Vercel**

Push frontend changes. Open `/market-monitor` and verify:
- Heat map grid renders with 30 columns of data
- Click a cell → side panel opens with ticker list
- Theme Tracker shows sector rankings
- Click a sector → side panel shows sector stocks
- Force Recompute button works

**Step 5: Commit any fixes**

```bash
git commit -m "fix(monitor): address smoke test issues"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Supabase tables | `alembic/versions/015_*` |
| 2 | Universe refresh endpoint | `api/endpoints/market_monitor.py`, `api/main.py` |
| 3 | Breadth + theme computation | `api/endpoints/market_monitor.py`, tests |
| 4 | All API endpoints | `api/endpoints/market_monitor.py`, tests |
| 5 | Vercel cron route | `frontend/src/app/api/cron/market-monitor/`, `vercel.json` |
| 6 | Frontend API proxies | `frontend/src/app/api/market-monitor/` (5 routes) |
| 7 | Types + hook | `frontend/src/lib/types.ts`, `frontend/src/hooks/use-market-monitor.ts` |
| 8 | Heat map grid | `frontend/src/components/market-monitor/breadth-heat-map.tsx` + cell |
| 9 | Drill-down panel | `frontend/src/components/market-monitor/drill-down-panel.tsx` |
| 10 | Theme tracker table | `frontend/src/components/market-monitor/theme-tracker-table.tsx` |
| 11 | Page + sidebar nav | `frontend/src/app/market-monitor/page.tsx`, sidebar |
| 12 | Backfill + smoke test | Deploy + verify |
