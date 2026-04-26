# Plan 1 — Foundation: Schema + Indicator Overlay + Coiled Spring + Universe Overrides + API + Claude Skill

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of the unified morning screener — Supabase tables, indicator overlay (ATR%, %from50MA, Extension B/A), one end-to-end scan (Coiled Spring with multi-condition compression + days-in-coil tracking), Claude-skill-driven universe overrides, and a working `POST /api/screener/morning/run` that returns scan results.

**Architecture:** New `api/indicators/screener/` module mirrors the existing `api/indicators/swing/` pattern. Reuses the swing universe resolver as the base universe (so we don't rebuild CSV import); layers a new `universe_overrides` service on top. A scan registry pattern lets later plans add scans without touching the runner. Persistence via Supabase (matching swing precedent), not SQLAlchemy. Claude Code skill at `.claude/skills/screener-universe-edit.md` provides the `/screener-universe-*` commands.

**Tech Stack:** Python 3.12, FastAPI, Supabase Python client, yfinance, pandas, TA-Lib, pytest. No frontend in this plan (Plan 3 builds the UI).

**Reference:** Spec at [docs/superpowers/specs/2026-04-25-unified-screener-design.md](../specs/2026-04-25-unified-screener-design.md). Reuses swing universe resolver at [api/indicators/swing/universe/resolver.py](../../../api/indicators/swing/universe/resolver.py).

---

## File Structure (created/modified by this plan)

**Backend — new:**
- `docs/schema/019_add_screener_tables.sql` — Supabase migration (3 tables)
- `api/indicators/screener/__init__.py`
- `api/indicators/screener/overlay.py` — ATR%, %from50MA, Extension B/A
- `api/indicators/screener/registry.py` — scan registry pattern
- `api/indicators/screener/runner.py` — orchestration (universe → bars → indicators → scans → persist)
- `api/indicators/screener/scans/__init__.py`
- `api/indicators/screener/scans/coiled.py` — Coiled Spring scan
- `api/indicators/screener/universe_override.py` — Supabase CRUD for overrides + apply on top of resolved universe
- `api/indicators/screener/persistence.py` — `screener_runs` + `coiled_watchlist` Supabase CRUD
- `api/schemas/screener.py` — Pydantic request/response models
- `api/endpoints/screener_morning.py` — `/api/screener/morning/*` and `/api/screener/universe/*` routes
- `.claude/skills/screener-universe-edit.md` — Claude Code skill for manual universe edits

**Backend — modified:**
- `api/main.py` — register the new router

**Backend — tests:**
- `tests/screener/__init__.py`
- `tests/screener/conftest.py` — shared synthetic-bars and mock-supabase fixtures
- `tests/screener/test_overlay.py`
- `tests/screener/test_universe_override.py`
- `tests/screener/test_registry.py`
- `tests/screener/test_coiled.py`
- `tests/screener/test_persistence.py`
- `tests/screener/test_runner.py`
- `tests/screener/test_endpoints.py`

---

## Task 1: Supabase migration — 3 new tables

**Files:**
- Create: `docs/schema/019_add_screener_tables.sql`

- [ ] **Step 1: Write the migration SQL**

Following the pattern of `docs/schema/016_add_swing_tables.sql`:

```sql
-- 019_add_screener_tables.sql
-- Tables for the unified morning screener (Plan 1).

create table if not exists screener_runs (
  id uuid primary key default gen_random_uuid(),
  ran_at timestamptz not null default now(),
  mode text not null check (mode in ('swing', 'position')),
  universe_size int not null,
  scan_count int not null,
  hit_count int not null,
  duration_seconds numeric not null,
  results jsonb not null,
  error text
);

create index if not exists idx_screener_runs_ran_at on screener_runs (ran_at desc);
create index if not exists idx_screener_runs_mode_ran_at on screener_runs (mode, ran_at desc);

create table if not exists coiled_watchlist (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  mode text not null check (mode in ('swing', 'position')),
  first_detected_at date not null,
  last_seen_at date not null,
  days_in_compression int not null,
  status text not null check (status in ('active', 'fired', 'broken')),
  fired_at date,
  graduated_to_trigger jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ticker, mode, first_detected_at)
);

create index if not exists idx_coiled_watchlist_active
  on coiled_watchlist (mode, status, days_in_compression desc)
  where status = 'active';

create table if not exists universe_overrides (
  id uuid primary key default gen_random_uuid(),
  mode text not null check (mode in ('swing', 'position')),
  ticker text not null,
  action text not null check (action in ('add', 'remove')),
  source text not null default 'claude_skill',
  created_at timestamptz not null default now(),
  unique (mode, ticker, action)
);

create index if not exists idx_universe_overrides_mode on universe_overrides (mode);
```

- [ ] **Step 2: Apply migration to Supabase**

Run via Supabase SQL editor, or:

```bash
psql "$SUPABASE_DB_URL" -f docs/schema/019_add_screener_tables.sql
```

Expected: three `CREATE TABLE` statements succeed. Verify in Supabase dashboard that `screener_runs`, `coiled_watchlist`, and `universe_overrides` appear.

- [ ] **Step 3: Commit**

```bash
git add docs/schema/019_add_screener_tables.sql
git commit -m "feat(screener): add screener_runs, coiled_watchlist, universe_overrides tables"
```

---

## Task 2: Pydantic schemas

**Files:**
- Create: `api/schemas/screener.py`

- [ ] **Step 1: Write the schemas**

```python
# api/schemas/screener.py
"""Pydantic schemas for the unified morning screener API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


Mode = Literal["swing", "position"]
Lane = Literal["breakout", "transition", "reversion"]
Role = Literal["universe", "coiled", "setup_ready", "trigger"]


class IndicatorOverlay(BaseModel):
    """Per-ticker indicator stack computed once per run."""
    atr_pct: float = Field(..., description="ATR(14) / close")
    pct_from_50ma: float = Field(..., description="(close - SMA50) / SMA50")
    extension: float = Field(..., description="jfsrev formula: B/A")
    sma_50: float
    atr_14: float


class ScanHit(BaseModel):
    """A single (ticker, scan_id) pairing emitted by a scan."""
    ticker: str
    scan_id: str
    lane: Lane
    role: Role
    evidence: dict = Field(default_factory=dict)


class ScreenerRunRequest(BaseModel):
    mode: Mode = "swing"
    scan_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of scans to run; if None, runs all registered scans for the mode.",
    )


class TickerResult(BaseModel):
    ticker: str
    last_close: float
    overlay: IndicatorOverlay
    scans_hit: list[str]
    confluence: int


class ScreenerRunResponse(BaseModel):
    run_id: str
    mode: Mode
    ran_at: datetime
    universe_size: int
    scan_count: int
    hit_count: int
    duration_seconds: float
    tickers: list[TickerResult]


class UniverseShowResponse(BaseModel):
    mode: Mode
    base_tickers: list[str]
    overrides_added: list[str]
    overrides_removed: list[str]
    effective_tickers: list[str]
    base_source: str


class UniverseUpdateRequest(BaseModel):
    mode: Mode
    action: Literal["add", "remove", "replace", "clear_overrides"]
    tickers: list[str] = Field(default_factory=list)


class UniverseUpdateResponse(BaseModel):
    mode: Mode
    overrides_added: list[str]
    overrides_removed: list[str]
    effective_size: int


class CoiledEntry(BaseModel):
    ticker: str
    mode: Mode
    first_detected_at: date
    last_seen_at: date
    days_in_compression: int
    status: Literal["active", "fired", "broken"]
```

- [ ] **Step 2: Verify imports cleanly**

```bash
venv/bin/python -c "from api.schemas.screener import ScreenerRunResponse, TickerResult; print('ok')"
```

Expected: prints `ok` with no import errors.

- [ ] **Step 3: Commit**

```bash
git add api/schemas/screener.py
git commit -m "feat(screener): add Pydantic schemas for morning screener API"
```

---

## Task 3: Test scaffolding — conftest

**Files:**
- Create: `tests/screener/__init__.py`
- Create: `tests/screener/conftest.py`

- [ ] **Step 1: Create test module marker**

```bash
mkdir -p tests/screener
touch tests/screener/__init__.py
```

- [ ] **Step 2: Write conftest with shared fixtures**

```python
# tests/screener/conftest.py
"""Shared fixtures for screener tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def synth_daily_bars():
    """Builder for synthetic daily OHLCV bars.

    Usage:
        bars = synth_daily_bars(closes=[100, 101, 102, ...], volume=5_000_000)
    """
    def _build(
        closes: list[float],
        volume: int = 5_000_000,
        start: str = "2026-01-01",
    ) -> pd.DataFrame:
        dates = pd.date_range(start, periods=len(closes), freq="B")
        return pd.DataFrame({
            "date": dates,
            "open": closes,
            "high": [c * 1.005 for c in closes],
            "low": [c * 0.995 for c in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        })
    return _build


@pytest.fixture
def mock_supabase():
    """A MagicMock structured to look like a Supabase client.

    Tests configure return values per-table-call as needed.
    """
    sb = MagicMock()
    return sb
```

- [ ] **Step 3: Verify pytest discovers the module**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/ --collect-only -q
```

Expected: `0 tests collected` (no test files yet, but no errors).

- [ ] **Step 4: Commit**

```bash
git add tests/screener/__init__.py tests/screener/conftest.py
git commit -m "test(screener): add test module scaffolding and shared fixtures"
```

---

## Task 4: Indicator overlay — ATR%, %from50MA, Extension

**Files:**
- Create: `tests/screener/test_overlay.py`
- Create: `api/indicators/screener/__init__.py`
- Create: `api/indicators/screener/overlay.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_overlay.py
"""Tests for the indicator overlay computer."""
from __future__ import annotations

import pytest

from api.indicators.screener.overlay import compute_overlay


def test_overlay_returns_all_metrics(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert out.atr_pct >= 0
    assert out.sma_50 == pytest.approx(100.0)
    assert out.atr_14 >= 0
    assert out.pct_from_50ma == pytest.approx(0.0, abs=1e-9)
    assert out.extension == pytest.approx(0.0, abs=1e-9)


def test_extension_uses_jfsrev_formula(synth_daily_bars):
    """Extension = ((close - SMA50) * close) / (SMA50 * ATR).

    Construct bars where SMA50 ≈ 70, close = 100, ATR ≈ 3.
    """
    closes = [70.0] * 50 + [100.0] * 10
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    # B = (100 - SMA50)/SMA50; A = ATR/100; Ext = B/A
    expected_b = (100.0 - out.sma_50) / out.sma_50
    expected_a = out.atr_14 / 100.0
    assert out.extension == pytest.approx(expected_b / expected_a, rel=1e-6)


def test_overlay_raises_when_insufficient_bars(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 49)
    with pytest.raises(ValueError, match="at least 50"):
        compute_overlay(bars)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_overlay.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.indicators.screener.overlay'`.

- [ ] **Step 3: Create module marker**

```bash
mkdir -p api/indicators/screener
touch api/indicators/screener/__init__.py
```

- [ ] **Step 4: Implement the overlay**

```python
# api/indicators/screener/overlay.py
"""Indicator overlay: ATR%, % from 50-MA, jfsrev extension.

Single function `compute_overlay(bars)` computes all metrics from a daily OHLCV
DataFrame with columns: open, high, low, close, volume.
"""
from __future__ import annotations

import pandas as pd
import talib

from api.schemas.screener import IndicatorOverlay


SMA_PERIOD = 50
ATR_PERIOD = 14


def compute_overlay(bars: pd.DataFrame) -> IndicatorOverlay:
    """Compute the indicator overlay from a daily bar DataFrame.

    Requires at least 50 bars (for the SMA50). Raises ValueError if fewer.
    """
    if len(bars) < SMA_PERIOD:
        raise ValueError(
            f"compute_overlay requires at least {SMA_PERIOD} bars; got {len(bars)}."
        )

    high = bars["high"].astype(float).values
    low = bars["low"].astype(float).values
    close = bars["close"].astype(float).values

    sma_50 = float(pd.Series(close).rolling(SMA_PERIOD).mean().iloc[-1])
    atr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)
    atr_14 = float(atr[-1]) if not pd.isna(atr[-1]) else 0.0
    last_close = float(close[-1])

    atr_pct = atr_14 / last_close if last_close > 0 else 0.0
    pct_from_50ma = (last_close - sma_50) / sma_50 if sma_50 > 0 else 0.0

    if atr_pct > 0:
        b = pct_from_50ma
        a = atr_pct
        extension = b / a
    else:
        extension = 0.0

    return IndicatorOverlay(
        atr_pct=atr_pct,
        pct_from_50ma=pct_from_50ma,
        extension=extension,
        sma_50=sma_50,
        atr_14=atr_14,
    )
```

- [ ] **Step 5: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_overlay.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/screener/test_overlay.py api/indicators/screener/__init__.py api/indicators/screener/overlay.py
git commit -m "feat(screener): add indicator overlay (ATR%, %from50MA, jfsrev extension)"
```

---

## Task 5: Universe overrides — Supabase CRUD + apply layer

**Files:**
- Create: `tests/screener/test_universe_override.py`
- Create: `api/indicators/screener/universe_override.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_universe_override.py
"""Tests for universe overrides: Supabase CRUD + apply on top of base universe."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.indicators.screener.universe_override import (
    add_overrides,
    remove_overrides,
    clear_overrides,
    list_overrides,
    apply_overrides,
)


def _table_chain(rows):
    """Build a Supabase chain that returns `rows` from .execute()."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.insert.return_value = chain
    chain.delete.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    return chain


def test_apply_overrides_adds_and_removes(mock_supabase):
    rows = [
        {"mode": "swing", "ticker": "NVDA", "action": "add"},
        {"mode": "swing", "ticker": "TSLA", "action": "remove"},
    ]
    mock_supabase.table.return_value = _table_chain(rows)
    base = ["AAPL", "TSLA", "MSFT"]
    effective = apply_overrides(mock_supabase, base, mode="swing")
    assert "NVDA" in effective
    assert "TSLA" not in effective
    assert "AAPL" in effective
    assert "MSFT" in effective


def test_add_overrides_writes_unique_rows(mock_supabase):
    chain = _table_chain([])
    mock_supabase.table.return_value = chain
    add_overrides(mock_supabase, mode="swing", tickers=["NVDA", "AMD", "NVDA"])
    insert_args = chain.insert.call_args[0][0]
    inserted_tickers = sorted({r["ticker"] for r in insert_args})
    assert inserted_tickers == ["AMD", "NVDA"]
    assert all(r["action"] == "add" for r in insert_args)
    assert all(r["mode"] == "swing" for r in insert_args)


def test_clear_overrides_deletes_for_mode(mock_supabase):
    chain = _table_chain([])
    mock_supabase.table.return_value = chain
    clear_overrides(mock_supabase, mode="swing")
    chain.delete.assert_called_once()
    chain.eq.assert_any_call("mode", "swing")


def test_list_overrides_partitions_by_action(mock_supabase):
    rows = [
        {"mode": "swing", "ticker": "NVDA", "action": "add"},
        {"mode": "swing", "ticker": "AMD", "action": "add"},
        {"mode": "swing", "ticker": "TSLA", "action": "remove"},
    ]
    mock_supabase.table.return_value = _table_chain(rows)
    added, removed = list_overrides(mock_supabase, mode="swing")
    assert sorted(added) == ["AMD", "NVDA"]
    assert removed == ["TSLA"]


def test_remove_overrides_writes_remove_rows(mock_supabase):
    chain = _table_chain([])
    mock_supabase.table.return_value = chain
    remove_overrides(mock_supabase, mode="swing", tickers=["TSLA"])
    insert_args = chain.insert.call_args[0][0]
    assert insert_args == [{"mode": "swing", "ticker": "TSLA", "action": "remove", "source": "claude_skill"}]
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_universe_override.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the overrides module**

```python
# api/indicators/screener/universe_override.py
"""Universe overrides — manual ticker add/remove on top of resolved base universe.

Persisted to Supabase `universe_overrides` table. Per-mode (swing/position).
"""
from __future__ import annotations

from typing import Literal

from supabase import Client


Mode = Literal["swing", "position"]


def add_overrides(sb: Client, mode: Mode, tickers: list[str]) -> None:
    """Insert add-overrides for the given tickers. Deduplicates input."""
    unique = sorted(set(t.upper().strip() for t in tickers if t.strip()))
    if not unique:
        return
    rows = [
        {"mode": mode, "ticker": t, "action": "add", "source": "claude_skill"}
        for t in unique
    ]
    sb.table("universe_overrides").insert(rows).execute()


def remove_overrides(sb: Client, mode: Mode, tickers: list[str]) -> None:
    """Insert remove-overrides for the given tickers. Deduplicates input."""
    unique = sorted(set(t.upper().strip() for t in tickers if t.strip()))
    if not unique:
        return
    rows = [
        {"mode": mode, "ticker": t, "action": "remove", "source": "claude_skill"}
        for t in unique
    ]
    sb.table("universe_overrides").insert(rows).execute()


def clear_overrides(sb: Client, mode: Mode) -> None:
    """Delete all overrides for the given mode."""
    sb.table("universe_overrides").delete().eq("mode", mode).execute()


def list_overrides(sb: Client, mode: Mode) -> tuple[list[str], list[str]]:
    """Return (added_tickers, removed_tickers) for the given mode."""
    res = (
        sb.table("universe_overrides")
        .select("*")
        .eq("mode", mode)
        .execute()
    )
    rows = res.data or []
    added = sorted({r["ticker"] for r in rows if r["action"] == "add"})
    removed = sorted({r["ticker"] for r in rows if r["action"] == "remove"})
    return added, removed


def apply_overrides(sb: Client, base_tickers: list[str], mode: Mode) -> list[str]:
    """Apply overrides to a base ticker list. Adds first, then removes."""
    added, removed = list_overrides(sb, mode)
    effective = set(base_tickers) | set(added)
    effective -= set(removed)
    return sorted(effective)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_universe_override.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_universe_override.py api/indicators/screener/universe_override.py
git commit -m "feat(screener): add universe overrides CRUD + apply layer"
```

---

## Task 6: Scan registry pattern

**Files:**
- Create: `tests/screener/test_registry.py`
- Create: `api/indicators/screener/registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_registry.py
"""Tests for the scan registry."""
from __future__ import annotations

import pytest

from api.indicators.screener.registry import (
    ScanDescriptor,
    register_scan,
    get_scans_for_mode,
    get_scan_by_id,
    clear_registry,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_lookup_by_id():
    def dummy_fn(bars_by_ticker, overlays_by_ticker):
        return []
    desc = ScanDescriptor(
        scan_id="dummy",
        lane="breakout",
        role="trigger",
        mode="swing",
        fn=dummy_fn,
    )
    register_scan(desc)
    assert get_scan_by_id("dummy") is desc


def test_get_scans_for_mode_filters():
    def fn(_, __):
        return []
    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", fn))
    register_scan(ScanDescriptor("b", "breakout", "trigger", "position", fn))
    register_scan(ScanDescriptor("c", "transition", "coiled", "swing", fn))
    swing = get_scans_for_mode("swing")
    ids = sorted(s.scan_id for s in swing)
    assert ids == ["a", "c"]


def test_register_duplicate_raises():
    def fn(_, __):
        return []
    register_scan(ScanDescriptor("dup", "breakout", "trigger", "swing", fn))
    with pytest.raises(ValueError, match="already registered"):
        register_scan(ScanDescriptor("dup", "breakout", "trigger", "swing", fn))
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_registry.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the registry**

```python
# api/indicators/screener/registry.py
"""Scan registry — scans declare themselves at import time.

A ScanDescriptor is (scan_id, lane, role, mode, fn). The runner iterates over
descriptors filtered by mode and dispatches each fn with the shared
(bars_by_ticker, overlays_by_ticker) context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from api.schemas.screener import IndicatorOverlay, Lane, Mode, Role, ScanHit


ScanFn = Callable[
    [dict[str, pd.DataFrame], dict[str, IndicatorOverlay]],
    list[ScanHit],
]


@dataclass(frozen=True)
class ScanDescriptor:
    scan_id: str
    lane: Lane
    role: Role
    mode: Mode
    fn: ScanFn


_REGISTRY: dict[str, ScanDescriptor] = {}


def register_scan(desc: ScanDescriptor) -> None:
    if desc.scan_id in _REGISTRY:
        raise ValueError(f"Scan '{desc.scan_id}' already registered.")
    _REGISTRY[desc.scan_id] = desc


def get_scan_by_id(scan_id: str) -> ScanDescriptor | None:
    return _REGISTRY.get(scan_id)


def get_scans_for_mode(mode: Mode) -> list[ScanDescriptor]:
    return [d for d in _REGISTRY.values() if d.mode == mode]


def all_scans() -> list[ScanDescriptor]:
    return list(_REGISTRY.values())


def clear_registry() -> None:
    """Test-only: empty the registry."""
    _REGISTRY.clear()
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_registry.py api/indicators/screener/registry.py
git commit -m "feat(screener): add scan registry pattern"
```

---

## Task 7: Coiled Spring scan

**Files:**
- Create: `tests/screener/test_coiled.py`
- Create: `api/indicators/screener/scans/__init__.py`
- Create: `api/indicators/screener/scans/coiled.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_coiled.py
"""Tests for the Coiled Spring multi-condition scan."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.scans.coiled import (
    is_coiled,
    coiled_scan,
)


def _bars_with_compression(start_close=100.0, days=120, compress_window=10):
    """Build 120 bars: trend up to day 100, then a flat compression for last 10."""
    rng = np.random.default_rng(42)
    closes = list(np.linspace(start_close, start_close * 1.6, days - compress_window))
    flat = [closes[-1]] * compress_window
    closes = closes + flat
    dates = pd.date_range("2025-12-01", periods=days, freq="B")
    highs = [c + rng.uniform(0.0, 0.2) for c in closes[:-compress_window]] + [
        flat[0] + 0.05 for _ in range(compress_window)
    ]
    lows = [c - rng.uniform(0.0, 0.2) for c in closes[:-compress_window]] + [
        flat[0] - 0.05 for _ in range(compress_window)
    ]
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [5_000_000] * days,
    })


