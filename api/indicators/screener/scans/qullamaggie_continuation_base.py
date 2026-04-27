"""Qullamaggie Continuation Base — pullback to 10-SMA on a leader, volume drying.

Conditions on the latest daily bar:
  - last_close > $5
  - volume_avg_50d > 300_000
  - adr_pct_20d > 4%
  - |last_close - SMA10| / SMA10 <= 2%
  - sum(volume[-5:]) / sum(volume[-10:-5]) < 0.5

Lane: breakout. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


MIN_PRICE = 5.0
MIN_VOLUME_AVG_50D = 300_000.0
MIN_ADR_PCT = 0.04
MAX_DIST_FROM_10SMA = 0.02
MAX_RECENT_VOLUME_RATIO = 0.5


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 10:
        return None
    last_close = float(bars["close"].iloc[-1])
    if last_close <= MIN_PRICE:
        return None
    if overlay.volume_avg_50d <= MIN_VOLUME_AVG_50D:
        return None
    if overlay.adr_pct_20d <= MIN_ADR_PCT:
        return None
    sma10 = float(bars["close"].rolling(10).mean().iloc[-1])
    if sma10 <= 0:
        return None
    if abs(last_close - sma10) / sma10 > MAX_DIST_FROM_10SMA:
        return None
    last_5_vol = float(bars["volume"].iloc[-5:].sum())
    prior_5_vol = float(bars["volume"].iloc[-10:-5].sum())
    if prior_5_vol <= 0:
        return None
    ratio = last_5_vol / prior_5_vol
    if ratio >= MAX_RECENT_VOLUME_RATIO:
        return None
    return {
        "sma10": sma10,
        "dist_from_sma10_pct": abs(last_close - sma10) / sma10,
        "adr_pct_20d": overlay.adr_pct_20d,
        "last_5d_volume_ratio": ratio,
    }


def qullamaggie_continuation_base_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker[ticker]
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="qullamaggie_continuation_base",
            lane="breakout", role="setup_ready",
            overlay=overlay, bars=bars,
            evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="qullamaggie_continuation_base", lane="breakout", role="setup_ready",
    mode="swing", fn=qullamaggie_continuation_base_scan, weight=1,
))
