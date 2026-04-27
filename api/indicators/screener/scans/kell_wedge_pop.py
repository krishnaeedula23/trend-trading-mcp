"""Kell Wedge Pop — adapter around api/indicators/swing/setups/wedge_pop.py.

The existing detector requires QQQ bars for relative-strength comparison. The
endpoint always fetches QQQ alongside the universe; we read it out of
bars_by_ticker. If QQQ is missing, every scan returns empty.

This scan is unique among the screener catalog because it iterates
`bars_by_ticker.items()` (not `overlays_by_ticker`) so it can filter out
"QQQ" itself from being evaluated as a hit candidate against itself.

Lane: breakout. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.indicators.swing.setups.wedge_pop import detect as wedge_pop_detect
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def kell_wedge_pop_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    qqq = bars_by_ticker.get("QQQ")
    if qqq is None:
        return []
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if ticker == "QQQ":
            continue
        overlay = overlays_by_ticker.get(ticker)
        if overlay is None:
            continue
        try:
            setup_hit = wedge_pop_detect(bars, qqq, {"ticker": ticker})
        except Exception as exc:  # noqa: BLE001
            logger.debug("kell_wedge_pop: detector raised for %s: %s", ticker, exc)
            continue
        if setup_hit is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="kell_wedge_pop",
            lane="breakout", role="setup_ready",
            overlay=overlay, bars=bars,
            evidence=dict(setup_hit.detection_evidence),
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_wedge_pop", lane="breakout", role="setup_ready",
    mode="swing", fn=kell_wedge_pop_scan, weight=1,
))