def _bars_no_compression():
    """Random-walk bars, definitely not compressed."""
    rng = np.random.default_rng(7)
    closes = [100.0]
    for _ in range(119):
        closes.append(closes[-1] * (1 + rng.normal(0, 0.03)))
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.04 for c in closes],
        "low": [c * 0.96 for c in closes],
        "close": closes,
        "volume": [5_000_000] * 120,
    })


def test_is_coiled_detects_compression():
    bars = _bars_with_compression()
    assert is_coiled(bars) is True


def test_is_coiled_rejects_random_walk():
    bars = _bars_no_compression()
    assert is_coiled(bars) is False


def test_is_coiled_requires_above_50ma():
    """Trend gate: close < SMA50 → never coiled."""
    closes = list(np.linspace(200.0, 50.0, 120))  # downtrend
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    bars = pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [5_000_000] * 120,
    })
    assert is_coiled(bars) is False


def test_coiled_scan_emits_hit_for_compressed_ticker():
    bars = _bars_with_compression()
    bars_by_ticker = {"FAKE": bars}
    overlays_by_ticker = {"FAKE": compute_overlay(bars)}
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker)
    assert len(hits) == 1
    assert hits[0].ticker == "FAKE"
    assert hits[0].lane == "breakout"
    assert hits[0].role == "coiled"
    assert hits[0].scan_id == "coiled_spring"
    assert "donchian_width_pct" in hits[0].evidence


