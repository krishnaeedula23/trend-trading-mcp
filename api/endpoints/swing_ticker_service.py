"""Thin yfinance wrapper used by /api/swing/ticker/<T>/* endpoints.

Kept separate from swing.py so tests can monkey-patch these functions
without pulling yfinance into the import graph.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf


_TF_TO_YF: dict[str, tuple[str, str]] = {
    "daily":  ("d", "1d"),
    "weekly": ("d", "1wk"),
    "60m":    ("d", "60m"),
}


def fetch_bars(ticker: str, tf: str, lookback: int) -> pd.DataFrame:
    _, interval = _TF_TO_YF[tf]
    period_days = max(lookback * 2, 10)
    raw = yf.Ticker(ticker).history(period=f"{period_days}d", interval=interval, auto_adjust=False)
    if raw.empty:
        return raw
    df = raw.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
    df.columns = ["date", "open", "high", "low", "close", "volume"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.tail(lookback).reset_index(drop=True)


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    t = yf.Ticker(ticker)
    info: dict[str, Any] = getattr(t, "info", {}) or {}
    cal = getattr(t, "calendar", None)
    next_earn: date | None = None
    try:
        if cal is not None and "Earnings Date" in cal.index:
            next_earn = pd.to_datetime(cal.loc["Earnings Date"][0]).date()
    except Exception:
        next_earn = None
    adv = None
    try:
        hist = t.history(period="40d")
        if not hist.empty:
            adv = float((hist["Close"] * hist["Volume"]).tail(20).mean())
    except Exception:
        pass
    return {
        "fundamentals": info,
        "next_earnings_date": next_earn,
        "beta": info.get("beta"),
        "avg_daily_dollar_volume": adv,
    }
