"""Reversal Extension setup detector — capitulation near HTF support with divergence."""
from __future__ import annotations

import pandas as pd

from api.indicators.common.atr import atr
from api.indicators.common.moving_averages import ema, sma, weekly_resample
from api.indicators.common.phase_oscillator import phase_oscillator_daily
from api.indicators.swing.setups.base import SetupHit, volume_vs_avg


def detect(bars: pd.DataFrame, qqq_bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
    """Return SetupHit if Reversal Extension fires on the current (last) bar, else None."""
    if len(bars) < 200:
        return None

    close = bars["close"]
    cur_close = float(close.iloc[-1])
    cur_low = float(bars["low"].iloc[-1])

    ema10 = ema(bars, 10)
    ema20 = ema(bars, 20)
    sma200 = sma(bars, 200)
    atr14 = atr(bars, 14)

    cur_ema10 = float(ema10.iloc[-1])
    cur_ema20 = float(ema20.iloc[-1])
    cur_sma200 = float(sma200.iloc[-1])
    cur_atr = float(atr14.iloc[-1])

    # --- Rule 1: Higher-TF support proximity (any of three) ---
    dist_sma200 = abs(cur_close - cur_sma200) / cur_sma200
    near_sma200 = dist_sma200 < 0.03

    weekly = weekly_resample(bars)
    ema10w = ema(weekly, 10)
    cur_10w_ema = float(ema10w.iloc[-1])
    dist_10w_ema = abs(cur_close - cur_10w_ema) / cur_10w_ema
    near_10w_ema = dist_10w_ema < 0.03

    w_lookback = min(20, len(weekly))
    weekly_base_low = float(weekly["low"].iloc[-w_lookback:].min())
    dist_weekly_low = abs(cur_close - weekly_base_low) / weekly_base_low if weekly_base_low != 0 else 1.0
    near_weekly_low = dist_weekly_low < 0.03

    if near_sma200:
        support_type = "sma200"
    elif near_10w_ema:
        support_type = "10w_ema"
    elif near_weekly_low:
        support_type = "weekly_low"
    else:
        return None

    # --- Rule 2: Capitulation volume ---
    vol_ratio = volume_vs_avg(bars, 20)
    if vol_ratio <= 1.5:
        return None

    # --- Rule 3: Phase oscillator oversold ---
    phase_osc = phase_oscillator_daily(bars)
    cur_phase = float(phase_osc.iloc[-1])
    if cur_phase > -50:
        return None

    # --- Rule 4: Price stretched below EMA10 ---
    stretch = cur_ema10 - cur_close
    if stretch <= 1.5 * cur_atr:
        return None

    # --- Rule 5: Bullish divergence over last 10 bars ---
    window_close = close.iloc[-10:]
    window_osc = phase_osc.iloc[-10:]

    # Price: current bar is the lowest in the window
    if not (float(window_close.iloc[-1]) < float(window_close.iloc[:-1].min())):
        return None

    # Oscillator: current bar is NOT the lowest in the window (it has turned up)
    if not (float(window_osc.iloc[-1]) > float(window_osc.iloc[:-1].min())):
        return None

    # --- Score ---
    raw_score = 3
    if cur_phase < -70:
        raw_score += 1
    if vol_ratio > 2.0:
        raw_score += 1
    raw_score = min(raw_score, 5)

    dist_ema10_atr = stretch / cur_atr if cur_atr else 0.0

    return SetupHit(
        ticker=ctx["ticker"],
        setup_kell="reversal_extension",
        cycle_stage="reversal_extension",
        entry_zone=(round(cur_close * 0.995, 4), round(cur_close * 1.01, 4)),
        stop_price=cur_low,
        first_target=cur_ema20,
        second_target=None,
        detection_evidence={
            "dist_to_sma200_pct": round(dist_sma200, 6),
            "dist_to_ema10_atr": round(dist_ema10_atr, 4),
            "phase_osc": round(cur_phase, 4),
            "volume_vs_20d_avg": round(vol_ratio, 4),
            "support_type": support_type,
        },
        raw_score=raw_score,
    )
