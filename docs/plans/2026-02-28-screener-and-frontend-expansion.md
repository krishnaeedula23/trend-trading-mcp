# Screener & Frontend Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up remaining Schwab bulk endpoints, build a server-side screener, add Cmd+K global search, build the `/screener` page, and add Lightweight Charts to `/analyze/[ticker]`.

**Architecture:** Backend-first (Schwab wrappers → screener orchestrator → frontend). The screener endpoint resolves a stock universe, runs Saty indicators in batch, grades with Green Flag, and returns ranked results. Frontend gets Cmd+K search via `cmdk`, a `/screener` page with TanStack Table, and a candlestick chart on the analyze page.

**Tech Stack:** Python 3.12, FastAPI, schwab-py 1.5.1+, pytest | Next.js 16, React 19, Tailwind 4, shadcn/ui, SWR, cmdk, @tanstack/react-table, lightweight-charts 5.1

---

## Task 1: Wire Schwab `get_movers` Wrapper

**Files:**
- Modify: `api/integrations/schwab/client.py:48-92`
- Modify: `api/endpoints/schwab.py`
- Create: `tests/api/test_schwab_client.py`

**Step 1: Write the failing test for `get_movers`**

```python
# tests/api/test_schwab_client.py
"""Tests for Schwab client convenience wrappers."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def mock_schwab_client():
    """Return a mocked schwab.client.Client."""
    client = MagicMock()
    with patch("api.integrations.schwab.client.get_client", return_value=client):
        yield client


class TestGetMovers:
    def test_returns_json_for_valid_index(self, mock_schwab_client):
        mock_schwab_client.get_movers.return_value = MagicMock(
            status_code=200,
            json=lambda: {"screener": [{"symbol": "AAPL", "totalVolume": 1_000_000}]},
        )
        mock_schwab_client.get_movers.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_movers

        result = get_movers("$SPX")
        assert result["screener"][0]["symbol"] == "AAPL"
        mock_schwab_client.get_movers.assert_called_once()

    def test_raises_on_bad_status(self, mock_schwab_client):
        from requests.exceptions import HTTPError

        mock_schwab_client.get_movers.return_value = MagicMock()
        mock_schwab_client.get_movers.return_value.raise_for_status.side_effect = HTTPError("502")

        from api.integrations.schwab.client import get_movers

        with pytest.raises(HTTPError):
            get_movers("$SPX")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_movers'`

**Step 3: Write minimal implementation**

Add to `api/integrations/schwab/client.py` after line 92:

```python
def get_movers(
    index: str = "$SPX",
    sort_order: str | None = None,
    frequency: int | None = None,
) -> dict[str, Any]:
    """Top movers for a market index (e.g. $SPX, $DJI, $COMPX)."""
    import schwab.client

    kwargs: dict[str, Any] = {}
    idx_map = {
        "$SPX": schwab.client.Client.Movers.Index.SPX,
        "$DJI": schwab.client.Client.Movers.Index.DJI,
        "$COMPX": schwab.client.Client.Movers.Index.COMPX,
        "$NYSE": schwab.client.Client.Movers.Index.NYSE,
        "$NASDAQ": schwab.client.Client.Movers.Index.NASDAQ,
    }
    idx = idx_map.get(index.upper(), schwab.client.Client.Movers.Index.SPX)

    if sort_order:
        order_map = {
            "volume": schwab.client.Client.Movers.SortOrder.VOLUME,
            "trades": schwab.client.Client.Movers.SortOrder.TRADES,
            "percent_change_up": schwab.client.Client.Movers.SortOrder.PERCENT_CHANGE_UP,
            "percent_change_down": schwab.client.Client.Movers.SortOrder.PERCENT_CHANGE_DOWN,
        }
        kwargs["sort_order"] = order_map.get(sort_order.lower())
    if frequency is not None:
        freq_map = {
            0: schwab.client.Client.Movers.Frequency.ZERO,
            1: schwab.client.Client.Movers.Frequency.ONE,
            5: schwab.client.Client.Movers.Frequency.FIVE,
            10: schwab.client.Client.Movers.Frequency.TEN,
            30: schwab.client.Client.Movers.Frequency.THIRTY,
            60: schwab.client.Client.Movers.Frequency.SIXTY,
        }
        kwargs["frequency"] = freq_map.get(frequency)

    resp = get_client().get_movers(idx, **kwargs)
    resp.raise_for_status()
    return resp.json()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py::TestGetMovers -v`
Expected: 2 passed

**Step 5: Add the endpoint**

Add to `api/endpoints/schwab.py` after the `/price-history` endpoint:

