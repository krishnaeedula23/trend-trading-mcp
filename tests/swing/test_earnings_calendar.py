# tests/swing/test_earnings_calendar.py
"""Tests for api.indicators.swing.earnings_calendar."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api.indicators.swing.earnings_calendar import (
    last_earnings_gap_pct,
    next_earnings_date,
)


# ---------------------------------------------------------------------------
# next_earnings_date — yfinance primary
# ---------------------------------------------------------------------------

def test_next_earnings_date_yfinance_returns_date():
    """yfinance .calendar returns a list → extract earliest future date."""
    future = date.today() + timedelta(days=20)

    mock_ticker = MagicMock()
    mock_ticker.calendar = {"Earnings Date": [future]}

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = next_earnings_date("AAPL")

    assert result == future


def test_next_earnings_date_yfinance_skips_past_dates():
    """Past dates in the list are ignored; only future dates returned."""
    past = date.today() - timedelta(days=5)
    future = date.today() + timedelta(days=30)

    mock_ticker = MagicMock()
    mock_ticker.calendar = {"Earnings Date": [past, future]}

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = next_earnings_date("MSFT")

    assert result == future


def test_next_earnings_date_yfinance_empty_falls_back_to_finnhub(monkeypatch):
    """yfinance returns empty dict → Finnhub fallback is used."""
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")

    mock_ticker = MagicMock()
    mock_ticker.calendar = {}

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "earningsCalendar": [{"date": "2026-05-15"}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with patch("requests.get", return_value=mock_response) as mock_get:
            result = next_earnings_date("NVDA")

    assert result == date(2026, 5, 15)
    mock_get.assert_called_once()


def test_next_earnings_date_yfinance_empty_list_falls_back_to_finnhub(monkeypatch):
    """yfinance returns {'Earnings Date': []} → Finnhub fallback is used."""
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")

    mock_ticker = MagicMock()
    mock_ticker.calendar = {"Earnings Date": []}

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "earningsCalendar": [{"date": "2026-06-01"}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with patch("requests.get", return_value=mock_response):
            result = next_earnings_date("TSLA")

    assert result == date(2026, 6, 1)


def test_next_earnings_date_both_unavailable_returns_none(monkeypatch):
    """yfinance empty + no FINNHUB_API_KEY → None."""
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    mock_ticker = MagicMock()
    mock_ticker.calendar = {}

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = next_earnings_date("XYZ")

    assert result is None


def test_next_earnings_date_yfinance_raises_falls_back_to_finnhub(monkeypatch):
    """yfinance raises an exception → Finnhub fallback used."""
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "earningsCalendar": [{"date": "2026-07-20"}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("yfinance.Ticker", side_effect=RuntimeError("network error")):
        with patch("requests.get", return_value=mock_response):
            result = next_earnings_date("AMZN")

    assert result == date(2026, 7, 20)


def test_next_earnings_date_both_raise_returns_none(monkeypatch):
    """yfinance raises + Finnhub raises → None (no unhandled exception)."""
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")

    with patch("yfinance.Ticker", side_effect=RuntimeError("network")):
        with patch("requests.get", side_effect=RuntimeError("connection refused")):
            result = next_earnings_date("FAIL")

    assert result is None


# ---------------------------------------------------------------------------
# next_earnings_date — Finnhub: filters past dates
# ---------------------------------------------------------------------------

def test_next_earnings_date_finnhub_skips_past_dates(monkeypatch):
    """Finnhub entries with past dates are ignored."""
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")

    mock_ticker = MagicMock()
    mock_ticker.calendar = {}

    past_str = (date.today() - timedelta(days=10)).isoformat()
    future_str = (date.today() + timedelta(days=15)).isoformat()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "earningsCalendar": [{"date": past_str}, {"date": future_str}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with patch("requests.get", return_value=mock_response):
            result = next_earnings_date("META")

    assert result == date.fromisoformat(future_str)


# ---------------------------------------------------------------------------
# last_earnings_gap_pct
# ---------------------------------------------------------------------------

def _make_bars(closes: list[float], opens: list[float]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame."""
    n = len(closes)
    assert len(opens) == n
    return pd.DataFrame(
        {
            "close": closes,
            "open": opens,
            "high": closes,
            "low": closes,
            "volume": [1_000_000] * n,
        }
    )


def test_last_earnings_gap_pct_detects_gap_up():
    """7% gap-up 5 bars ago is returned as ~0.07."""
    # 20 bars; gap at bar index 15 (5 bars from end)
    closes = [100.0] * 20
    opens = [100.0] * 20
    # bar 15: opens 7% above bar-14 close (100.0)
    opens[15] = 107.0

    bars = _make_bars(closes, opens)
    result = last_earnings_gap_pct("AAPL", bars, lookback_days=10)

    assert result is not None
    assert abs(result - 0.07) < 1e-9


def test_last_earnings_gap_pct_no_gap_returns_none():
    """No gap >= 5% → None."""
    closes = [100.0] * 20
    opens = [100.0] * 20
    # small 2% gap — below threshold
    opens[18] = 102.0

    bars = _make_bars(closes, opens)
    result = last_earnings_gap_pct("AAPL", bars, lookback_days=10)

    assert result is None


def test_last_earnings_gap_pct_returns_largest_gap():
    """When multiple gaps qualify, the largest is returned."""
    closes = [100.0] * 20
    opens = [100.0] * 20
    opens[11] = 106.0  # 6% — within lookback=10 from end
    opens[15] = 109.0  # 9% — larger

    bars = _make_bars(closes, opens)
    result = last_earnings_gap_pct("AAPL", bars, lookback_days=10)

    assert result is not None
    assert abs(result - 0.09) < 1e-9


def test_last_earnings_gap_pct_ignores_gaps_outside_lookback():
    """A gap 20 bars ago is outside lookback=10 and must not be returned."""
    closes = [100.0] * 25
    opens = [100.0] * 25
    opens[3] = 110.0  # 10% gap, but index 3 is outside lookback=10 from end (25-10=15)

    bars = _make_bars(closes, opens)
    result = last_earnings_gap_pct("AAPL", bars, lookback_days=10)

    assert result is None


def test_last_earnings_gap_pct_empty_bars_returns_none():
    """Empty DataFrame → None without raising."""
    bars = pd.DataFrame({"close": [], "open": [], "high": [], "low": [], "volume": []})
    result = last_earnings_gap_pct("AAPL", bars)
    assert result is None


def test_last_earnings_gap_pct_exactly_5pct_qualifies():
    """Exactly 5% gap (== threshold) should qualify."""
    closes = [100.0] * 10
    opens = [100.0] * 10
    opens[8] = 105.0  # exactly 5%

    bars = _make_bars(closes, opens)
    result = last_earnings_gap_pct("AAPL", bars, lookback_days=5)

    assert result is not None
    assert abs(result - 0.05) < 1e-9
