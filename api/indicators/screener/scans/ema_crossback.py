"""EMA Crossback (screener-side, stateless).

Detects a healthy pullback to EMA10/20 in an established uptrend. Unlike the
swing-pipeline detector, we do NOT require a prior Wedge Pop in history —
that gate exists in the swing pipeline; the screener's job is to surface
candidates regardless of upstream history.

Conditions on the latest daily bar:
  - bars >= 30
  - ribbon_state == "bullish" AND above_48ema
  - close within 0.5 × ATR of EMA10 or EMA20 (whichever is closer)
  - bar's low > respected EMA
  - volume / 20-day avg < 0.8

Lane: transition. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.common.atr import atr as atr_series
from api.indicators.common.moving_averages import ema as ema_series
from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.indicators.swing.setups.base import volume_vs_avg
from api.schemas.screener import IndicatorOverlay, ScanHit


HALF_ATR = 0.5
MAX_VOLUME_RATIO = 0.8


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 30:
        return None
    if overlay.ribbon_state != "bullish" or not overlay.above_48ema:
        return None
    ema10 = ema_series(bars, 10)
    ema20 = ema_series(bars, 20)
    atr14 = atr_series(bars, 14)
    cur_close = float(bars["close"].iloc[-1])
    cur_low = float(bars["low"].iloc[-1])
    cur_atr = float(atr14.iloc[-1])
    cur_e10 = float(ema10.iloc[-1])
    cur_e20 = float(ema20.iloc[-1])
    if cur_atr <= 0:
        return None

    dist10 = abs(cur_close - cur_e10)
    dist20 = abs(cur_close - cur_e20)
    if dist10 <= dist20:
        respected, respected_val, respected_dist = "ema10", cur_e10, dist10
    else:
        respected, respected_val, respected_dist = "ema20", cur_e20, dist20
    if respected_dist >= HALF_ATR * cur_atr:
        return None
    if cur_low <= respected_val:
        return None

    try:
        vol_ratio = volume_vs_avg(bars, 20)
    except ValueError:
        return None
    if vol_ratio >= MAX_VOLUME_RATIO:
        return None

    return {
        "respected_ema": respected,
        "dist_to_ema_atr": respected_dist / cur_atr,
        "volume_vs_20d_avg": vol_ratio,
    }


def ema_crossback_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker[ticker]
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="ema_crossback",
            lane="transition", role="setup_ready",
            overlay=overlay, bars=bars,
            evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="ema_crossback", lane="transition", role="setup_ready",
    mode="swing", fn=ema_crossback_scan, weight=1,
))