```python
@router.get("/movers")
async def get_movers(
    index: str = Query("$SPX", description="Market index: $SPX, $DJI, $COMPX, $NYSE, $NASDAQ"),
    sort_order: str | None = Query(None, description="volume | trades | percent_change_up | percent_change_down"),
    frequency: int | None = Query(None, description="Change threshold: 0, 1, 5, 10, 30, 60"),
):
    """Return top movers for a market index."""
    _require_token()
    try:
        return schwab_client.get_movers(index, sort_order=sort_order, frequency=frequency)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc
```

**Step 6: Commit**

```bash
git add api/integrations/schwab/client.py api/endpoints/schwab.py tests/api/test_schwab_client.py
git commit -m "feat: add Schwab get_movers wrapper and /api/schwab/movers endpoint"
```

---

## Task 2: Wire Schwab `get_quotes` Wrapper

**Files:**
- Modify: `api/integrations/schwab/client.py`
- Modify: `api/endpoints/schwab.py`
- Modify: `tests/api/test_schwab_client.py`

**Step 1: Write the failing test**

Add to `tests/api/test_schwab_client.py`:

```python
class TestGetQuotes:
    def test_returns_quotes_for_multiple_symbols(self, mock_schwab_client):
        mock_schwab_client.get_quotes.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "AAPL": {"quote": {"lastPrice": 195.0}},
                "MSFT": {"quote": {"lastPrice": 420.0}},
            },
        )
        mock_schwab_client.get_quotes.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_quotes

        result = get_quotes(["AAPL", "MSFT"])
        assert "AAPL" in result
        assert "MSFT" in result
        mock_schwab_client.get_quotes.assert_called_once()

    def test_single_symbol_as_string(self, mock_schwab_client):
        mock_schwab_client.get_quotes.return_value = MagicMock(
            status_code=200,
            json=lambda: {"SPY": {"quote": {"lastPrice": 500.0}}},
        )
        mock_schwab_client.get_quotes.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_quotes

        result = get_quotes(["SPY"])
        assert "SPY" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py::TestGetQuotes -v`
Expected: FAIL — `ImportError: cannot import name 'get_quotes'`

**Step 3: Write minimal implementation**

Add to `api/integrations/schwab/client.py`:

```python
def get_quotes(symbols: list[str]) -> dict[str, Any]:
    """Batch quotes for multiple symbols."""
    resp = get_client().get_quotes([s.upper() for s in symbols])
    resp.raise_for_status()
    return resp.json()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py::TestGetQuotes -v`
Expected: 2 passed

**Step 5: Add the endpoint**

Add to `api/endpoints/schwab.py`:

```python
from fastapi import Body

@router.post("/quotes")
async def get_quotes(
    symbols: list[str] = Body(..., description="List of ticker symbols", max_length=50),
):
    """Return batch quotes for up to 50 symbols."""
    _require_token()
    try:
        return schwab_client.get_quotes(symbols)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc
```

**Step 6: Commit**

```bash
git add api/integrations/schwab/client.py api/endpoints/schwab.py tests/api/test_schwab_client.py
git commit -m "feat: add Schwab get_quotes bulk wrapper and /api/schwab/quotes endpoint"
```

---

## Task 3: Wire Schwab `get_instruments` Wrapper

**Files:**
- Modify: `api/integrations/schwab/client.py`
- Modify: `api/endpoints/schwab.py`
- Modify: `tests/api/test_schwab_client.py`

**Step 1: Write the failing test**

Add to `tests/api/test_schwab_client.py`:

```python
class TestGetInstruments:
    def test_symbol_search(self, mock_schwab_client):
        mock_schwab_client.get_instruments.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "instruments": [
                    {"symbol": "AAPL", "description": "Apple Inc", "exchange": "NASDAQ"},
                ]
            },
        )
        mock_schwab_client.get_instruments.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_instruments

        result = get_instruments("AAPL", projection="symbol_search")
        assert result["instruments"][0]["symbol"] == "AAPL"

    def test_description_search(self, mock_schwab_client):
        mock_schwab_client.get_instruments.return_value = MagicMock(
            status_code=200,
            json=lambda: {"instruments": [{"symbol": "AAPL", "description": "Apple Inc"}]},
        )
        mock_schwab_client.get_instruments.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_instruments

        result = get_instruments("Apple", projection="description_search")
        assert len(result["instruments"]) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py::TestGetInstruments -v`
Expected: FAIL — `ImportError: cannot import name 'get_instruments'`

**Step 3: Write minimal implementation**

Add to `api/integrations/schwab/client.py`:

