"""Kell Exhaustion Extension adapter — stateless subset of the swing detector.

The full swing detector at api/indicators/swing/setups/exhaustion_extension.py
flags 4 conditions: kell_2nd_extension (history-dependent), climax_bar,
far_above_10ema, weekly_air. The screener can only evaluate the **stateless**
two — climax_bar and far_above_10ema — so we pass last_base_breakout_idx=None
and weekly=None.

Iterates `bars_by_ticker.items()` (not overlays) so it can skip QQQ
(benchmark, not a candidate). Tickers without overlays are skipped silently.

Lane: reversion. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.indicators.swing.setups.exhaustion_extension import (
    detect_exhaustion_extension,
)
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def kell_exhaustion_extension_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if ticker == "QQQ":
            continue
        overlay = overlays_by_ticker.get(ticker)
        if overlay is None:
            continue
        try:
            flag = detect_exhaustion_extension(bars, last_base_breakout_idx=None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("kell_exhaustion_extension: detector raised for %s: %s", ticker, exc)
            continue
        if not (flag.far_above_10ema or flag.climax_bar):
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="kell_exhaustion_extension",
            lane="reversion", role="trigger",
            overlay=overlay, bars=bars,
            evidence={
                "far_above_10ema": flag.far_above_10ema,
                "climax_bar": flag.climax_bar,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_exhaustion_extension", lane="reversion", role="trigger",
    mode="swing", fn=kell_exhaustion_extension_scan, weight=2,
))