def test_coiled_scan_skips_random_ticker():
    bars = _bars_no_compression()
    bars_by_ticker = {"NOISE": bars}
    overlays_by_ticker = {"NOISE": compute_overlay(bars)}
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker)
    assert hits == []
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_coiled.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create scans module marker**

```bash
mkdir -p api/indicators/screener/scans
touch api/indicators/screener/scans/__init__.py
```

- [ ] **Step 4: Implement Coiled Spring**

```python
# api/indicators/screener/scans/coiled.py
"""Coiled Spring scan — multi-condition compression detector.

Conditions (ALL must be true on the latest daily bar):
  1. Donchian width (20-day high - low) / close < 8%   (basing)
  2. TTM Squeeze ON: Bollinger Bands inside Keltner Channels
  3. (Phase Oscillator condition deferred — Plan 2 will wire the actual indicator;
     for now we use a proxy: rolling-20 close stddev / SMA20 < 2%)
  4. close > SMA50 (trend gate)

Lives in lane=breakout, role=coiled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import talib

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


DONCHIAN_PERIOD = 20
DONCHIAN_WIDTH_THRESHOLD = 0.08
BB_PERIOD = 20
BB_STD = 2.0
KC_PERIOD = 20
KC_ATR_MULT = 1.5
COMPRESSION_PROXY_THRESHOLD = 0.02


def _ttm_squeeze_on(bars: pd.DataFrame) -> bool:
    high = bars["high"].astype(float).values
    low = bars["low"].astype(float).values
    close = bars["close"].astype(float).values
    if len(close) < max(BB_PERIOD, KC_PERIOD) + 1:
        return False
    upper_bb, _, lower_bb = talib.BBANDS(close, timeperiod=BB_PERIOD, nbdevup=BB_STD, nbdevdn=BB_STD)
    atr = talib.ATR(high, low, close, timeperiod=KC_PERIOD)
    sma = talib.SMA(close, timeperiod=KC_PERIOD)
    upper_kc = sma[-1] + KC_ATR_MULT * atr[-1]
    lower_kc = sma[-1] - KC_ATR_MULT * atr[-1]
    return bool(upper_bb[-1] <= upper_kc and lower_bb[-1] >= lower_kc)


def _donchian_width_pct(bars: pd.DataFrame) -> float:
    if len(bars) < DONCHIAN_PERIOD:
        return float("inf")
    window = bars.iloc[-DONCHIAN_PERIOD:]
    width = float(window["high"].max() - window["low"].min())
    last_close = float(bars["close"].iloc[-1])
    return width / last_close if last_close > 0 else float("inf")


def _compression_proxy(bars: pd.DataFrame) -> float:
    """Stand-in for Phase Oscillator compression — rolling stddev / SMA20."""
    close = bars["close"].astype(float)
    if len(close) < BB_PERIOD:
        return float("inf")
    sma20 = float(close.rolling(BB_PERIOD).mean().iloc[-1])
    std20 = float(close.rolling(BB_PERIOD).std().iloc[-1])
    return std20 / sma20 if sma20 > 0 else float("inf")


def is_coiled(bars: pd.DataFrame) -> bool:
    """Return True if the latest bar meets all coiled-spring conditions."""
    if len(bars) < 50:
        return False
    last_close = float(bars["close"].iloc[-1])
    sma_50 = float(bars["close"].rolling(50).mean().iloc[-1])
    if last_close <= sma_50:
        return False
    if _donchian_width_pct(bars) >= DONCHIAN_WIDTH_THRESHOLD:
        return False
    if not _ttm_squeeze_on(bars):
        return False
    if _compression_proxy(bars) >= COMPRESSION_PROXY_THRESHOLD:
        return False
    return True


def coiled_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    """Emit a hit for every ticker whose latest bar is coiled."""
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if not is_coiled(bars):
            continue
        hits.append(ScanHit(
            ticker=ticker,
            scan_id="coiled_spring",
            lane="breakout",
            role="coiled",
            evidence={
                "donchian_width_pct": _donchian_width_pct(bars),
                "ttm_squeeze_on": True,
                "compression_proxy": _compression_proxy(bars),
                "close": float(bars["close"].iloc[-1]),
            },
        ))
    return hits


# Self-register at import time
register_scan(ScanDescriptor(
    scan_id="coiled_spring",
    lane="breakout",
    role="coiled",
    mode="swing",
    fn=coiled_scan,
))
```