```python
def get_instruments(query: str, projection: str = "symbol_search") -> dict[str, Any]:
    """Search for instruments by symbol or description."""
    import schwab.client

    proj_map = {
        "symbol_search": schwab.client.Client.Instrument.Projection.SYMBOL_SEARCH,
        "symbol_regex": schwab.client.Client.Instrument.Projection.SYMBOL_REGEX,
        "description_search": schwab.client.Client.Instrument.Projection.DESCRIPTION_SEARCH,
        "description_regex": schwab.client.Client.Instrument.Projection.DESCRIPTION_REGEX,
        "search": schwab.client.Client.Instrument.Projection.SEARCH,
        "fundamental": schwab.client.Client.Instrument.Projection.FUNDAMENTAL,
    }
    proj = proj_map.get(projection.lower(), schwab.client.Client.Instrument.Projection.SYMBOL_SEARCH)
    resp = get_client().get_instruments(query, proj)
    resp.raise_for_status()
    return resp.json()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py::TestGetInstruments -v`
Expected: 2 passed

**Step 5: Add the endpoint**

Add to `api/endpoints/schwab.py`:

```python
@router.get("/instruments")
async def get_instruments(
    query: str = Query(..., description="Search term (symbol or description text)"),
    projection: str = Query("symbol_search", description="symbol_search | description_search | fundamental"),
):
    """Search for instruments by symbol or description."""
    _require_token()
    try:
        return schwab_client.get_instruments(query, projection=projection)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc
```

**Step 6: Run all Schwab tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_schwab_client.py -v`
Expected: 6 passed (all 3 test classes)

**Step 7: Commit**

```bash
git add api/integrations/schwab/client.py api/endpoints/schwab.py tests/api/test_schwab_client.py
git commit -m "feat: add Schwab get_instruments wrapper and /api/schwab/instruments endpoint"
```

---

## Task 4: Build Screener Backend Orchestrator

**Files:**
- Create: `api/endpoints/screener.py`
- Create: `tests/api/test_screener.py`
- Modify: `api/main.py` (register router)

**Step 1: Write the failing test**

```python
# tests/api/test_screener.py
"""Tests for the screener orchestrator endpoint."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """FastAPI test client with mocked Schwab dependency."""
    from api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_schwab_token():
    """Skip the token check for all screener tests."""
    with patch("api.endpoints.schwab.token_exists", return_value=True):
        yield


class TestScreenerScan:
    def test_returns_ranked_results(self, client):
        """Screener should accept tickers, run indicators, and return graded results."""
        mock_trade_plan = {
            "ticker": "AAPL",
            "atr_levels": {"atr": 3.5, "pdc": 190.0, "current_price": 195.0,
                           "atr_status": "green", "atr_covered_pct": 0.3, "atr_room_ok": True,
                           "trend": "up", "chopzilla": False, "trading_mode": "trending",
                           "call_trigger": 193.5, "put_trigger": 186.5,
                           "trigger_box": {"low": 186.5, "high": 193.5, "inside": False},
                           "levels": {}},
            "pivot_ribbon": {"ribbon_state": "bullish", "bias_candle": "blue",
                             "in_compression": False, "above_200ema": True,
                             "ema8": 194, "ema13": 193, "ema21": 192, "ema48": 190, "ema200": 180,
                             "spread": 0.02, "chopzilla": False,
                             "bias_signal": "pullback", "conviction_arrow": "none",
                             "last_conviction_type": "none", "last_conviction_bars_ago": None,
                             "above_48ema": True},
            "phase_oscillator": {"oscillator": 65, "phase": "green",
                                  "in_compression": False, "current_zone": "momentum",
                                  "oscillator_prev": 60,
                                  "zone_crosses": {}, "zones": {},
                                  "last_mr_type": None, "last_mr_bars_ago": None},
            "green_flag": {"grade": "A+", "score": 7, "max_score": 10,
                           "direction": "bullish", "recommendation": "Strong trade",
                           "flags": {}, "verbal_audit": "All flags met"},
            "direction": "bullish",
            "price_structure": {"pdh": 196, "pdl": 189, "pmh": 200, "pml": 185},
        }

        with patch("api.endpoints.screener.calculate_trade_plan", return_value=mock_trade_plan):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["AAPL"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["ticker"] == "AAPL"
        assert data["results"][0]["grade"] == "A+"

    def test_empty_tickers_returns_400(self, client):
        resp = client.post("/api/screener/scan", json={
            "tickers": [],
            "timeframe": "1d",
            "direction": "bullish",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_results_sorted_by_grade_then_score(self, client):
        """A+ should come before A, A before B."""
        results = [
            {"ticker": "B_STOCK", "grade": "B", "score": 3},
            {"ticker": "A_PLUS", "grade": "A+", "score": 7},
            {"ticker": "A_STOCK", "grade": "A", "score": 4},
        ]

        with patch("api.endpoints.screener.calculate_trade_plan") as mock_calc:
            mock_calc.side_effect = [
                {**_base_plan(), "ticker": "B_STOCK",
                 "green_flag": {"grade": "B", "score": 3, "max_score": 10,
                                "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
                {**_base_plan(), "ticker": "A_PLUS",
                 "green_flag": {"grade": "A+", "score": 7, "max_score": 10,
                                "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
                {**_base_plan(), "ticker": "A_STOCK",
                 "green_flag": {"grade": "A", "score": 4, "max_score": 10,
                                "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
            ]
            resp = client.post("/api/screener/scan", json={
                "tickers": ["B_STOCK", "A_PLUS", "A_STOCK"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        data = resp.json()
        grades = [r["grade"] for r in data["results"]]
        assert grades == ["A+", "A", "B"]


def _base_plan() -> dict:
    """Minimal trade plan dict for test mocking."""
    return {
        "atr_levels": {"atr": 3, "pdc": 100, "current_price": 103,
                        "atr_status": "green", "atr_covered_pct": 0.3, "atr_room_ok": True,
                        "trend": "up", "chopzilla": False, "trading_mode": "trending",
                        "call_trigger": 101, "put_trigger": 97,
                        "trigger_box": {"low": 97, "high": 101, "inside": False}, "levels": {}},
        "pivot_ribbon": {"ribbon_state": "bullish", "bias_candle": "green",
                         "in_compression": False, "above_200ema": True,
                         "ema8": 102, "ema13": 101, "ema21": 100, "ema48": 98, "ema200": 90,
                         "spread": 0.02, "chopzilla": False,
                         "bias_signal": "pullback", "conviction_arrow": "none",
                         "last_conviction_type": "none", "last_conviction_bars_ago": None,
                         "above_48ema": True},
        "phase_oscillator": {"oscillator": 50, "phase": "green", "in_compression": False,
                              "current_zone": "momentum", "oscillator_prev": 45,
                              "zone_crosses": {}, "zones": {},
                              "last_mr_type": None, "last_mr_bars_ago": None},
        "direction": "bullish",
        "price_structure": {"pdh": 105, "pdl": 98, "pmh": 108, "pml": 95},
    }
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_screener.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.endpoints.screener'`

**Step 3: Write the screener endpoint**

```python
# api/endpoints/screener.py
"""Screener orchestrator — batch Saty analysis with grade ranking."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.green_flag import green_flag
from api.indicators.satyland.price_structure import price_structure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "skip": 3}


class ScanRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=100)
    timeframe: str = Field(default="1d")
    direction: str = Field(default="bullish")


class ScanResultItem(BaseModel):
    ticker: str
    grade: str
    score: int
    atr_levels: dict[str, Any]
    pivot_ribbon: dict[str, Any]
    phase_oscillator: dict[str, Any]
    green_flag: dict[str, Any]
    price_structure: dict[str, Any]
    error: str | None = None


class ScanResponse(BaseModel):
    results: list[ScanResultItem]
    total: int
    scanned: int
    errors: int


def calculate_trade_plan(ticker: str, timeframe: str, direction: str) -> dict[str, Any]:
    """Run the full Saty indicator stack for a single ticker.

    This mirrors the logic in api/endpoints/satyland.py trade_plan endpoint
    but is importable for batch use.
    """
    import yfinance as yf

    period_map = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
                  "1h": "730d", "4h": "730d", "1d": "2y", "1w": "10y"}
    period = period_map.get(timeframe, "2y")
    interval = timeframe if timeframe != "4h" else "1h"

    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        raise ValueError(f"No data for {ticker} at {timeframe}")

    # Flatten multi-index if present
    if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)

    atr_result = atr_levels(df)
    ribbon_result = pivot_ribbon(df)
    phase_result = phase_oscillator(df)
    structure_result = price_structure(df)
    flag_result = green_flag(
        atr=atr_result,
        ribbon=ribbon_result,
        phase=phase_result,
        structure=structure_result,
        direction=direction,
    )

    return {
        "ticker": ticker,
        "atr_levels": atr_result,
        "pivot_ribbon": ribbon_result,
        "phase_oscillator": phase_result,
        "price_structure": structure_result,
        "green_flag": flag_result,
        "direction": direction,
    }


