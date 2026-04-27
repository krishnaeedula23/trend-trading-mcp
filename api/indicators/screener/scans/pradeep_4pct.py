"""Pradeep 4% Breakout (bullish) — daily bar trigger.

Conditions on the latest daily bar:
  - pct_change_today > 4%
  - today's volume > yesterday's volume
  - today's volume > 100_000

Lane: breakout. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


PCT_CHANGE_MIN = 0.04
MIN_VOLUME = 100_000


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 2:
        return None
    today_vol = float(bars["volume"].iloc[-1])
    yesterday_vol = float(bars["volume"].iloc[-2])
    if overlay.pct_change_today <= PCT_CHANGE_MIN:
        return None
    if today_vol <= yesterday_vol:
        return None
    if today_vol <= MIN_VOLUME:
        return None
    return {
        "pct_change_today": overlay.pct_change_today,
        "volume_today": today_vol,
        "volume_yesterday": yesterday_vol,
    }


def pradeep_4pct_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker[ticker]
        evidence = _check(bars, overlay)
        if evidence is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="pradeep_4pct_breakout",
            lane="breakout", role="trigger",
            overlay=overlay, bars=bars,
            evidence=evidence,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="pradeep_4pct_breakout", lane="breakout", role="trigger",
    mode="swing", fn=pradeep_4pct_scan, weight=2,
))
