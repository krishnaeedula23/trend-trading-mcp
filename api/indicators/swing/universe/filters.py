"""Universe filter pipeline — 4 stages applied cheapest-first.

Stage 1: price + liquidity (price-only data, fast)
Stage 2: trend + base proxy (price-only, fast)
Stage 3: fundamentals (yfinance quarterly financials, slow — only for Stage 1+2 passers)
Stage 4: relative strength vs QQQ (price-only, fast)

Each stage takes a DataFrame of bars for one ticker and returns bool (pass/fail).
The orchestrator (generator.py) applies stages in sequence.
"""
from __future__ import annotations

import pandas as pd

MIN_PRICE = 50.0
MAX_PRICE = 1_000.0
MIN_DOLLAR_VOLUME_20D = 20_000_000   # Kell: $20M min daily dollar volume
MAX_BASE_RANGE_PCT = 0.15            # 5-8 week base proxy
MIN_REV_GROWTH_YOY = 0.30            # Kell says 40%; relaxed to 30% (yfinance noise)
MIN_RS_VS_QQQ_63D = 0.0              # must outperform


def stage1_price_liquidity(bars: pd.DataFrame) -> bool:
    """Stage 1: price in [50, 1000] + avg 20d dollar volume >= $20M."""
    if bars.empty:
        return False
    last_close = bars["close"].iloc[-1]
    if not (MIN_PRICE <= last_close <= MAX_PRICE):
        return False
    last_20 = bars.tail(20)
    if len(last_20) < 20:
        return False
    dollar_volume = (last_20["close"] * last_20["volume"]).mean()
    return dollar_volume >= MIN_DOLLAR_VOLUME_20D


def stage2_trend_base(bars: pd.DataFrame) -> bool:
    """Stage 2: close > SMA-200 AND last-30-bar range / mid-price < 15%."""
    if len(bars) < 200:
        return False
    sma_200 = bars["close"].tail(200).mean()
    last_close = bars["close"].iloc[-1]
    if last_close <= sma_200:
        return False
    last_30 = bars["close"].tail(30)
    if len(last_30) < 30:
        return False
    hi, lo = last_30.max(), last_30.min()
    mid = (hi + lo) / 2
    if mid <= 0:
        return False
    return (hi - lo) / mid < MAX_BASE_RANGE_PCT


def stage3_fundamentals(fundamentals: dict) -> bool:
    """Stage 3: latest Q rev growth >= 30% AND accelerating from prior quarter."""
    rev = fundamentals.get("quarterly_revenue_yoy")
    if not rev or len(rev) < 2:
        return False
    latest, prior = rev[0], rev[1]
    if latest is None or prior is None:
        return False
    if latest < MIN_REV_GROWTH_YOY:
        return False
    return latest > prior


def stage4_relative_strength(ticker_bars: pd.DataFrame, qqq_bars: pd.DataFrame) -> bool:
    """Stage 4: ticker 63d return > QQQ 63d return."""
    if len(ticker_bars) < 63 or len(qqq_bars) < 63:
        return False
    def _ret(df: pd.DataFrame) -> float:
        start = df["close"].iloc[-63]
        end = df["close"].iloc[-1]
        return (end - start) / start if start > 0 else -1.0
    return _ret(ticker_bars) > _ret(qqq_bars) + MIN_RS_VS_QQQ_63D