@router.post("/scan")
async def scan(request: ScanRequest) -> ScanResponse:
    """Scan tickers through the Saty indicator stack and return graded results."""
    results: list[ScanResultItem] = []
    errors = 0

    for ticker in request.tickers:
        try:
            plan = calculate_trade_plan(ticker, request.timeframe, request.direction)
            results.append(ScanResultItem(
                ticker=ticker.upper(),
                grade=plan["green_flag"]["grade"],
                score=plan["green_flag"]["score"],
                atr_levels=plan["atr_levels"],
                pivot_ribbon=plan["pivot_ribbon"],
                phase_oscillator=plan["phase_oscillator"],
                green_flag=plan["green_flag"],
                price_structure=plan["price_structure"],
            ))
        except Exception as exc:
            logger.warning("Screener failed for %s: %s", ticker, exc)
            errors += 1
            results.append(ScanResultItem(
                ticker=ticker.upper(),
                grade="skip",
                score=0,
                atr_levels={},
                pivot_ribbon={},
                phase_oscillator={},
                green_flag={},
                price_structure={},
                error=str(exc),
            ))

    # Sort: A+ first, then A, then B, then skip. Within same grade, higher score first.
    results.sort(key=lambda r: (GRADE_ORDER.get(r.grade, 99), -r.score))

    return ScanResponse(
        results=results,
        total=len(request.tickers),
        scanned=len(request.tickers) - errors,
        errors=errors,
    )
```

**Step 4: Register the router in `api/main.py`**

Find the section where routers are included and add:

```python
from api.endpoints.screener import router as screener_router
app.include_router(screener_router)
```

**Step 5: Run tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/api/test_screener.py -v`
Expected: 3 passed

**Step 6: Verify existing Saty tests still pass**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/satyland/ -v`
Expected: 115 passed

**Step 7: Commit**

```bash
git add api/endpoints/screener.py tests/api/test_screener.py api/main.py
git commit -m "feat: add POST /api/screener/scan orchestrator endpoint with grade ranking"
```

---

## Task 5: Install Frontend Dependencies (cmdk + tanstack-table)

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install cmdk and tanstack-table**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm install cmdk @tanstack/react-table`

**Step 2: Verify install**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm ls cmdk @tanstack/react-table`
Expected: Both packages listed with versions

**Step 3: Commit**

```bash
cd /Users/krishnaeedula/claude/trend-trading-mcp
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add cmdk and @tanstack/react-table dependencies"
```

---

## Task 6: Add shadcn Command Component for Cmd+K

**Files:**
- Create: `frontend/src/components/ui/command.tsx` (shadcn)
- Create: `frontend/src/components/global-search.tsx`
- Modify: `frontend/src/components/layout/header.tsx`

**Step 1: Add the shadcn command component**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npx shadcn@latest add command`

This installs the shadcn `Command` component (wraps `cmdk`).

**Step 2: Create global search component**

```tsx
// frontend/src/components/global-search.tsx
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOG", "AMD"]

export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const router = useRouter()

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  function navigate(ticker: string) {
    setOpen(false)
    setQuery("")
    router.push(`/analyze/${ticker.toUpperCase()}`)
  }

  const filtered = query.length > 0
    ? POPULAR_TICKERS.filter((t) => t.toLowerCase().startsWith(query.toLowerCase()))
    : POPULAR_TICKERS

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search ticker... (e.g. AAPL)"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {query.length > 0 && (
            <button
              className="w-full text-left px-2 py-1.5 text-sm"
              onClick={() => navigate(query)}
            >
              Analyze <span className="font-semibold">{query.toUpperCase()}</span>
            </button>
          )}
        </CommandEmpty>
        <CommandGroup heading="Popular">
          {filtered.map((ticker) => (
            <CommandItem key={ticker} value={ticker} onSelect={() => navigate(ticker)}>
              {ticker}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
```

**Step 3: Wire into layout header**

In `frontend/src/components/layout/header.tsx`, add the search trigger:

1. Import `GlobalSearch` at top
2. Add `<GlobalSearch />` inside the header
3. Add a visible search button/hint: `⌘K` badge

**Step 4: Verify it renders**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`
Expected: Build succeeds without errors

**Step 5: Commit**

```bash
cd /Users/krishnaeedula/claude/trend-trading-mcp
git add frontend/src/components/ui/command.tsx frontend/src/components/global-search.tsx frontend/src/components/layout/header.tsx
git commit -m "feat: add Cmd+K global ticker search with shadcn command palette"
```

---

## Task 7: Build `/screener` Frontend Page

**Files:**
- Create: `frontend/src/app/screener/page.tsx`
- Create: `frontend/src/hooks/use-screener.ts`
- Create: `frontend/src/components/screener/screener-filters.tsx`
- Create: `frontend/src/components/screener/screener-table.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx` (add nav link)
- Modify: `frontend/src/lib/types.ts` (add screener types)
- Modify: `frontend/src/lib/railway.ts` (add screener API function)

**Step 1: Add screener types**

Add to `frontend/src/lib/types.ts`:

```typescript
// Screener
export interface ScreenerScanRequest {
  tickers: string[]
  timeframe: string
  direction: Direction
}

