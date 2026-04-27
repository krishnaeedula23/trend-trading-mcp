"""Qullamaggie Episodic Pivot — high-conviction breakout trigger.

Conditions on the latest daily bar:
  - pct_change_today > 7.5%
  - close > yesterday's high
  - dollar_volume_today > $100M

Lane: breakout. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


PCT_CHANGE_MIN = 0.075
DOLLAR_VOLUME_MIN = 100_000_000.0


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 2:
        return None
    yesterday_high = float(bars["high"].iloc[-2])
    last_close = float(bars["close"].iloc[-1])
    if overlay.pct_change_today <= PCT_CHANGE_MIN:
        return None
    if last_close <= yesterday_high:
        return None
    if overlay.dollar_volume_today <= DOLLAR_VOLUME_MIN:
        return None
    return {
        "pct_change_today": overlay.pct_change_today,
        "yesterday_high": yesterday_high,
    }


def qullamaggie_episodic_pivot_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker[ticker]
        evidence = _check(bars, overlay)
        if evidence is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="qullamaggie_episodic_pivot",
            lane="breakout", role="trigger",
            overlay=overlay, bars=bars,
            evidence=evidence,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="qullamaggie_episodic_pivot", lane="breakout", role="trigger",
    mode="swing", fn=qullamaggie_episodic_pivot_scan, weight=2,
))
