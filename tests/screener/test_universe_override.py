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


def test_apply_overrides_remove_wins_over_add_for_same_ticker(mock_supabase):
    """Contract: when a ticker has both add and remove rows, remove wins."""
    rows = [
        {"mode": "swing", "ticker": "NVDA", "action": "add"},
        {"mode": "swing", "ticker": "NVDA", "action": "remove"},
    ]
    mock_supabase.table.return_value = _table_chain(rows)
    effective = apply_overrides(mock_supabase, base_tickers=["AAPL"], mode="swing")
    assert "NVDA" not in effective
    assert "AAPL" in effective


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
