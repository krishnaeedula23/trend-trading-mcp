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
