# api/indicators/swing/earnings_calendar.py
"""Earnings calendar utilities for swing trade risk management.

Provides:
  - next_earnings_date(ticker)  → datetime.date | None
  - last_earnings_gap_pct(ticker, bars, lookback_days) → float | None

Fallback chain for next_earnings_date:
  1. yfinance .calendar dict (primary)
  2. Finnhub API (if FINNHUB_API_KEY env var is set)
  3. None
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def next_earnings_date(ticker: str) -> date | None:
    """Return the earliest future earnings date for *ticker*, or None.

    Tries yfinance first; falls back to Finnhub if FINNHUB_API_KEY is set.
    Returns None when both sources are unavailable or raise.
    """
    result = _from_yfinance(ticker)
    if result is not None:
        return result

    result = _from_finnhub(ticker)
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _from_yfinance(ticker: str) -> date | None:
    """Extract the earliest future earnings date from yfinance .calendar."""
    try:
        import yfinance as yf

        cal = yf.Ticker(ticker).calendar
        if not cal or not isinstance(cal, dict):
            return None

        raw = cal.get("Earnings Date")
        if not raw:
            return None

        # Normalise: single Timestamp or list of Timestamps/dates
        if not isinstance(raw, (list, tuple)):
            raw = [raw]

        today = date.today()
        candidates: list[date] = []
        for item in raw:
            try:
                if isinstance(item, datetime):
                    d = item.date()
                elif isinstance(item, date):
                    d = item
                elif isinstance(item, pd.Timestamp):
                    d = item.date()
                else:
                    continue
                if d >= today:
                    candidates.append(d)
            except Exception:  # noqa: BLE001
                continue

        return min(candidates) if candidates else None

    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance earnings lookup failed for %s: %s", ticker, exc)
        return None


def _from_finnhub(ticker: str) -> date | None:
    """Extract the earliest future earnings date from Finnhub API."""
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return None

    try:
        import requests

        url = "https://finnhub.io/api/v1/stock/earnings-calendar"
        resp = requests.get(url, params={"symbol": ticker, "token": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("earningsCalendar") or []
        today = date.today()
        candidates: list[date] = []
        for entry in entries:
            raw_date = entry.get("date")
            if not raw_date:
                continue
            try:
                d = date.fromisoformat(raw_date)
                if d >= today:
                    candidates.append(d)
            except ValueError:
                continue

        return min(candidates) if candidates else None

    except Exception as exc:  # noqa: BLE001
        logger.warning("Finnhub earnings lookup failed for %s: %s", ticker, exc)
        return None


def last_earnings_gap_pct(
    ticker: str,  # noqa: ARG001  kept for API consistency
    bars: pd.DataFrame,
    lookback_days: int = 10,
) -> float | None:
    """Return the largest gap-up (>= 5%) in the last *lookback_days* bars.

    A gap-up is defined as:
        (bars['open'].iloc[i] - bars['close'].iloc[i-1]) / bars['close'].iloc[i-1] >= 0.05

    Returns the largest gap as a positive float (e.g. 0.07 for 7%),
    or None if no qualifying gap is found.
    """
    if bars is None or len(bars) < 2:
        return None

    start = max(len(bars) - lookback_days, 1)
    best: float | None = None

    for i in range(start, len(bars)):
        prev_close = bars["close"].iloc[i - 1]
        cur_open = bars["open"].iloc[i]
        if prev_close == 0:
            continue
        gap = (cur_open - prev_close) / prev_close
        if gap >= 0.05:
            best = gap if best is None else max(best, gap)

    return best
