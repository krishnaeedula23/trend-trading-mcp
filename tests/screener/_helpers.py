"""Shared synthetic-bar builders for screener tests.

Promoted from inline definitions in each scan's test file once Task 8 made it
clear the helper repeats across 14+ scan tests.
"""
from __future__ import annotations

import pandas as pd


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
