"""Vomy Up Daily — bar-based proxy for the satyland Vomy bullish reversal.

Conditions on the latest daily bar:
  - overlay.bias_candle == "blue"          (Pivot Ribbon Pro buy-pullback)
  - overlay.above_48ema is True
  - overlay.ribbon_state in {"chopzilla", "bullish"}   (transitioning or completed)
  - phase_oscillator(today) > phase_oscillator(yesterday)   (rising)

Lane: transition. Role: trigger. Weight: 2.

The full satyland VomyEvaluator requires MTF scores + structure dicts the
screener doesn't have. We use the bar-based proxy above and rely on Task 23's
live-data smoke test to validate hit rates.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def _phase_pair(bars: pd.DataFrame) -> tuple[float, float] | None:
    """Return (prior, today) Phase Oscillator values, or None if uncomputable."""
    if len(bars) < 23:
        return None
    try:
        today = float(phase_oscillator(bars)["oscillator"])
        prior = float(phase_oscillator(bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError) as exc:
        logger.debug("phase_oscillator unavailable for vomy_up_daily: %s", exc)
        return None
    return prior, today


def vomy_up_daily_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        if overlay.bias_candle != "blue":
            continue
        if not overlay.above_48ema:
            continue
        if overlay.ribbon_state not in ("chopzilla", "bullish"):
            continue
        bars = bars_by_ticker[ticker]
        pair = _phase_pair(bars)
        if pair is None:
            continue
        prior, today = pair
        if not (today > prior):
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="vomy_up_daily",
            lane="transition", role="trigger",
            overlay=overlay, bars=bars,
            evidence={
                "bias_candle": overlay.bias_candle,
                "ribbon_state": overlay.ribbon_state,
                "phase_today": today,
                "phase_prior": prior,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_up_daily", lane="transition", role="trigger",
    mode="swing", fn=vomy_up_daily_scan, weight=2,
))
