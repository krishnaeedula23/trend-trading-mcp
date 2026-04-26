"""Indicator overlay: ATR%, % from 50-MA, jfsrev extension.

Single function `compute_overlay(bars)` computes all metrics from a daily OHLCV
DataFrame with columns: open, high, low, close, volume.
"""
from __future__ import annotations

import pandas as pd
import talib

from api.schemas.screener import IndicatorOverlay


SMA_PERIOD = 50
ATR_PERIOD = 14


def compute_overlay(bars: pd.DataFrame) -> IndicatorOverlay:
    """Compute the indicator overlay from a daily bar DataFrame.

    Requires at least 50 bars (for the SMA50). Raises ValueError if fewer.
    """
    if len(bars) < SMA_PERIOD:
        raise ValueError(
            f"compute_overlay requires at least {SMA_PERIOD} bars; got {len(bars)}."
        )

    high = bars["high"].astype(float).values
    low = bars["low"].astype(float).values
    close = bars["close"].astype(float).values

    sma_50 = float(pd.Series(close).rolling(SMA_PERIOD).mean().iloc[-1])
    atr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)
    atr_14 = float(atr[-1]) if not pd.isna(atr[-1]) else 0.0
    last_close = float(close[-1])

    atr_pct = atr_14 / last_close if last_close > 0 else 0.0
    pct_from_50ma = (last_close - sma_50) / sma_50 if sma_50 > 0 else 0.0

    if atr_pct > 0:
        b = pct_from_50ma
        a = atr_pct
        extension = b / a
    else:
        extension = 0.0

    return IndicatorOverlay(
        atr_pct=atr_pct,
        pct_from_50ma=pct_from_50ma,
        extension=extension,
        sma_50=sma_50,
        atr_14=atr_14,
    )
