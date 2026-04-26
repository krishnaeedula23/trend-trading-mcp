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