export interface ScreenerResultItem {
  ticker: string
  grade: Grade
  score: number
  atr_levels: Partial<AtrLevels>
  pivot_ribbon: Partial<PivotRibbon>
  phase_oscillator: Partial<PhaseOscillator>
  green_flag: Partial<GreenFlag>
  price_structure: Partial<PriceStructure>
  error?: string
}

export interface ScreenerScanResponse {
  results: ScreenerResultItem[]
  total: number
  scanned: number
  errors: number
}
```

**Step 2: Add screener API function**

Add to `frontend/src/lib/railway.ts`:

```typescript
export async function runScreenerScan(
  tickers: string[],
  timeframe: string = "1d",
  direction: string = "bullish",
): Promise<ScreenerScanResponse> {
  const resp = await railwayFetch("/api/screener/scan", { tickers, timeframe, direction })
  return resp.json()
}
```

**Step 3: Create the screener hook**

```typescript
// frontend/src/hooks/use-screener.ts
"use client"

import { useState } from "react"
import type { ScreenerScanResponse, Direction } from "@/lib/types"
import { runScreenerScan } from "@/lib/railway"

export function useScreener() {
  const [results, setResults] = useState<ScreenerScanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function scan(tickers: string[], timeframe: string, direction: Direction) {
    setLoading(true)
    setError(null)
    try {
      const data = await runScreenerScan(tickers, timeframe, direction)
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed")
    } finally {
      setLoading(false)
    }
  }

  return { results, loading, error, scan }
}
```

**Step 4: Create screener filters component**

```tsx
// frontend/src/components/screener/screener-filters.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Watchlist, Direction } from "@/lib/types"

interface ScreenerFiltersProps {
  watchlists: Watchlist[]
  loading: boolean
  onScan: (tickers: string[], timeframe: string, direction: Direction) => void
}

