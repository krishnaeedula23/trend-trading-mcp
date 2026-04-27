"""Kell Flag Base — tight consolidation following a strong impulse leg.

Conditions on the latest daily bar:
  - bars >= 30
  - ribbon_state == "bullish" AND above_48ema
  - prior 15-bar impulse window (bars[-25:-5]) shows >= 15% net move
  - last 5 bars: (max(high) - min(low)) / mean(close) < 5%
  - mean(volume[-5:]) < 0.8 * mean(volume[-25:-5])

Lane: breakout. Role: setup_ready. Weight: 1.

This is a NEW detector — Plan 2 does not have an existing swing-pipeline
equivalent for Kell's "Base-n-Break" pre-trigger.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


IMPULSE_LOOKBACK_START = -25
IMPULSE_LOOKBACK_END = -5
IMPULSE_MIN_PCT = 0.15
BASE_WINDOW = 5
BASE_MAX_RANGE_PCT = 0.05
VOLUME_DRYING_RATIO = 0.8


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 30:
        return None
    if overlay.ribbon_state != "bullish" or not overlay.above_48ema:
        return None

    impulse_window = bars.iloc[IMPULSE_LOOKBACK_START:IMPULSE_LOOKBACK_END]
    if len(impulse_window) < 10:
        return None
    start = float(impulse_window["close"].iloc[0])
    peak = float(impulse_window["close"].max())
    if start <= 0:
        return None
    impulse_pct = (peak / start) - 1.0
    if impulse_pct < IMPULSE_MIN_PCT:
        return None

    base = bars.iloc[-BASE_WINDOW:]
    base_range = float(base["high"].max() - base["low"].min())
    base_mean = float(base["close"].mean())
    if base_mean <= 0:
        return None
    base_range_pct = base_range / base_mean
    if base_range_pct >= BASE_MAX_RANGE_PCT:
        return None

    base_vol = float(base["volume"].mean())
    impulse_vol = float(impulse_window["volume"].mean())
    if impulse_vol <= 0:
        return None
    vol_ratio = base_vol / impulse_vol
    if vol_ratio >= VOLUME_DRYING_RATIO:
        return None

    return {
        "impulse_pct": impulse_pct,
        "base_range_pct": base_range_pct,
        "base_volume_ratio": vol_ratio,
    }


def kell_flag_base_scan(
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
            ticker=ticker, scan_id="kell_flag_base",
            lane="breakout", role="setup_ready",
            overlay=overlay, bars=bars,
            evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_flag_base", lane="breakout", role="setup_ready",
    mode="swing", fn=kell_flag_base_scan, weight=1,
))
