"""Tests for runner-level observability: earnings filter, sector grouping, structured logs."""
from __future__ import annotations

import logging
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from api.indicators.screener.registry import ScanDescriptor, clear_registry, register_scan
from api.indicators.screener.runner import run_screener
from api.schemas.screener import ScanHit
from tests.screener._helpers import make_daily_bars


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def _make_chain(rows=None):
    c = MagicMock()
    c.insert.return_value = c
    c.select.return_value = c
    c.eq.return_value = c
    c.upsert.return_value = c
    c.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return c


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date")
def test_earnings_blackout_filters_breakout_triggers(mock_earnings, mock_sectors, mock_supabase):
    """A ticker with earnings in 3 days must not fire on a breakout-trigger scan."""
    mock_earnings.return_value = date(2026, 4, 28)   # 3 days from today below
    mock_sectors.return_value = {}

    def trigger_scan(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="pradeep_4pct_breakout",
                        lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor(
        "pradeep_4pct_breakout", "breakout", "trigger", "swing",
        trigger_scan, weight=2,
    ))

    runs_chain = _make_chain([{"id": "run-eo"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": make_daily_bars(closes=[100.0] * 60)},
        today=date(2026, 4, 25),
    )
    assert response.hit_count == 0


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date")
def test_earnings_blackout_does_not_filter_setup_ready(mock_earnings, mock_sectors, mock_supabase):
    """A setup_ready scan should still hit even within the earnings blackout window."""
    mock_earnings.return_value = date(2026, 4, 28)
    mock_sectors.return_value = {"AAPL": "Technology"}

    def setup_scan(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="kell_wedge_pop",
                        lane="breakout", role="setup_ready") for t in bars_by]

    register_scan(ScanDescriptor(
        "kell_wedge_pop", "breakout", "setup_ready", "swing",
        setup_scan, weight=1,
    ))

    runs_chain = _make_chain([{"id": "run-sr"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": make_daily_bars(closes=[100.0] * 60)},
        today=date(2026, 4, 25),
    )
    assert response.hit_count == 1


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date", return_value=None)
def test_runner_returns_sector_summary(_, mock_sectors, mock_supabase):
    mock_sectors.return_value = {"AAPL": "Technology", "NVDA": "Technology", "XOM": "Energy"}

    def scan_a(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a, weight=1))

    runs_chain = _make_chain([{"id": "run-sec"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={
            "AAPL": make_daily_bars(closes=[100.0] * 60),
            "NVDA": make_daily_bars(closes=[100.0] * 60),
            "XOM":  make_daily_bars(closes=[100.0] * 60),
        },
        today=date(2026, 4, 25),
    )
    assert response.sector_summary == {"Technology": 2, "Energy": 1}
    by_ticker = {t.ticker: t for t in response.tickers}
    assert by_ticker["AAPL"].sector == "Technology"


@patch("api.indicators.screener.runner.get_sectors_bulk", return_value={})
@patch("api.indicators.screener.runner.next_earnings_date", return_value=None)
def test_runner_emits_structured_logs(_, __, mock_supabase, caplog):
    """Per-scan and per-ticker logs are emitted."""
    def scan_a(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a, weight=1))

    runs_chain = _make_chain([{"id": "run-log"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    with caplog.at_level(logging.INFO, logger="api.indicators.screener.runner"):
        run_screener(
            sb=mock_supabase, mode="swing",
            bars_by_ticker={"AAPL": make_daily_bars(closes=[100.0] * 60)},
            today=date(2026, 4, 25),
        )
    msgs = [r.message for r in caplog.records]
    assert "screener.scan_complete" in msgs
    assert "screener.ticker_hit" in msgs