export function ScreenerFilters({ watchlists, loading, onScan }: ScreenerFiltersProps) {
  const [selectedWatchlist, setSelectedWatchlist] = useState<string>("all")
  const [timeframe, setTimeframe] = useState("1d")
  const [direction, setDirection] = useState<Direction>("bullish")

  function handleScan() {
    let tickers: string[]
    if (selectedWatchlist === "all") {
      tickers = watchlists.flatMap((w) => w.tickers)
      tickers = [...new Set(tickers)] // dedupe
    } else {
      const wl = watchlists.find((w) => w.id === selectedWatchlist)
      tickers = wl?.tickers ?? []
    }
    if (tickers.length === 0) return
    onScan(tickers, timeframe, direction)
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <Select value={selectedWatchlist} onValueChange={setSelectedWatchlist}>
        <SelectTrigger className="w-48">
          <SelectValue placeholder="Select watchlist" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Watchlists</SelectItem>
          {watchlists.map((w) => (
            <SelectItem key={w.id} value={w.id}>{w.name} ({w.tickers.length})</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={timeframe} onValueChange={setTimeframe}>
        <SelectTrigger className="w-24">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {["5m", "15m", "1h", "1d", "1w"].map((tf) => (
            <SelectItem key={tf} value={tf}>{tf}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={direction} onValueChange={(v) => setDirection(v as Direction)}>
        <SelectTrigger className="w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="bullish">Bullish</SelectItem>
          <SelectItem value="bearish">Bearish</SelectItem>
        </SelectContent>
      </Select>

      <Button onClick={handleScan} disabled={loading}>
        {loading ? "Scanning..." : "Scan"}
      </Button>
    </div>
  )
}
```

**Step 5: Create screener results table with TanStack Table**

```tsx
// frontend/src/components/screener/screener-table.tsx
"use client"

import { useMemo } from "react"
import Link from "next/link"
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import { useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { GradeBadge } from "@/components/ideas/grade-badge"
import type { ScreenerResultItem } from "@/lib/types"

interface ScreenerTableProps {
  results: ScreenerResultItem[]
  timeframe: string
  direction: string
}

export function ScreenerTable({ results, timeframe, direction }: ScreenerTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "grade", desc: false }])

  const columns = useMemo<ColumnDef<ScreenerResultItem>[]>(
    () => [
      {
        accessorKey: "ticker",
        header: "Ticker",
        cell: ({ row }) => (
          <Link
            href={`/analyze/${row.original.ticker}?tf=${timeframe}&dir=${direction}`}
            className="font-medium text-blue-600 hover:underline"
          >
            {row.original.ticker}
          </Link>
        ),
      },
      {
        accessorKey: "grade",
        header: "Grade",
        cell: ({ row }) => <GradeBadge grade={row.original.grade} />,
        sortingFn: (a, b) => {
          const order = { "A+": 0, A: 1, B: 2, skip: 3 }
          return (order[a.original.grade as keyof typeof order] ?? 99)
            - (order[b.original.grade as keyof typeof order] ?? 99)
        },
      },
      {
        accessorKey: "score",
        header: "Score",
        cell: ({ row }) => `${row.original.score}/10`,
      },
      {
        id: "bias",
        header: "Bias",
        cell: ({ row }) => {
          const bias = row.original.pivot_ribbon?.bias_candle
          if (!bias) return "—"
          const colors: Record<string, string> = {
            green: "bg-green-500", blue: "bg-blue-500",
            orange: "bg-orange-500", red: "bg-red-500", gray: "bg-gray-400",
          }
          return (
            <span className="flex items-center gap-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${colors[bias] ?? "bg-gray-400"}`} />
              {bias}
            </span>
          )
        },
      },
      {
        id: "phase",
        header: "Phase",
        cell: ({ row }) => {
          const phase = row.original.phase_oscillator?.phase
          return phase?.toUpperCase() ?? "—"
        },
      },
      {
        id: "ribbon",
        header: "Ribbon",
        cell: ({ row }) => row.original.pivot_ribbon?.ribbon_state ?? "—",
      },
      {
        id: "atr_status",
        header: "ATR",
        cell: ({ row }) => row.original.atr_levels?.atr_status ?? "—",
      },
    ],
    [timeframe, direction],
  )

  const table = useReactTable({
    data: results,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className="cursor-pointer select-none"
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {{ asc: " ↑", desc: " ↓" }[header.column.getIsSorted() as string] ?? ""}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-8 text-muted-foreground">
                No results. Run a scan to see screener results.
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}
```

**Step 6: Create the screener page**

```tsx
// frontend/src/app/screener/page.tsx
"use client"

import { useWatchlists } from "@/hooks/use-watchlists"
import { useScreener } from "@/hooks/use-screener"
import { ScreenerFilters } from "@/components/screener/screener-filters"
import { ScreenerTable } from "@/components/screener/screener-table"
import type { Direction } from "@/lib/types"
import { useState } from "react"

export default function ScreenerPage() {
  const { watchlists, isLoading: wlLoading } = useWatchlists()
  const { results, loading, error, scan } = useScreener()
  const [config, setConfig] = useState({ timeframe: "1d", direction: "bullish" })

  function handleScan(tickers: string[], timeframe: string, direction: Direction) {
    setConfig({ timeframe, direction })
    scan(tickers, timeframe, direction)
  }

  if (wlLoading) {
    return <div className="p-6">Loading watchlists...</div>
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Screener</h1>
        <p className="text-muted-foreground">
          Scan watchlists through the Saty indicator stack
        </p>
      </div>

      <ScreenerFilters
        watchlists={watchlists ?? []}
        loading={loading}
        onScan={handleScan}
      />

      {error && (
        <div className="text-red-500 text-sm">{error}</div>
      )}

      {results && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            {results.scanned} scanned, {results.errors} errors
          </p>
          <ScreenerTable
            results={results.results.filter((r) => !r.error)}
            timeframe={config.timeframe}
            direction={config.direction}
          />
        </div>
      )}
    </div>
  )
}
```

**Step 7: Add nav link in sidebar**

In `frontend/src/components/layout/sidebar.tsx`, add a "Screener" nav item pointing to `/screener` alongside the existing `/scan` link.

**Step 8: Verify build**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`
Expected: Build succeeds

**Step 9: Commit**

```bash
cd /Users/krishnaeedula/claude/trend-trading-mcp
git add frontend/src/app/screener/ frontend/src/hooks/use-screener.ts frontend/src/components/screener/ frontend/src/lib/types.ts frontend/src/lib/railway.ts frontend/src/components/layout/sidebar.tsx
git commit -m "feat: add /screener page with server-side scan, TanStack Table, and grade ranking"
```

---

## Task 8: Add Lightweight Charts to `/analyze/[ticker]`

**Files:**
- Create: `frontend/src/components/charts/price-chart.tsx`
- Modify: `frontend/src/app/analyze/[ticker]/page.tsx`
- Modify: `frontend/src/lib/railway.ts` (add price history fetcher)
- Create: `frontend/src/hooks/use-price-history.ts`

**Step 1: Add price history API function**

Add to `frontend/src/lib/railway.ts`:

```typescript
export async function getPriceHistory(
  ticker: string,
  frequency: string = "1d",
): Promise<Record<string, unknown>> {
  const url = `${getBaseUrl()}/api/schwab/price-history?ticker=${encodeURIComponent(ticker)}&frequency=${encodeURIComponent(frequency)}`
  const resp = await fetch(url)
  if (!resp.ok) throw new RailwayError(resp.status, `Price history fetch failed: ${resp.statusText}`)
  return resp.json()
}
```

**Step 2: Create price history hook**

```typescript
// frontend/src/hooks/use-price-history.ts
"use client"

import useSWR from "swr"
import { getPriceHistory } from "@/lib/railway"

export function usePriceHistory(ticker: string | null, frequency: string = "1d") {
  const { data, error, isLoading } = useSWR(
    ticker ? ["price-history", ticker, frequency] : null,
    () => getPriceHistory(ticker!, frequency),
    { refreshInterval: 60_000 },
  )
  return { data, error, isLoading }
}
```

**Step 3: Create the price chart component**

```tsx
// frontend/src/components/charts/price-chart.tsx
"use client"

import { useEffect, useRef } from "react"
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts"

interface Candle {
  time: string  // YYYY-MM-DD or epoch
  open: number
  high: number
  low: number
  close: number
}

interface LevelLine {
  price: number
  color: string
  label: string
  style?: number  // 0=solid, 1=dotted, 2=dashed
}

interface PriceChartProps {
  candles: Candle[]
  levels?: LevelLine[]
  height?: number
}

export function PriceChart({ candles, levels = [], height = 400 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: { borderColor: "#374151" },
    })

    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    })

    series.setData(candles)

    // Add ATR level lines as price lines
    for (const level of levels) {
      series.createPriceLine({
        price: level.price,
        color: level.color,
        lineWidth: 1,
        lineStyle: level.style ?? 2,
        axisLabelVisible: true,
        title: level.label,
      })
    }

    chart.timeScale().fitContent()
    chartRef.current = chart
    seriesRef.current = series

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [candles, levels, height])

  return <div ref={containerRef} className="w-full rounded-lg border" />
}
```

**Step 4: Wire into the analyze page**

In `frontend/src/app/analyze/[ticker]/page.tsx`:

1. Import `PriceChart` and `usePriceHistory`
2. Call `usePriceHistory(ticker, timeframe)` to fetch OHLCV data
3. Transform Schwab candles to `{time, open, high, low, close}` format
4. Build `levels` array from `atr_levels` (call_trigger, put_trigger, pdc, key fib levels)
5. Render `<PriceChart candles={candles} levels={levels} />` above or alongside the indicator panel

Key level lines to show:
- PDC (previous day close) — white, solid
- Call Trigger — green, dashed
- Put Trigger — red, dashed
- Golden Gate Bull — teal, dotted (if present in `atr_levels.levels`)
- Golden Gate Bear — orange, dotted (if present)

**Step 5: Verify build**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
cd /Users/krishnaeedula/claude/trend-trading-mcp
git add frontend/src/components/charts/price-chart.tsx frontend/src/hooks/use-price-history.ts frontend/src/app/analyze/\[ticker\]/page.tsx frontend/src/lib/railway.ts
git commit -m "feat: add Lightweight Charts candlestick with ATR level overlays on /analyze page"
```

---

## Task 9: Final Verification

**Step 1: Run all backend tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && venv/bin/pytest tests/satyland/ tests/api/ -v`
Expected: All tests pass (115 Saty + 6+ Schwab + 3+ screener)

**Step 2: Run frontend build**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`
Expected: Clean build

**Step 3: Run frontend tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm test`
Expected: All Vitest tests pass (65+)

**Step 4: Update conductor plan.md**

Mark completed tasks in `conductor/tracks/project-audit-modernization_20260205/plan.md`:
- [x] Task 4.1 (Schwab wrappers)
- [x] Task 4.2 (Screener endpoint)
- [x] Task 4.3 (shadcn components — command added)
- [x] Task 4.4 (/screener page)

**Step 5: Commit docs update**

```bash
cd /Users/krishnaeedula/claude/trend-trading-mcp
git add conductor/
git commit -m "docs: update plan.md — mark Phase 4 tasks 4.1-4.4 complete"
```
