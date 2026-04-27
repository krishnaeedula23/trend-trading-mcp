"""Test that the runner backfills days_in_compression for newly-coiled tickers."""
from __future__ import annotations

import importlib
from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from api.indicators.screener.registry import clear_registry
from api.indicators.screener.runner import run_screener


@pytest.fixture(autouse=True)
def _reset_registry():
    import api.indicators.screener.scans.coiled as coiled_module
    clear_registry()
    importlib.reload(coiled_module)
    yield
    clear_registry()


def _flat_compressed_bars(days=120, compress_window=40):
    """Build bars that satisfy is_coiled: step-up base then flat compression.

    Matches the pattern from test_coiled.py's _bars_with_compression helper:
    (days - compress_window) bars at start * 0.99, then compress_window bars flat.
    Realistic ±0.5 intra-bar ranges so TTM Squeeze fires and phase oscillator
    converges to ~0 over the long flat window.
    """
    rng = np.random.default_rng(42)
    start_close = 100.0
    closes = [start_close * 0.99] * (days - compress_window) + [start_close] * compress_window
    dates = pd.date_range("2025-12-01", periods=days, freq="B")
    highs = [c + float(rng.uniform(0.4, 0.6)) for c in closes]
    lows = [c - float(rng.uniform(0.4, 0.6)) for c in closes]
    return pd.DataFrame({
        "date": dates, "open": closes, "high": highs, "low": lows,
        "close": closes, "volume": [5_000_000] * days,
    })


def test_runner_seeds_days_in_compression_from_backfill(mock_supabase):
    bars = _flat_compressed_bars(days=120, compress_window=40)

    runs_chain = MagicMock()
    runs_chain.insert.return_value = runs_chain
    runs_chain.execute.return_value = MagicMock(data=[{"id": "run-bf"}])

    coiled_chain = MagicMock()
    coiled_chain.select.return_value = coiled_chain
    coiled_chain.eq.return_value = coiled_chain
    coiled_chain.upsert.return_value = coiled_chain
    coiled_chain.execute.return_value = MagicMock(data=[])

    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"FAKE": bars},
        today=date(2026, 4, 25),
    )

    upsert_arg = coiled_chain.upsert.call_args[0][0]
    fake_row = next(r for r in upsert_arg if r["ticker"] == "FAKE")
    assert fake_row["days_in_compression"] >= 5, (
        f"Expected backfilled days >= 5; got {fake_row['days_in_compression']}"
    )
