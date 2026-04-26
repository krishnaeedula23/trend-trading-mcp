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