- [ ] **Step 5: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_coiled.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/screener/test_coiled.py api/indicators/screener/scans/__init__.py api/indicators/screener/scans/coiled.py
git commit -m "feat(screener): add Coiled Spring multi-condition scan"
```

---

## Task 8: Persistence — screener_runs + coiled_watchlist

**Files:**
- Create: `tests/screener/test_persistence.py`
- Create: `api/indicators/screener/persistence.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_persistence.py
"""Tests for screener_runs + coiled_watchlist Supabase CRUD."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from api.indicators.screener.persistence import (
    save_run,
    update_coiled_watchlist,
    get_active_coiled,
)


def _chain(rows=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.upsert.return_value = chain
    chain.execute.return_value = MagicMock(data=rows or [])
    return chain


def test_save_run_inserts_row(mock_supabase):
    chain = _chain()
    mock_supabase.table.return_value = chain
    payload = {
        "mode": "swing",
        "universe_size": 500,
        "scan_count": 1,
        "hit_count": 7,
        "duration_seconds": 42.5,
        "results": {"tickers": []},
    }
    run_id = save_run(mock_supabase, payload)
    assert run_id is not None
    insert_arg = chain.insert.call_args[0][0]
    assert insert_arg["mode"] == "swing"
    assert insert_arg["hit_count"] == 7


def test_update_coiled_watchlist_inserts_new_ticker(mock_supabase):
    """A coiled ticker not yet on watchlist gets a new row with days=1."""
    chain = _chain([])  # no existing rows
    mock_supabase.table.return_value = chain
    today = date(2026, 4, 25)
    update_coiled_watchlist(
        mock_supabase,
        mode="swing",
        coiled_tickers={"NVDA"},
        today=today,
    )
    upsert_arg = chain.upsert.call_args[0][0]
    nvda_row = next(r for r in upsert_arg if r["ticker"] == "NVDA")
    assert nvda_row["days_in_compression"] == 1
    assert nvda_row["status"] == "active"
    assert nvda_row["first_detected_at"] == today.isoformat()


def test_update_coiled_watchlist_increments_existing(mock_supabase):
    """An existing active coiled ticker gets days_in_compression++ when seen again."""
    today = date(2026, 4, 25)
    yesterday = today - timedelta(days=1)
    existing = [{
        "ticker": "NVDA",
        "mode": "swing",
        "first_detected_at": (today - timedelta(days=4)).isoformat(),
        "last_seen_at": yesterday.isoformat(),
        "days_in_compression": 4,
        "status": "active",
    }]
    chain = _chain(existing)
    mock_supabase.table.return_value = chain
    update_coiled_watchlist(
        mock_supabase,
        mode="swing",
        coiled_tickers={"NVDA"},
        today=today,
    )
    upsert_arg = chain.upsert.call_args[0][0]
    nvda_row = next(r for r in upsert_arg if r["ticker"] == "NVDA")
    assert nvda_row["days_in_compression"] == 5
    assert nvda_row["last_seen_at"] == today.isoformat()


def test_update_coiled_watchlist_marks_broken_when_missing(mock_supabase):
    """An active ticker NOT in today's coiled set gets status='broken'."""
    today = date(2026, 4, 25)
    yesterday = today - timedelta(days=1)
    existing = [{
        "ticker": "TSLA",
        "mode": "swing",
        "first_detected_at": (today - timedelta(days=10)).isoformat(),
        "last_seen_at": yesterday.isoformat(),
        "days_in_compression": 10,
        "status": "active",
    }]
    chain = _chain(existing)
    mock_supabase.table.return_value = chain
    update_coiled_watchlist(
        mock_supabase,
        mode="swing",
        coiled_tickers=set(),  # TSLA no longer coiled
        today=today,
    )
    upsert_arg = chain.upsert.call_args[0][0]
    tsla_row = next(r for r in upsert_arg if r["ticker"] == "TSLA")
    assert tsla_row["status"] == "broken"


def test_get_active_coiled_filters_by_mode(mock_supabase):
    rows = [{"ticker": "NVDA", "days_in_compression": 8}]
    chain = _chain(rows)
    mock_supabase.table.return_value = chain
    out = get_active_coiled(mock_supabase, mode="swing")
    assert out == rows
    chain.eq.assert_any_call("mode", "swing")
    chain.eq.assert_any_call("status", "active")
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_persistence.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement persistence**

