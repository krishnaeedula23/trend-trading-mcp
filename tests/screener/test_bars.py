# tests/screener/test_bars.py
"""Tests for bar fetcher."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from api.indicators.screener.bars import fetch_daily_bars_bulk


def _stub_yf_download_result(tickers: list[str]) -> pd.DataFrame:
    """yfinance returns a multi-index DataFrame for batch downloads."""
    dates = pd.date_range("2026-02-01", periods=60, freq="B")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], tickers])
    data = {}
    for col_name in ["Open", "High", "Low", "Close"]:
        for t in tickers:
            data[(col_name, t)] = [100.0] * 60
    for t in tickers:
        data[("Volume", t)] = [1_000_000] * 60
    return pd.DataFrame(data, index=dates, columns=cols)


def test_fetch_daily_bars_bulk_returns_dict_keyed_by_ticker():
    tickers = ["AAPL", "NVDA"]
    with patch("api.indicators.screener.bars.yf.download") as mock_dl:
        mock_dl.return_value = _stub_yf_download_result(tickers)
        out = fetch_daily_bars_bulk(tickers, period="6mo")
    assert set(out.keys()) == {"AAPL", "NVDA"}
    for t, df in out.items():
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
        assert len(df) == 60


def test_fetch_daily_bars_bulk_handles_empty_input():
    out = fetch_daily_bars_bulk([], period="6mo")
    assert out == {}


def test_fetch_daily_bars_bulk_skips_tickers_with_all_nans():
    tickers = ["GOOD", "DEAD"]
    df = _stub_yf_download_result(tickers)
    df[("Close", "DEAD")] = [float("nan")] * 60
    df[("Open", "DEAD")] = [float("nan")] * 60
    df[("High", "DEAD")] = [float("nan")] * 60
    df[("Low", "DEAD")] = [float("nan")] * 60
    df[("Volume", "DEAD")] = [float("nan")] * 60
    with patch("api.indicators.screener.bars.yf.download") as mock_dl:
        mock_dl.return_value = df
        out = fetch_daily_bars_bulk(tickers, period="6mo")
    assert "GOOD" in out
    assert "DEAD" not in out
