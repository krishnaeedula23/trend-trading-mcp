"""Vomy Up Hourly — same logic as vomy_up_daily but on 60m bars.

Conditions on the latest hourly bar:
  - hourly Pivot Ribbon bias_candle == "blue"
  - hourly close >= hourly EMA48
  - hourly ribbon_state in {"chopzilla", "bullish"}
  - hourly phase_oscillator rising

Reads from the runner's `hourly_bars_by_ticker` dict. Skips silently when no
hourly bars are available for a ticker.

Lane: transition. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def _evaluate_ticker(hourly_bars: pd.DataFrame) -> dict | None:
    """Run the 4-condition Vomy Up gate on hourly bars; return evidence or None."""
    if len(hourly_bars) < 50:
        return None
    try:
        pr = pivot_ribbon(hourly_bars)
        if pr["bias_candle"] != "blue":
            return None
        if not pr["above_48ema"]:
            return None
        if pr["ribbon_state"] not in ("chopzilla", "bullish"):
            return None
        today = float(phase_oscillator(hourly_bars)["oscillator"])
        prior = float(phase_oscillator(hourly_bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError) as exc:
        logger.debug("pivot_ribbon/phase_oscillator unavailable for vomy_up_hourly: %s", exc)
        return None
    if not (today > prior):
        return None
    return {
        "bias_candle": pr["bias_candle"],
        "ribbon_state": pr["ribbon_state"],
        "phase_today_hourly": today,
        "phase_prior_hourly": prior,
    }


def vomy_up_hourly_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, hb in hourly_bars_by_ticker.items():
        # Daily overlay still needed for make_hit's evidence enrichment (close, dollar_volume_today
        # come from the daily bars). Look up daily bars + overlay; skip ticker if either missing.
        if ticker not in bars_by_ticker or ticker not in overlays_by_ticker:
            continue
        ev = _evaluate_ticker(hb)
        if ev is None:
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="vomy_up_hourly",
            lane="transition", role="trigger",
            overlay=overlays_by_ticker[ticker],
            bars=bars_by_ticker[ticker],
            evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_up_hourly", lane="transition", role="trigger",
    mode="swing", fn=vomy_up_hourly_scan, weight=2,
))
