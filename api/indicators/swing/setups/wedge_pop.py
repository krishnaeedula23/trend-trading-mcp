"""Wedge Pop setup detector — Kell's descending-channel reclaim pattern."""
from __future__ import annotations

import pandas as pd

from api.indicators.common.atr import atr
from api.indicators.common.moving_averages import ema
from api.indicators.common.relative_strength import rs_vs_benchmark
from api.indicators.swing.setups.base import SetupHit, prior_swing_high, volume_vs_avg


def detect(bars: pd.DataFrame, qqq_bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
    """Return SetupHit if Wedge Pop fires on the current (last) bar, else None."""
    if len(bars) < 25:
        return None

    ema10 = ema(bars, 10)
    ema20 = ema(bars, 20)
    atr14 = atr(bars, 14)
    cur_close = float(bars["close"].iloc[-1])
    cur_atr   = float(atr14.iloc[-1])
    cur_ema10 = float(ema10.iloc[-1])
    cur_ema20 = float(ema20.iloc[-1])

    # 1: EMA10 slope flat (< 0.2 × ATR per bar over last 5 bars)
    slope = (ema10.iloc[-1] - ema10.iloc[-6]) / 5
    if abs(float(slope)) >= 0.2 * cur_atr:
        return None

    # 2: EMA10/EMA20 spread tight (< 0.5 × ATR)
    if abs(cur_ema10 - cur_ema20) >= 0.5 * cur_atr:
        return None

    # 3: prior descending channel in last 15 bars before current
    window = bars.iloc[-16:-1]
    if len(window) < 15:
        return None
    cur_low = float(bars["low"].iloc[-1])
    if cur_low <= float(window["low"].min()):   # 3a: higher low
        return None
    highs = window["high"].tolist()
    has_lower_high = any(
        highs[j] < highs[i]
        for i in range(len(highs))
        for j in range(i + 1, len(highs))
    )
    if not has_lower_high:                       # 3b: prior lower-high pair
        return None

    # 4: RS vs QQQ positive over 10 days
    rs_val = float(rs_vs_benchmark(bars, qqq_bars, 10).iloc[-1])
    if rs_val <= 0:
        return None

    # 5: reclaim — close > EMA10 and > EMA20
    if cur_close <= cur_ema10 or cur_close <= cur_ema20:
        return None

    # 6: volume >= 1.2× 20-day avg
    vol_ratio = volume_vs_avg(bars, 20)
    if vol_ratio < 1.2:
        return None

    entry_zone  = (cur_close, round(cur_close * 1.02, 4))
    stop_price  = float(max(cur_low, float(bars["low"].iloc[-4:-1].min())))
    first_target = prior_swing_high(bars, 60)
    raw_score   = min(3 + (1 if vol_ratio > 1.5 else 0) + (1 if rs_val > 0.02 else 0), 5)

    return SetupHit(
        ticker=ctx["ticker"],
        setup_kell="wedge_pop",
        cycle_stage="wedge_pop",
        entry_zone=entry_zone,
        stop_price=stop_price,
        first_target=first_target,
        second_target=None,
        detection_evidence={
            "ema10": round(cur_ema10, 4),
            "ema20": round(cur_ema20, 4),
            "ema10_slope": round(float(slope), 6),
            "rs_vs_qqq_10d": round(rs_val, 6),
            "volume_vs_20d_avg": round(vol_ratio, 4),
        },
        raw_score=raw_score,
    )
