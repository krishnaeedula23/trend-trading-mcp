# api/indicators/swing/setups/exhaustion_extension.py
"""Exhaustion Extension detector — warning-only, runs in post-market pipeline.

Unlike the 5 detection-oriented setups in Plan 2, this does not create new ideas.
It flags risk on existing active ideas (status in 'watching'|'triggered'|'adding'|'trailing').

Triggers (spec §6.5, Kell source-notes §11):
  - Kell-direct: >= 2 extensions from 10-EMA since last base breakout (primary)
  - Kell-direct: climax volume (>= 2x avg 20d) + upper wick > 50% of day's range
  - Heuristic: close > 2 ATRs above 10-EMA
  - Heuristic: weekly close > 15% above 10-WSMA (caller feeds weekly df separately)

`last_base_breakout_idx` is the 0-based row index in `df` of the most recent
Base-n-Break detection (from `swing_events` history) — or None if none recorded.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from api.indicators.common.moving_averages import ema
from api.indicators.common.atr import atr


EXTENSION_ATR_THRESHOLD = 1.0      # "an extension" = close > 10-EMA + 1 ATR
FAR_ABOVE_ATR_MULT = 2.0           # heuristic: > 2 ATR above 10-EMA
CLIMAX_VOL_MULT = 2.0              # >= 2x avg 20d volume
CLIMAX_WICK_FRAC = 0.50            # upper wick > 50% of day's range
WEEKLY_AIR_PCT = 0.15              # close > 15% above weekly 10-SMA


@dataclass
class ExhaustionFlag:
    kell_2nd_extension: bool = False
    climax_bar: bool = False
    far_above_10ema: bool = False
    weekly_air: bool = False

    def any(self) -> bool:
        return any([self.kell_2nd_extension, self.climax_bar,
                    self.far_above_10ema, self.weekly_air])


def detect_exhaustion_extension(
    daily: pd.DataFrame,
    last_base_breakout_idx: int | None,
    weekly: pd.DataFrame | None = None,
) -> ExhaustionFlag:
    """Evaluate exhaustion triggers on the most recent daily bar.

    `daily` must have columns: open, high, low, close, volume (date index or column).
    """
    flag = ExhaustionFlag()
    if daily is None or len(daily) < 20:
        return flag

    ema10 = ema(daily, 10)
    atr14 = atr(daily, 14)
    last_close = float(daily["close"].iloc[-1])
    last_ema = float(ema10.iloc[-1])
    last_atr = float(atr14.iloc[-1])

    # Heuristic: far above 10-EMA (always check)
    if last_atr > 0 and (last_close - last_ema) > FAR_ABOVE_ATR_MULT * last_atr:
        flag.far_above_10ema = True

    # Climax bar: volume + upper wick
    last_vol = float(daily["volume"].iloc[-1])
    avg_vol = float(daily["volume"].tail(20).mean())
    last_high = float(daily["high"].iloc[-1])
    last_low = float(daily["low"].iloc[-1])
    rng = last_high - last_low
    if rng > 0 and avg_vol > 0:
        upper_wick = last_high - max(last_close, float(daily["open"].iloc[-1]))
        if last_vol >= CLIMAX_VOL_MULT * avg_vol and upper_wick / rng >= CLIMAX_WICK_FRAC:
            flag.climax_bar = True

    # Kell 2nd+ extension: count closes that poked > 1 ATR above 10-EMA since breakout
    if last_base_breakout_idx is not None and last_base_breakout_idx < len(daily) - 1:
        post = daily.iloc[last_base_breakout_idx + 1:]
        post_ema = ema10.iloc[last_base_breakout_idx + 1:]
        post_atr = atr14.iloc[last_base_breakout_idx + 1:]
        extension_count = 0
        in_extension = False
        for close_i, ema_i, atr_i in zip(post["close"], post_ema, post_atr):
            if atr_i <= 0:
                continue
            is_ext = (close_i - ema_i) > EXTENSION_ATR_THRESHOLD * atr_i
            if is_ext and not in_extension:
                extension_count += 1
                in_extension = True
            elif not is_ext:
                in_extension = False
        if extension_count >= 2:
            flag.kell_2nd_extension = True

    # Weekly Air (heuristic)
    if weekly is not None and len(weekly) >= 10:
        wsma10 = weekly["close"].tail(10).mean()
        last_weekly_close = float(weekly["close"].iloc[-1])
        if wsma10 > 0 and (last_weekly_close - wsma10) / wsma10 > WEEKLY_AIR_PCT:
            flag.weekly_air = True

    return flag
