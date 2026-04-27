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

    def _make_chain(rows=None):
        c = MagicMock()
        c.insert.return_value = c
        c.select.return_value = c
        c.eq.return_value = c
        c.upsert.return_value = c
        c.execute.return_value = MagicMock(data=rows if rows is not None else [])
        return c

    runs_chain = _make_chain([{"id": "run-1"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

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

    def _make_chain(rows=None):
        c = MagicMock()
        c.insert.return_value = c
        c.select.return_value = c
        c.eq.return_value = c
        c.upsert.return_value = c
        c.execute.return_value = MagicMock(data=rows if rows is not None else [])
        return c

    runs_chain = _make_chain([{"id": "run-2"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase,
        mode="swing",
        bars_by_ticker={"SHORT": bars_short, "OK": bars_ok},
        today=date(2026, 4, 25),
    )

    tickers = [t.ticker for t in response.tickers]
    assert "OK" in tickers
    assert "SHORT" not in tickers


def test_runner_filters_by_scan_ids(mock_supabase):
    """When scan_ids is passed, only those scans run."""
    def scan_a(bars_by, overlays_by):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    def scan_b(bars_by, overlays_by):
        return [ScanHit(ticker=t, scan_id="b", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a))
    register_scan(ScanDescriptor("b", "breakout", "trigger", "swing", scan_b))

    def _make_chain(rows=None):
        c = MagicMock()
        c.insert.return_value = c
        c.select.return_value = c
        c.eq.return_value = c
        c.upsert.return_value = c
        c.execute.return_value = MagicMock(data=rows if rows is not None else [])
        return c

    runs_chain = _make_chain([{"id": "run-3"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase,
        mode="swing",
        bars_by_ticker={"AAPL": _bars([100.0] * 60)},
        today=date(2026, 4, 25),
        scan_ids=["a"],
    )

    assert response.scan_count == 1
    aapl = next(t for t in response.tickers if t.ticker == "AAPL")
    assert aapl.scans_hit == ["a"]


def test_runner_returns_weighted_confluence(mock_supabase):
    """Confluence score = sum of scan weights, not raw count."""
    from datetime import date
    from unittest.mock import MagicMock
    from api.indicators.screener.registry import ScanDescriptor, register_scan, clear_registry
    from api.indicators.screener.runner import run_screener
    from api.schemas.screener import ScanHit

    clear_registry()

    def scan_heavy(bars_by, _o):
        return [ScanHit(ticker=t, scan_id="heavy", lane="breakout", role="trigger") for t in bars_by]

    def scan_light(bars_by, _o):
        return [ScanHit(ticker=t, scan_id="light", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("heavy", "breakout", "trigger", "swing", scan_heavy, weight=3))
    register_scan(ScanDescriptor("light", "breakout", "trigger", "swing", scan_light, weight=1))

    def _make_chain(rows=None):
        c = MagicMock()
        c.insert.return_value = c
        c.select.return_value = c
        c.eq.return_value = c
        c.upsert.return_value = c
        c.execute.return_value = MagicMock(data=rows if rows is not None else [])
        return c

    runs_chain = _make_chain([{"id": "run-w"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": _bars([100.0] * 60)},
        today=date(2026, 4, 25),
    )
    aapl = next(t for t in response.tickers if t.ticker == "AAPL")
    assert aapl.confluence == 4
    assert aapl.confluence_weight == 4
    assert sorted(aapl.scans_hit) == ["heavy", "light"]
    clear_registry()


def test_runner_picks_up_scans_via_package_import():
    """Regression test for prior bug: the scans PACKAGE __init__ must trigger
    self-registration of every scan, because that's the production import path.

    Use importlib.reload to force the side effect after the autouse fixture
    cleared the registry — `import` alone is a no-op when modules are cached.
    """
    import importlib

    import api.indicators.screener.scans as scans_pkg
    import api.indicators.screener.scans.coiled as coiled_module
    import api.indicators.screener.registry as registry_module

    # Force the side effects to re-run against the cleared registry
    importlib.reload(coiled_module)
    importlib.reload(scans_pkg)

    descriptors = registry_module.all_scans()
    assert any(d.scan_id == "coiled_spring" for d in descriptors), (
        "coiled_spring must self-register when the scans package is imported; "
        "if this fails, scans/__init__.py is not importing coiled.py"
    )