```python
# api/indicators/screener/persistence.py
"""Supabase CRUD for screener_runs and coiled_watchlist."""
from __future__ import annotations

from datetime import date
from typing import Literal

from supabase import Client


Mode = Literal["swing", "position"]


def save_run(sb: Client, payload: dict) -> str:
    """Insert a row into screener_runs and return the new id."""
    res = sb.table("screener_runs").insert(payload).execute()
    rows = res.data or []
    return rows[0]["id"] if rows else ""


def get_active_coiled(sb: Client, mode: Mode) -> list[dict]:
    """Return all currently-active coiled rows for the given mode."""
    res = (
        sb.table("coiled_watchlist")
        .select("*")
        .eq("mode", mode)
        .eq("status", "active")
        .execute()
    )
    return res.data or []


def update_coiled_watchlist(
    sb: Client,
    mode: Mode,
    coiled_tickers: set[str],
    today: date,
) -> None:
    """Reconcile active coiled rows with today's coiled set.

    For each ticker in coiled_tickers:
      - If active row exists: last_seen_at=today, days_in_compression++
      - Else: insert new row with days_in_compression=1, status='active'

    For each active row whose ticker is NOT in coiled_tickers:
      - Mark status='broken' (the squeeze broke without firing)

    Uses upsert keyed on (ticker, mode, first_detected_at).
    """
    existing = get_active_coiled(sb, mode)
    existing_by_ticker = {r["ticker"]: r for r in existing}

    upserts: list[dict] = []

    for ticker in coiled_tickers:
        prior = existing_by_ticker.get(ticker)
        if prior:
            upserts.append({
                "ticker": ticker,
                "mode": mode,
                "first_detected_at": prior["first_detected_at"],
                "last_seen_at": today.isoformat(),
                "days_in_compression": int(prior["days_in_compression"]) + 1,
                "status": "active",
            })
        else:
            upserts.append({
                "ticker": ticker,
                "mode": mode,
                "first_detected_at": today.isoformat(),
                "last_seen_at": today.isoformat(),
                "days_in_compression": 1,
                "status": "active",
            })

    for ticker, prior in existing_by_ticker.items():
        if ticker in coiled_tickers:
            continue
        upserts.append({
            "ticker": ticker,
            "mode": mode,
            "first_detected_at": prior["first_detected_at"],
            "last_seen_at": prior["last_seen_at"],
            "days_in_compression": int(prior["days_in_compression"]),
            "status": "broken",
        })

    if upserts:
        sb.table("coiled_watchlist").upsert(
            upserts,
            on_conflict="ticker,mode,first_detected_at",
        ).execute()
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_persistence.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_persistence.py api/indicators/screener/persistence.py
git commit -m "feat(screener): add screener_runs + coiled_watchlist Supabase CRUD"
```

---

## Task 9: Coiled backfill on first run

**Files:**
- Modify: `tests/screener/test_persistence.py`
- Modify: `api/indicators/screener/persistence.py`

- [ ] **Step 1: Add the failing backfill test**

Append to `tests/screener/test_persistence.py`:

```python
def test_backfill_days_in_compression_counts_consecutive_history():
    """Backfill: given last 60 daily bars + an is_coiled fn, count consecutive
    compressed days ending today."""
    from api.indicators.screener.persistence import backfill_days_in_compression
    import pandas as pd

    # Fake is_coiled: True for last 6 bars, False before
    history_len = 60

    def fake_is_coiled(window: pd.DataFrame) -> bool:
        return len(window) >= history_len - 5  # True for windows ending in last 6 days

    bars = pd.DataFrame({
        "date": pd.date_range("2026-02-01", periods=history_len, freq="B"),
        "open": [100.0] * history_len,
        "high": [101.0] * history_len,
        "low": [99.0] * history_len,
        "close": [100.0] * history_len,
        "volume": [1_000_000] * history_len,
    })
    days = backfill_days_in_compression(bars, is_coiled_fn=fake_is_coiled)
    assert days == 6


def test_backfill_returns_zero_when_today_not_coiled():
    from api.indicators.screener.persistence import backfill_days_in_compression
    import pandas as pd

    def never(_window):
        return False

    bars = pd.DataFrame({
        "date": pd.date_range("2026-02-01", periods=60, freq="B"),
        "open": [100.0] * 60,
        "high": [101.0] * 60,
        "low": [99.0] * 60,
        "close": [100.0] * 60,
        "volume": [1_000_000] * 60,
    })
    days = backfill_days_in_compression(bars, is_coiled_fn=never)
    assert days == 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_persistence.py -v -k backfill
```

Expected: FAIL with `ImportError: cannot import name 'backfill_days_in_compression'`.

- [ ] **Step 3: Add the backfill implementation**

Append to `api/indicators/screener/persistence.py`:

```python
from typing import Callable

import pandas as pd


def backfill_days_in_compression(
    bars: pd.DataFrame,
    is_coiled_fn: Callable[[pd.DataFrame], bool],
    max_lookback: int = 60,
) -> int:
    """Count consecutive trailing days where is_coiled_fn(bars[:i+1]) is True.

    Used on first run so existing coils don't reset to day 1. Walks backward
    from the latest bar; stops at the first non-coiled day.
    """
    n = len(bars)
    end = n
    days = 0
    for offset in range(min(max_lookback, n)):
        window = bars.iloc[: end - offset]
        if not is_coiled_fn(window):
            break
        days += 1
    return days
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_persistence.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_persistence.py api/indicators/screener/persistence.py
git commit -m "feat(screener): add backfill_days_in_compression for first-run history"
```

---

## Task 10: Runner orchestration

