"""Saty Trigger Up — Day / Multiday / Swing variants.

For each mode we read the per-mode ATR Levels dict from
overlay.saty_levels_by_mode[mode] and check:

    call_trigger < last_close < mid_50_bull

Fires a hit with scan_id 'saty_trigger_up_<mode>'. Skips silently when the
levels dict is missing for that mode (insufficient resampled history).

Lane: breakout. Role: trigger. Weight: 3 each.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


_MODES = ("day", "multiday", "swing")


def _make_scan(mode: str):
    scan_id = f"saty_trigger_up_{mode}"

    def scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
    ) -> list[ScanHit]:
        hits: list[ScanHit] = []
        for ticker, overlay in overlays_by_ticker.items():
            bars = bars_by_ticker[ticker]
            levels_dict = overlay.saty_levels_by_mode.get(mode)
            if not levels_dict:
                continue
            call_trigger = levels_dict.get("call_trigger")
            levels = levels_dict.get("levels", {})
            mid_50 = levels.get("mid_50_bull", {}).get("price")
            if call_trigger is None or mid_50 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if not (call_trigger < last_close < mid_50):
                continue
            hits.append(make_hit(
                ticker=ticker, scan_id=scan_id,
                lane="breakout", role="trigger",
                overlay=overlay, bars=bars,
                evidence={
                    "mode": mode,
                    "call_trigger": call_trigger,
                    "mid_50_bull": mid_50,
                },
            ))
        return hits

    return scan_fn


for _mode in _MODES:
    register_scan(ScanDescriptor(
        scan_id=f"saty_trigger_up_{_mode}",
        lane="breakout", role="trigger", mode="swing",
        fn=_make_scan(_mode), weight=3,
    ))
