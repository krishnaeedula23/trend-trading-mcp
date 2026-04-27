"""Shared synthetic-bar builders for screener tests.

Promoted from inline definitions in each scan's test file once Task 8 made it
clear the helper repeats across 14+ scan tests.
"""
from __future__ import annotations

import importlib

import pandas as pd


def force_register_scan_module(module_path: str) -> None:
    """Clear the registry and re-import a scan module so its register_scan(...)
    side effects fire from a clean state.

    Use this in tests that depend on a specific scan being registered (and no
    others). Example:
        force_register_scan_module("api.indicators.screener.scans.saty_reversion")
    """
    from api.indicators.screener.registry import clear_registry

    clear_registry()
    mod = importlib.import_module(module_path)
    importlib.reload(mod)


def scan_fn_by_id(scan_id: str):
    """Return the scan function registered under `scan_id`. Asserts presence."""
    from api.indicators.screener.registry import get_scan_by_id

    desc = get_scan_by_id(scan_id)
    assert desc is not None, f"missing scan {scan_id}"
    return desc.fn


def make_daily_bars(
    closes: list[float],
    volumes: list[int] | None = None,
    *,
    opens: list[float] | None = None,
    high_mult: float = 1.01,
    low_mult: float = 0.99,
    start: str = "2026-01-01",
) -> pd.DataFrame:
    """Build a synthetic daily OHLCV DataFrame.

    Defaults: open=close, high=close*1.01, low=close*0.99, volume=1_000_000.
    Override any of these via kwargs when a test needs a specific shape.
    """
    n = len(closes)
    if opens is None:
        opens = list(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    return pd.DataFrame({
        "date": pd.date_range(start, periods=n, freq="B"),
        "open": opens,
        "high": [c * high_mult for c in closes],
        "low":  [c * low_mult for c in closes],
        "close": closes, "volume": volumes,
    })
