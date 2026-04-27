"""Tests for hourly-bar bulk fetcher."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd


@patch("api.indicators.screener.bars.yf.download")
def test_fetch_hourly_bars_bulk_returns_dict_keyed_by_ticker(mock_dl):
    from api.indicators.screener.bars import fetch_hourly_bars_bulk

    idx = pd.date_range("2026-04-20 09:30", periods=3, freq="h", tz="America/New_York")
    fake = pd.DataFrame({
        ("Open", "AAPL"):   [170.0, 170.5, 171.0],
        ("High", "AAPL"):   [170.5, 171.0, 171.5],
        ("Low", "AAPL"):    [169.5, 170.3, 170.8],
        ("Close", "AAPL"):  [170.4, 170.9, 171.4],
        ("Volume", "AAPL"): [1_000_000, 800_000, 1_200_000],
        ("Open", "NVDA"):   [800.0, 802.0, 803.0],
        ("High", "NVDA"):   [802.0, 803.5, 804.5],
        ("Low", "NVDA"):    [799.0, 801.0, 802.5],
        ("Close", "NVDA"):  [801.5, 803.0, 804.0],
        ("Volume", "NVDA"): [500_000, 400_000, 600_000],
    }, index=idx)
    mock_dl.return_value = fake

    out = fetch_hourly_bars_bulk(["AAPL", "NVDA"], period="60d")
    assert set(out.keys()) == {"AAPL", "NVDA"}
    assert list(out["AAPL"].columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(out["AAPL"]) == 3


@patch("api.indicators.screener.bars.yf.download")
def test_fetch_hourly_bars_bulk_drops_all_nan_tickers(mock_dl):
    from api.indicators.screener.bars import fetch_hourly_bars_bulk

    idx = pd.date_range("2026-04-20 09:30", periods=2, freq="h", tz="America/New_York")
    fake = pd.DataFrame({
        ("Open", "AAPL"):   [170.0, 170.5],
        ("High", "AAPL"):   [170.5, 171.0],
        ("Low", "AAPL"):    [169.5, 170.3],
        ("Close", "AAPL"):  [170.4, 170.9],
        ("Volume", "AAPL"): [1_000_000, 800_000],
        ("Open", "DEAD"):   [np.nan, np.nan],
        ("High", "DEAD"):   [np.nan, np.nan],
        ("Low", "DEAD"):    [np.nan, np.nan],
        ("Close", "DEAD"):  [np.nan, np.nan],
        ("Volume", "DEAD"): [np.nan, np.nan],
    }, index=idx)
    mock_dl.return_value = fake

    out = fetch_hourly_bars_bulk(["AAPL", "DEAD"], period="60d")
    assert "AAPL" in out
    assert "DEAD" not in out


def test_fetch_hourly_bars_bulk_empty_input():
    from api.indicators.screener.bars import fetch_hourly_bars_bulk
    assert fetch_hourly_bars_bulk([], period="60d") == {}