**Files:**
- Create: `tests/screener/test_runner.py`
- Create: `api/indicators/screener/runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_runner.py
"""Tests for the runner orchestration."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from api.indicators.screener.registry import (
    ScanDescriptor,
    register_scan,
    clear_registry,
)
from api.indicators.screener.runner import run_screener
from api.schemas.screener import IndicatorOverlay, ScanHit


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def _bars(closes):
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=len(closes), freq="B"),
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [5_000_000] * len(closes),
    })


def test_runner_aggregates_hits_into_confluence(mock_supabase):
    bars_aapl = _bars([100.0] * 60)
    bars_nvda = _bars([100.0] * 60)
    bars_by_ticker = {"AAPL": bars_aapl, "NVDA": bars_nvda}

    def scan_a(bars_by, overlays_by):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    def scan_b(bars_by, overlays_by):
        return [ScanHit(ticker="NVDA", scan_id="b", lane="breakout", role="trigger")]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a))
    register_scan(ScanDescriptor("b", "breakout", "trigger", "swing", scan_b))

    chain = MagicMock()
    chain.insert.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "run-1"}])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.upsert.return_value = chain
    mock_supabase.table.return_value = chain

    response = run_screener(
        sb=mock_supabase,
        mode="swing",
        bars_by_ticker=bars_by_ticker,
        today=date(2026, 4, 25),
    )

    by_ticker = {t.ticker: t for t in response.tickers}
    assert by_ticker["AAPL"].confluence == 1
    assert by_ticker["NVDA"].confluence == 2
    assert response.hit_count == 2  # 2 unique tickers with hits
    assert response.scan_count == 2


def test_runner_skips_tickers_with_insufficient_bars(mock_supabase):
    bars_short = _bars([100.0] * 30)  # < 50 bars: overlay raises
    bars_ok = _bars([100.0] * 60)

    def scan_all(bars_by, overlays_by):
        return [ScanHit(ticker=t, scan_id="x", lane="breakout", role="trigger") for t in overlays_by]

    register_scan(ScanDescriptor("x", "breakout", "trigger", "swing", scan_all))

    chain = MagicMock()
    chain.insert.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "run-2"}])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.upsert.return_value = chain
    mock_supabase.table.return_value = chain

    response = run_screener(
        sb=mock_supabase,
        mode="swing",
        bars_by_ticker={"SHORT": bars_short, "OK": bars_ok},
        today=date(2026, 4, 25),
    )

    tickers = [t.ticker for t in response.tickers]
    assert "OK" in tickers
    assert "SHORT" not in tickers
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_runner.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the runner**

```python
# api/indicators/screener/runner.py
"""Runner: orchestrates a single screener run.

Inputs:
  - sb: Supabase client
  - mode: 'swing' | 'position'
  - bars_by_ticker: pre-fetched daily OHLCV per ticker
  - today: date stamp for coiled watchlist update

Steps:
  1. Compute indicator overlay per ticker (skip tickers with too few bars)
  2. Dispatch each registered scan for the mode
  3. Aggregate (ticker -> scans_hit list) confluence map
  4. Update coiled_watchlist for tickers whose hits include scan_id='coiled_spring'
  5. Persist screener_runs row
  6. Return ScreenerRunResponse
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

from supabase import Client

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.persistence import save_run, update_coiled_watchlist
from api.indicators.screener.registry import get_scans_for_mode
from api.schemas.screener import (
    IndicatorOverlay,
    Mode,
    ScreenerRunResponse,
    TickerResult,
)


import pandas as pd


def run_screener(
    sb: Client,
    mode: Mode,
    bars_by_ticker: dict[str, pd.DataFrame],
    today: date,
    scan_ids: list[str] | None = None,
) -> ScreenerRunResponse:
    started = time.time()

    overlays: dict[str, IndicatorOverlay] = {}
    for ticker, bars in bars_by_ticker.items():
        try:
            overlays[ticker] = compute_overlay(bars)
        except ValueError:
            continue

    eligible_bars = {t: bars_by_ticker[t] for t in overlays}

    descriptors = get_scans_for_mode(mode)
    if scan_ids is not None:
        descriptors = [d for d in descriptors if d.scan_id in scan_ids]

    hits_by_ticker: dict[str, list[str]] = {t: [] for t in overlays}

    coiled_tickers: set[str] = set()
    for desc in descriptors:
        try:
            hits = desc.fn(eligible_bars, overlays)
        except Exception:
            continue
        for hit in hits:
            hits_by_ticker.setdefault(hit.ticker, []).append(hit.scan_id)
            if hit.scan_id == "coiled_spring":
                coiled_tickers.add(hit.ticker)

    update_coiled_watchlist(sb, mode=mode, coiled_tickers=coiled_tickers, today=today)

    ticker_results: list[TickerResult] = []
    for ticker, scans in hits_by_ticker.items():
        if not scans:
            continue
        ticker_results.append(TickerResult(
            ticker=ticker,
            last_close=float(eligible_bars[ticker]["close"].iloc[-1]),
            overlay=overlays[ticker],
            scans_hit=scans,
            confluence=len(scans),
        ))

    duration = time.time() - started

    payload = {
        "mode": mode,
        "universe_size": len(bars_by_ticker),
        "scan_count": len(descriptors),
        "hit_count": len(ticker_results),
        "duration_seconds": round(duration, 3),
        "results": {"tickers": [t.model_dump(mode="json") for t in ticker_results]},
    }
    run_id = save_run(sb, payload)

    return ScreenerRunResponse(
        run_id=run_id,
        mode=mode,
        ran_at=datetime.now(timezone.utc),
        universe_size=len(bars_by_ticker),
        scan_count=len(descriptors),
        hit_count=len(ticker_results),
        duration_seconds=round(duration, 3),
        tickers=ticker_results,
    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_runner.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_runner.py api/indicators/screener/runner.py
git commit -m "feat(screener): add runner orchestration with confluence aggregation"
```

---

## Task 11: Bar fetcher — yfinance bulk download

**Files:**
- Create: `api/indicators/screener/bars.py`
- Create: tests added to `tests/screener/test_runner.py` (or new file `tests/screener/test_bars.py`)

- [ ] **Step 1: Write the failing test**

Create `tests/screener/test_bars.py`:

```python
# tests/screener/test_bars.py
"""Tests for bar fetcher."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from api.indicators.screener.bars import fetch_daily_bars_bulk


def _stub_yf_download_result(tickers: list[str]) -> pd.DataFrame:
    """yfinance returns a multi-index DataFrame for batch downloads."""
    dates = pd.date_range("2026-02-01", periods=60, freq="B")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], tickers])
    data = {}
    for col_name in ["Open", "High", "Low", "Close"]:
        for t in tickers:
            data[(col_name, t)] = [100.0] * 60
    for t in tickers:
        data[("Volume", t)] = [1_000_000] * 60
    return pd.DataFrame(data, index=dates, columns=cols)


def test_fetch_daily_bars_bulk_returns_dict_keyed_by_ticker():
    tickers = ["AAPL", "NVDA"]
    with patch("api.indicators.screener.bars.yf.download") as mock_dl:
        mock_dl.return_value = _stub_yf_download_result(tickers)
        out = fetch_daily_bars_bulk(tickers, period="6mo")
    assert set(out.keys()) == {"AAPL", "NVDA"}
    for t, df in out.items():
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
        assert len(df) == 60


def test_fetch_daily_bars_bulk_handles_empty_input():
    out = fetch_daily_bars_bulk([], period="6mo")
    assert out == {}


def test_fetch_daily_bars_bulk_skips_tickers_with_all_nans():
    tickers = ["GOOD", "DEAD"]
    df = _stub_yf_download_result(tickers)
    df[("Close", "DEAD")] = [float("nan")] * 60
    df[("Open", "DEAD")] = [float("nan")] * 60
    df[("High", "DEAD")] = [float("nan")] * 60
    df[("Low", "DEAD")] = [float("nan")] * 60
    df[("Volume", "DEAD")] = [float("nan")] * 60
    with patch("api.indicators.screener.bars.yf.download") as mock_dl:
        mock_dl.return_value = df
        out = fetch_daily_bars_bulk(tickers, period="6mo")
    assert "GOOD" in out
    assert "DEAD" not in out
