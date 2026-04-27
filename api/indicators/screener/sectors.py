"""Ticker → sector cache.

Backed by yfinance .info["sector"]. Cached per-process to avoid hammering
yfinance on every screener run. Failures map to "Unknown" rather than raising —
sector grouping is a UX nicety, not a correctness gate.
"""
from __future__ import annotations

import logging

import yfinance as yf


logger = logging.getLogger(__name__)

_CACHE: dict[str, str] = {}


def get_sector(ticker: str) -> str:
    """Return the sector for ``ticker``; "Unknown" on failure or missing data."""
    if ticker in _CACHE:
        return _CACHE[ticker]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector") or "Unknown"
    except Exception as exc:  # noqa: BLE001
        logger.warning("sector lookup failed for %s: %s", ticker, exc)
        sector = "Unknown"
    _CACHE[ticker] = sector
    return sector


def get_sectors_bulk(tickers: list[str]) -> dict[str, str]:
    """Return {ticker: sector} for many tickers; uses the same per-process cache."""
    return {t: get_sector(t) for t in tickers}
