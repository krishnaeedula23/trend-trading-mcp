"""EMA Crossback setup detector — pullback to EMA10/20 following a prior Wedge Pop."""
from __future__ import annotations

import pandas as pd

from api.indicators.common.atr import atr
from api.indicators.common.moving_averages import ema
from api.indicators.swing.setups.base import SetupHit, prior_swing_high, volume_vs_avg


def detect(bars: pd.DataFrame, qqq_bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
    """Return SetupHit if EMA Crossback fires on the current (last) bar, else None.

    ctx["prior_ideas"]: list of dicts representing prior swing_ideas rows for this
    ticker. Each must have at least keys 'setup_kell' and 'detected_at'.
    """
    if len(bars) < 30:
        return None

    # 1: Prior Wedge Pop within last 30 bars
    cutoff_date = pd.to_datetime(bars["date"].iloc[-30]).tz_localize(None)
    has_prior = any(
        p.get("setup_kell") == "wedge_pop"
        and pd.to_datetime(p["detected_at"]).tz_localize(None) >= cutoff_date
        for p in ctx.get("prior_ideas", [])
    )
    if not has_prior:
        return None

    ema10  = ema(bars, 10)
    ema20  = ema(bars, 20)
    atr14  = atr(bars, 14)

    cur_close  = float(bars["close"].iloc[-1])
    cur_low    = float(bars["low"].iloc[-1])
    cur_atr    = float(atr14.iloc[-1])
    cur_ema10  = float(ema10.iloc[-1])
    cur_ema20  = float(ema20.iloc[-1])

    # 2: Close within 0.5×ATR of EMA10 or EMA20; pick the closer one
    dist10 = abs(cur_close - cur_ema10)
    dist20 = abs(cur_close - cur_ema20)
    half_atr = 0.5 * cur_atr

    if dist10 <= dist20:
        respected_ema_name = "ema10"
        respected_ema_val  = cur_ema10
        dist_to_ema        = dist10
    else:
        respected_ema_name = "ema20"
        respected_ema_val  = cur_ema20
        dist_to_ema        = dist20

    if dist_to_ema >= half_atr:
        return None

    # 3: Low of pullback bar holds strictly above the respected EMA
    if cur_low <= respected_ema_val:
        return None

    # 4: Volume drying up — < 0.8× 20-day avg
    vol_ratio = volume_vs_avg(bars, 20)
    if vol_ratio >= 0.8:
        return None

    # Find detected_at for the matched prior wedge (first match for evidence)
    prior_wedge_at = next(
        p["detected_at"]
        for p in ctx.get("prior_ideas", [])
        if p.get("setup_kell") == "wedge_pop"
        and pd.to_datetime(p["detected_at"]).tz_localize(None) >= cutoff_date
    )
    # Normalise to ISO date string
    prior_wedge_at_str = str(pd.to_datetime(prior_wedge_at).date())

    dist_atr_ratio = dist_to_ema / cur_atr if cur_atr else 0.0

    raw_score = 3
    if vol_ratio < 0.6:
        raw_score += 1
    if dist_atr_ratio < 0.2:
        raw_score += 1
    raw_score = min(raw_score, 5)

    return SetupHit(
        ticker=ctx["ticker"],
        setup_kell="ema_crossback",
        cycle_stage="ema_crossback",
        entry_zone=(cur_close, round(cur_close * 1.015, 4)),
        stop_price=cur_low,
        first_target=prior_swing_high(bars, 60),
        second_target=None,
        detection_evidence={
            "respected_ema": respected_ema_name,
            "dist_to_ema_atr": round(dist_atr_ratio, 4),
            "volume_vs_20d_avg": round(vol_ratio, 4),
            "prior_wedge_at": prior_wedge_at_str,
        },
        raw_score=raw_score,
    )
