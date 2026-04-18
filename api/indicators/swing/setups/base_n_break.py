"""Base-n-Break setup detector — tight consolidation breakout with volume confirmation."""
from __future__ import annotations

import pandas as pd

from api.indicators.common.moving_averages import ema
from api.indicators.swing.setups.base import SetupHit, volume_vs_avg


def detect(bars: pd.DataFrame, qqq_bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
    """Return SetupHit if Base-n-Break fires on the current (last) bar, else None."""
    # Need at least 26 bars: 25 base + 1 current
    if len(bars) < 26:
        return None

    # Slice base: up to 40 bars immediately before current bar
    base = bars.iloc[-41:-1]
    if len(base) < 25:
        return None

    base_high = float(base["high"].max())
    base_low = float(base["low"].min())
    mid_price = (base_high + base_low) / 2

    # Rule 2: base tightness < 15%
    tightness = (base_high - base_low) / mid_price
    if tightness >= 0.15:
        return None

    # Rule 3: every base bar closes above EMA10 and EMA20
    ema10 = ema(bars, 10)
    ema20 = ema(bars, 20)

    # Align base indices to get the corresponding EMA slice
    base_ema10 = ema10.iloc[-41:-1].iloc[-len(base):]
    base_ema20 = ema20.iloc[-41:-1].iloc[-len(base):]

    base_closes = base["close"].values
    if not ((base_closes > base_ema10.values) & (base_closes > base_ema20.values)).all():
        return None

    cur_close = float(bars["close"].iloc[-1])

    # Rule 4: breakout close above base_high
    if cur_close <= base_high:
        return None

    # Rule 5: volume >= 1.5× 20-day avg
    vol_ratio = volume_vs_avg(bars, 20)
    if vol_ratio < 1.5:
        return None

    base_len = len(base)
    base_range = base_high - base_low
    cur_ema20 = float(ema20.iloc[-1])

    entry_zone = (cur_close, round(cur_close * 1.02, 4))
    stop_price = float(max(base_low, cur_ema20))
    first_target = round(cur_close + base_range, 4)

    raw_score = 3
    if tightness < 0.10:
        raw_score += 1
    if vol_ratio > 2.0:
        raw_score += 1
    raw_score = min(raw_score, 5)

    return SetupHit(
        ticker=ctx["ticker"],
        setup_kell="base_n_break",
        cycle_stage="base_n_break",
        entry_zone=entry_zone,
        stop_price=stop_price,
        first_target=first_target,
        second_target=None,
        detection_evidence={
            "base_length": base_len,
            "base_high": round(base_high, 4),
            "base_low": round(base_low, 4),
            "base_tightness_pct": round(tightness, 6),
            "volume_vs_20d_avg": round(vol_ratio, 4),
        },
        raw_score=raw_score,
    )