```

- [ ] **Step 2: Run test — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_bars.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the fetcher**

```python
# api/indicators/screener/bars.py
"""Bulk daily-bar fetcher using yfinance."""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_daily_bars_bulk(
    tickers: list[str],
    period: str = "6mo",
) -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV for all tickers in one yfinance batch call.

    Returns a dict {ticker: DataFrame[date, open, high, low, close, volume]}.
    Tickers with all-NaN data are dropped.
    """
    if not tickers:
        return {}

    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        group_by="column",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            df = pd.DataFrame({
                "date": raw.index,
                "open": raw[("Open", ticker)].values,
                "high": raw[("High", ticker)].values,
                "low": raw[("Low", ticker)].values,
                "close": raw[("Close", ticker)].values,
                "volume": raw[("Volume", ticker)].values,
            })
        except KeyError:
            continue
        df = df.dropna(subset=["close"])
        if df.empty:
            continue
        out[ticker] = df.reset_index(drop=True)
    return out
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_bars.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_bars.py api/indicators/screener/bars.py
git commit -m "feat(screener): add bulk daily-bar fetcher (yfinance)"
```

---

## Task 12: API endpoints — `/api/screener/morning/run` + universe routes

**Files:**
- Create: `tests/screener/test_endpoints.py`
- Create: `api/endpoints/screener_morning.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/screener/test_endpoints.py
"""Endpoint tests for the morning screener API."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints.screener_morning import router as screener_router
from api.schemas.screener import (
    IndicatorOverlay,
    ScreenerRunResponse,
    TickerResult,
)


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(screener_router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def test_run_morning_endpoint_calls_runner(client):
    fake_response = ScreenerRunResponse(
        run_id="run-1",
        mode="swing",
        ran_at=datetime.now(timezone.utc),
        universe_size=10,
        scan_count=1,
        hit_count=1,
        duration_seconds=1.2,
        tickers=[TickerResult(
            ticker="NVDA",
            last_close=900.0,
            overlay=IndicatorOverlay(atr_pct=0.03, pct_from_50ma=0.05, extension=1.67, sma_50=857.0, atr_14=27.0),
            scans_hit=["coiled_spring"],
            confluence=1,
        )],
    )
    with patch("api.endpoints.screener_morning._resolve_active_universe", return_value=["NVDA"]):
        with patch("api.endpoints.screener_morning.fetch_daily_bars_bulk", return_value={"NVDA": MagicMock()}):
            with patch("api.endpoints.screener_morning.run_screener", return_value=fake_response):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post("/api/screener/morning/run", json={"mode": "swing"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "swing"
    assert body["tickers"][0]["ticker"] == "NVDA"


def test_universe_show_endpoint(client):
    with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL", "TSLA"], "deepvue")):
        with patch("api.endpoints.screener_morning.list_overrides", return_value=(["NVDA"], ["TSLA"])):
            with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                res = client.get("/api/screener/universe?mode=swing")
    assert res.status_code == 200
    body = res.json()
    assert "NVDA" in body["effective_tickers"]
    assert "TSLA" not in body["effective_tickers"]
    assert "AAPL" in body["effective_tickers"]
    assert body["base_source"] == "deepvue"


def test_universe_update_add_action(client):
    with patch("api.endpoints.screener_morning.add_overrides") as mock_add:
        with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL"], "deepvue")):
            with patch("api.endpoints.screener_morning.list_overrides", return_value=(["NVDA"], [])):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post(
                        "/api/screener/universe/update",
                        json={"mode": "swing", "action": "add", "tickers": ["NVDA"]},
                    )
    assert res.status_code == 200
    mock_add.assert_called_once()
    body = res.json()
    assert "NVDA" in body["overrides_added"]


def test_universe_update_clear_overrides(client):
    with patch("api.endpoints.screener_morning.clear_overrides") as mock_clear:
        with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL"], "deepvue")):
            with patch("api.endpoints.screener_morning.list_overrides", return_value=([], [])):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post(
                        "/api/screener/universe/update",
                        json={"mode": "swing", "action": "clear_overrides"},
                    )
    assert res.status_code == 200
    mock_clear.assert_called_once()
```

- [ ] **Step 2: Run tests — expect failure**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_endpoints.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the endpoints**

```python
# api/endpoints/screener_morning.py
"""Morning screener endpoints — run scans, manage universe overrides.

Routes:
  POST /api/screener/morning/run         — run all scans for a mode, return results
  GET  /api/screener/universe             — show base + overrides + effective list
  POST /api/screener/universe/update      — add/remove/replace/clear overrides
"""
from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, HTTPException
from supabase import Client, create_client

from api.indicators.screener.bars import fetch_daily_bars_bulk
from api.indicators.screener.runner import run_screener
from api.indicators.screener.universe_override import (
    add_overrides,
    clear_overrides,
    list_overrides,
    remove_overrides,
)
# Reuses the swing universe resolver as the base universe source.
from api.indicators.swing.universe.resolver import resolve_universe
from api.schemas.screener import (
    Mode,
    ScreenerRunRequest,
    ScreenerRunResponse,
    UniverseShowResponse,
    UniverseUpdateRequest,
    UniverseUpdateResponse,
)

# Side effect: registers the coiled_spring scan
import api.indicators.screener.scans.coiled  # noqa: F401


router = APIRouter(prefix="/api/screener", tags=["screener"])


def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _resolve_base_universe(sb: Client, mode: Mode) -> tuple[list[str], str]:
    """For Plan 1, swing mode reuses the existing swing universe.
    Position mode raises until Plan 4 adds it.
    """
    if mode != "swing":
        raise HTTPException(status_code=501, detail=f"mode '{mode}' not supported in Plan 1")
    resolved = resolve_universe(sb)
    return list(resolved.tickers), resolved.source


def _resolve_active_universe(sb: Client, mode: Mode) -> list[str]:
    base, _ = _resolve_base_universe(sb, mode)
    added, removed = list_overrides(sb, mode)
    eff = (set(base) | set(added)) - set(removed)
    return sorted(eff)


@router.post("/morning/run", response_model=ScreenerRunResponse)
def run_morning(req: ScreenerRunRequest) -> ScreenerRunResponse:
    sb = _get_supabase()
    tickers = _resolve_active_universe(sb, req.mode)
    if not tickers:
        raise HTTPException(status_code=400, detail="Active universe is empty.")
    bars_by_ticker = fetch_daily_bars_bulk(tickers, period="6mo")
    return run_screener(
        sb=sb,
        mode=req.mode,
        bars_by_ticker=bars_by_ticker,
        today=date.today(),
        scan_ids=req.scan_ids,
    )


@router.get("/universe", response_model=UniverseShowResponse)
def get_universe(mode: Mode = "swing") -> UniverseShowResponse:
    sb = _get_supabase()
    base, source = _resolve_base_universe(sb, mode)
    added, removed = list_overrides(sb, mode)
    eff = sorted((set(base) | set(added)) - set(removed))
    return UniverseShowResponse(
        mode=mode,
        base_tickers=sorted(base),
        overrides_added=added,
        overrides_removed=removed,
        effective_tickers=eff,
        base_source=source,
    )


@router.post("/universe/update", response_model=UniverseUpdateResponse)
def update_universe(req: UniverseUpdateRequest) -> UniverseUpdateResponse:
    sb = _get_supabase()

    if req.action == "add":
        add_overrides(sb, mode=req.mode, tickers=req.tickers)
    elif req.action == "remove":
        remove_overrides(sb, mode=req.mode, tickers=req.tickers)
    elif req.action == "replace":
        clear_overrides(sb, mode=req.mode)
        # Treat replacement as: clear, then add the new list as overrides.
        # The base universe still applies; replacement here means "these are
        # the only overrides on top of the resolved base".
        add_overrides(sb, mode=req.mode, tickers=req.tickers)
    elif req.action == "clear_overrides":
        clear_overrides(sb, mode=req.mode)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    base, _ = _resolve_base_universe(sb, req.mode)
    added, removed = list_overrides(sb, req.mode)
    eff = (set(base) | set(added)) - set(removed)
    return UniverseUpdateResponse(
        mode=req.mode,
        overrides_added=added,
        overrides_removed=removed,
        effective_size=len(eff),
    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/test_endpoints.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/screener/test_endpoints.py api/endpoints/screener_morning.py
git commit -m "feat(screener): add /api/screener/morning/run and /api/screener/universe endpoints"
```

---

## Task 13: Wire router into FastAPI app

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Inspect existing router includes**

```bash
grep -n "include_router\|from api.endpoints" api/main.py | head -20
```

Note the pattern used (likely `from api.endpoints.swing import router as swing_router; app.include_router(swing_router)`).

- [ ] **Step 2: Add the screener router**

Add the import alongside other endpoint imports in `api/main.py`:

```python
from api.endpoints.screener_morning import router as screener_router
```

And in the app setup section where other routers are included:

```python
app.include_router(screener_router)
```

- [ ] **Step 3: Smoke-test the app boots**

```bash
venv/bin/python -c "from api.main import app; print(sorted(r.path for r in app.routes if hasattr(r, 'path')))" | tr ',' '\n' | grep screener
```

Expected: shows `/api/screener/morning/run`, `/api/screener/universe`, `/api/screener/universe/update`.

- [ ] **Step 4: Commit**

```bash
git add api/main.py
git commit -m "feat(screener): register screener_morning router on FastAPI app"
```

---

## Task 14: Claude Code skill — `/screener-universe-edit`

**Files:**
- Create: `.claude/skills/screener-universe-edit.md`

- [ ] **Step 1: Write the skill markdown**

```markdown
<!-- .claude/skills/screener-universe-edit.md -->
# /screener-universe-edit — Manual universe edits for the morning screener

Mutates the active screener universe via the Railway API. Persists overrides
across CSV refreshes; per-mode (swing | position).

## Subcommands

- `/screener-universe-edit show [--mode swing|position]`
- `/screener-universe-edit add NVDA, AMD, MXL [--mode swing]`
- `/screener-universe-edit remove TSLA [--mode swing]`
- `/screener-universe-edit replace NVDA, AMD [--mode swing]`
- `/screener-universe-edit clear [--mode swing]`

Default mode is `swing`.

## Auth & base URL

Same conventions as the swing skills (see `.claude/skills/_swing-shared.md`):

- Bearer token at `~/.config/trend-trading-mcp/swing-api.token`
- Base URL from `RAILWAY_SWING_BASE` env, fallback
  `https://trend-trading-mcp-production.up.railway.app`

## Implementation

Parse the user input. Then:

1. **show**

   ```bash
   curl -sf "$BASE/api/screener/universe?mode=$MODE" \
     -H "Authorization: Bearer $TOKEN" | jq .
   ```

   Render the output as a table:

   ```
   Mode: swing
   Base source: deepvue
   Base size: 524 tickers
   Manual added: NVDA, AMD, MXL (3)
   Manual removed: TSLA (1)
   Effective size: 526 tickers
   ```

2. **add / remove / replace** — all use POST `/api/screener/universe/update`:

   ```bash
   curl -sf -X POST "$BASE/api/screener/universe/update" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"mode\": \"$MODE\", \"action\": \"$ACTION\", \"tickers\": $TICKERS_JSON}"
   ```

   Where `$ACTION` is `add` / `remove` / `replace` and `$TICKERS_JSON` is a
   JSON array. Tickers should be uppercased and trimmed.

3. **clear** — POST with `action: "clear_overrides"` and no tickers.

## Failure modes

- Token file missing: `echo "token file missing"` and exit 1.
- HTTP non-2xx: print response body, exit 2. Do NOT retry silently.
- Empty ticker list for add/remove/replace: tell the user and exit without
  calling the API.

## Examples

User: `/screener-universe-edit add NVDA, AMD, MXL`

Action: parse 3 tickers, POST `{mode:"swing", action:"add", tickers:["NVDA","AMD","MXL"]}`,
then run `show` to print the new state.

User: `/screener-universe-edit remove TSLA --mode position`

Action: POST `{mode:"position", action:"remove", tickers:["TSLA"]}`, then `show` for position mode.
```

- [ ] **Step 2: Verify the skill file is well-formed**

```bash
ls -la .claude/skills/screener-universe-edit.md
head -5 .claude/skills/screener-universe-edit.md
```

Expected: file exists and starts with the comment + heading.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/screener-universe-edit.md
git commit -m "feat(screener): add /screener-universe-edit Claude Code skill"
```

---

## Task 15: End-to-end smoke test

**Files:**
- Create: `scripts/screener_smoke_test.py`

- [ ] **Step 1: Write the smoke test**

```python
#!/usr/bin/env python3
"""End-to-end smoke test for the morning screener.

Runs against a real Supabase + yfinance — does NOT mock anything. Use sparingly.

Usage:
    venv/bin/python scripts/screener_smoke_test.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

# Ensure scans are registered
import api.indicators.screener.scans.coiled  # noqa: F401
from api.indicators.screener.bars import fetch_daily_bars_bulk
from api.indicators.screener.runner import run_screener
from supabase import create_client


SAMPLE_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD", "MXL", "PLTR", "META", "AVGO", "COST"]


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        return 1

    sb = create_client(url, key)

    print(f"Fetching bars for {len(SAMPLE_TICKERS)} tickers...")
    bars = fetch_daily_bars_bulk(SAMPLE_TICKERS, period="6mo")
    print(f"  Got bars for {len(bars)} tickers.")

    print("Running screener...")
    response = run_screener(
        sb=sb,
        mode="swing",
        bars_by_ticker=bars,
        today=date.today(),
    )

    print(f"\nRun {response.run_id} — {response.duration_seconds}s")
    print(f"  Universe size: {response.universe_size}")
    print(f"  Scans run: {response.scan_count}")
    print(f"  Hits: {response.hit_count}")
    for tr in response.tickers:
        print(f"  {tr.ticker:6s}  Ext={tr.overlay.extension:+6.2f}  "
              f"ATR%={tr.overlay.atr_pct*100:5.2f}  "
              f"scans={tr.scans_hit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/screener_smoke_test.py
```

- [ ] **Step 3: Run it (requires Supabase env)**

```bash
venv/bin/python scripts/screener_smoke_test.py
```

Expected: prints fetched ticker count, runs the screener, prints per-ticker overlay + any coiled hits, exit 0. If no tickers are coiled today, the hit count may be 0 — that's fine; the goal is verifying the pipeline works end-to-end.

- [ ] **Step 4: Verify Supabase rows landed**

```bash
psql "$SUPABASE_DB_URL" -c "select id, mode, hit_count, duration_seconds, ran_at from screener_runs order by ran_at desc limit 5;"
```

Expected: at least one new row with the just-run results.

- [ ] **Step 5: Commit**

```bash
git add scripts/screener_smoke_test.py
git commit -m "test(screener): add end-to-end smoke test script"
```

---

## Task 16: Run the full test suite + lint

**Files:** none modified.

- [ ] **Step 1: Run all screener tests**

```bash
venv/bin/python -m pytest --confcutdir=tests/screener tests/screener/ -v
```

Expected: all tests in tests/screener/ pass (≥22 tests).

- [ ] **Step 2: Run the existing swing test suite to confirm no regression**

```bash
venv/bin/python -m pytest tests/swing/ -v
```

Expected: same passing count as before (no regressions).

- [ ] **Step 3: Run mypy / ruff if configured**

```bash
venv/bin/python -m ruff check api/indicators/screener/ api/endpoints/screener_morning.py api/schemas/screener.py tests/screener/ 2>/dev/null || echo "ruff not configured, skipping"
venv/bin/python -m mypy api/indicators/screener/ 2>/dev/null || echo "mypy not configured, skipping"
```

Expected: no errors (or skip messages).

- [ ] **Step 4: Final tag commit if anything was fixed**

If steps 1–3 surfaced any fixes, commit them with:

```bash
git add -A
git commit -m "chore(screener): plan-1 lint/test fixes"
```

If nothing was fixed, skip this step.

---

## Task 17: Push branch + summary

- [ ] **Step 1: Push**

```bash
git push origin HEAD
```

- [ ] **Step 2: Print plan-completion summary**

Print the following to the user:

```
Plan 1 complete. New surfaces:

Backend:
  - 3 Supabase tables: screener_runs, coiled_watchlist, universe_overrides
  - api/indicators/screener/ module: overlay, registry, runner, scans/coiled, bars,
    persistence, universe_override
  - 3 API endpoints under /api/screener/

Claude skill:
  - /screener-universe-edit (show, add, remove, replace, clear)

Verified end-to-end via scripts/screener_smoke_test.py.

Next: Plan 2 will populate the scan registry with the rest of the catalog
(Pradeep 4%, Qullamaggie EP/Continuation, Saty Trigger Up/Down, Vomy daily/hourly,
Reversion candidates, Wedge Pop, Flag Base, EMA Crossback, Exhaustion Extension)
and wire confluence aggregation into the response payload.
```

---

## Self-Review Notes (for the engineer reading this)

**Spec coverage in Plan 1:** §1 (goal — partial: backend only), §2 (modes/lanes/roles model — schema + registry support all), §3 (one scan: coiled_spring; rest in Plan 2), §4 (Coiled Spring fully implemented), §6 (universe overrides + Claude skill; CSV/generated reused from swing module), §7 (overlay: ATR%, %from50MA, Extension; Saty/Phase/Hourly Vomy deferred), §8 (confluence aggregation in runner), §11 (architecture matches), §12 (3 tables created).

**Deferred to later plans:**
- Plan 2: Remaining scan implementations + Saty indicator integration (overlay enhancements) + Hourly Vomy
- Plan 3: All frontend (`/morning` page, mobile, drawer, mode/lane/role tabs)
- Plan 4: Auto-promotion between lanes, model-book auto-capture, cron wiring, Position-mode UI

**Type consistency check:** `Mode`, `Lane`, `Role` Literal types are defined once in `api/schemas/screener.py` and reused everywhere. `ScanFn` signature in `registry.py` matches what `runner.py` invokes (`fn(bars_by_ticker, overlays_by_ticker)`) and what `coiled_scan` in `scans/coiled.py` accepts.

**Known assumption to revisit:** The `_compression_proxy` in coiled.py is a stand-in for the real Phase Oscillator (rolling stddev / SMA20). Plan 2 will replace this proxy with the actual Phase Oscillator port from `docs/phase_oscillator_pine_script.txt` and recalibrate thresholds.
