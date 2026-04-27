"""Saty Trigger Down (Day) — mirror of Saty Trigger Up Day for reversion lane.

Reads overlay.saty_levels_by_mode["day"]. Conditions:
    mid_50_bear < last_close < put_trigger

Fires a hit with scan_id 'saty_trigger_down_day'. Skips silently when the
day-mode levels dict is missing.

Lane: reversion. Role: trigger. Weight: 3.

We ship only the Day variant in Plan 2; Multiday/Swing down variants can be
added later if needed.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


def saty_trigger_down_day_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        levels_dict = overlay.saty_levels_by_mode.get("day")
        if not levels_dict:
            continue
        put_trigger = levels_dict.get("put_trigger")
        levels = levels_dict.get("levels", {})
        mid_50_bear = levels.get("mid_50_bear", {}).get("price")
        if put_trigger is None or mid_50_bear is None:
            continue
        bars = bars_by_ticker[ticker]
        last_close = float(bars["close"].iloc[-1])
        if not (mid_50_bear < last_close < put_trigger):
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="saty_trigger_down_day",
            lane="reversion", role="trigger",
            overlay=overlay, bars=bars,
            evidence={
                "put_trigger": put_trigger,
                "mid_50_bear": mid_50_bear,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="saty_trigger_down_day",
    lane="reversion", role="trigger", mode="swing",
    fn=saty_trigger_down_day_scan, weight=3,
))
