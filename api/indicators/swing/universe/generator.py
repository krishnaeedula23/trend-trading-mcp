"""Backend universe generator — applies 4 filter stages over a base ticker list.

Called weekly from the Sunday cron when Deepvue-sourced universe is > 7 days stale.
Runtime: ~10-15 min for ~3500 base tickers because Stage 3 requires a yfinance
fundamentals call per Stage 1+2 passer (~200-400 calls, rate-limited).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from api.indicators.swing.universe.filters import (
    stage1_price_liquidity,
    stage2_trend_base,
    stage3_fundamentals,
    stage4_relative_strength,
)

logger = logging.getLogger(__name__)

BASE_TICKERS_PATH = Path(__file__).parent / "base_tickers.json"


def _load_base_tickers() -> list[str]:
    with BASE_TICKERS_PATH.open() as f:
        return json.load(f)["tickers"]


def _fetch_bars_bulk(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Bulk-fetch daily bars via yfinance. Returns {ticker: DataFrame} including QQQ."""
    import yfinance as yf
    all_tickers = list(set(tickers) | {"QQQ"})
    raw = yf.download(all_tickers, period="1y", group_by="ticker", progress=False, auto_adjust=True)
    result: dict[str, pd.DataFrame] = {}
    for t in all_tickers:
        try:
            sub = raw[t].dropna().reset_index().rename(columns={"Date": "date", "Close": "close", "Volume": "volume"})
            result[t] = sub[["date", "close", "volume"]]
        except Exception as e:
            logger.warning("Failed to unpack bars for %s: %s", t, e)
    return result


def _fetch_fundamentals(ticker: str) -> dict:
    """Fetch quarterly revenue growth via yfinance."""
    import yfinance as yf
    try:
        tk = yf.Ticker(ticker)
        fin = tk.quarterly_financials
        if fin is None or fin.empty:
            return {}
        if "Total Revenue" not in fin.index:
            return {}
        rev = fin.loc["Total Revenue"].dropna()
        if len(rev) < 5:
            return {}
        yoy = []
        for i in range(len(rev) - 4):
            curr = rev.iloc[i]
            prior = rev.iloc[i + 4]
            if prior and prior > 0:
                yoy.append(float((curr - prior) / prior))
        return {"quarterly_revenue_yoy": yoy}
    except Exception as e:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, e)
        return {}


def generate_backend_universe(tickers: list[str] | None = None) -> dict:
    """Run the 4-stage filter pipeline."""
    if tickers is None:
        tickers = _load_base_tickers()

    logger.info("Starting universe generation for %d base tickers", len(tickers))
    bars = _fetch_bars_bulk(tickers)
    qqq = bars.get("QQQ")
    if qqq is None or qqq.empty:
        raise RuntimeError("QQQ bars unavailable — cannot compute RS")

    stage12_pass: list[str] = []
    for t in tickers:
        b = bars.get(t)
        if b is None or not stage1_price_liquidity(b):
            continue
        if not stage2_trend_base(b):
            continue
        stage12_pass.append(t)
    logger.info("Stage 1+2: %d / %d passed", len(stage12_pass), len(tickers))

    stage3_pass: dict[str, dict] = {}
    for t in stage12_pass:
        f = _fetch_fundamentals(t)
        if f and stage3_fundamentals(f):
            stage3_pass[t] = f
    logger.info("Stage 3: %d passed", len(stage3_pass))

    passers: dict[str, dict] = {}
    for t, fund in stage3_pass.items():
        if stage4_relative_strength(bars[t], qqq):
            passers[t] = {"fundamentals": fund}
    logger.info("Stage 4: %d passed — final universe size %d", len(passers), len(passers))

    return {
        "passers": passers,
        "stats": {
            "base_count": len(tickers),
            "stage12_count": len(stage12_pass),
            "stage3_count": len(stage3_pass),
            "final_count": len(passers),
        },
    }
