# api/indicators/screener/bars.py
"""Bulk daily-bar fetcher using yfinance."""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_daily_bars_bulk(
    tickers: list[str],
    period: str = "6mo",
) -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV for all tickers in one yfinance batch call.

    Returns a dict {ticker: DataFrame[date, open, high, low, close, volume]}.
    Tickers with all-NaN data are dropped.
    """
    if not tickers:
        return {}

    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        group_by="column",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            df = pd.DataFrame({
                "date": raw.index,
                "open": raw[("Open", ticker)].values,
                "high": raw[("High", ticker)].values,
                "low": raw[("Low", ticker)].values,
                "close": raw[("Close", ticker)].values,
                "volume": raw[("Volume", ticker)].values,
            })
        except KeyError:
            continue
        df = df.dropna(subset=["close"])
        if df.empty:
            continue
        out[ticker] = df.reset_index(drop=True)
    return out
