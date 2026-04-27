"""Saty Golden Gate Up — Day / Multiday / Swing variants.

For each mode read overlay.saty_levels_by_mode[mode]:
    golden_gate_bull <= last_close < fib_786_bull

Fires a hit with scan_id 'saty_golden_gate_up_<mode>'. Skips silently when the
levels dict is missing for that mode.

Lane: breakout. Role: trigger. Weight: 3 each.

Note: `mode` here is the Saty timeframe (day/multiday/swing), not the runner's
`Mode` literal which gates which screener run includes us — descriptors all
register with `mode="swing"` (runner-side gate).
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


_MODES = ("day", "multiday", "swing")


def _make_scan(mode: str):
    scan_id = f"saty_golden_gate_up_{mode}"

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
            levels = levels_dict.get("levels", {})
            gg = levels.get("golden_gate_bull", {}).get("price")
            f786 = levels.get("fib_786_bull", {}).get("price")
            if gg is None or f786 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if not (gg <= last_close < f786):
                continue
            hits.append(make_hit(
                ticker=ticker, scan_id=scan_id,
                lane="breakout", role="trigger",
                overlay=overlay, bars=bars,
                evidence={
                    "mode": mode,
                    "golden_gate": gg,
                    "fib_786": f786,
                },
            ))
        return hits

    return scan_fn


for _mode in _MODES:
    register_scan(ScanDescriptor(
        scan_id=f"saty_golden_gate_up_{_mode}",
        lane="breakout", role="trigger", mode="swing",
        fn=_make_scan(_mode), weight=3,
    ))
