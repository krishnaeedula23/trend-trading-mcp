"""Vomy Down at extension highs — bearish reversal trigger near climax.

Conditions on the latest daily bar:
  - bias_candle == "orange"
  - not above_48ema
  - ribbon_state in {"chopzilla", "bearish"}
  - phase_oscillator falling (today < yesterday)
  - overlay.extension > 7

Lane: reversion. Role: trigger. Weight: 2.

The phase oscillator "today" value is read from overlay.phase_oscillator
(cached by compute_overlay) — only "yesterday" is recomputed via
phase_oscillator(bars.iloc[:-1]). This halves the per-ticker phase work
and eliminates drift between the overlay's degraded-fallback path and
the scan's narrow-exception path.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)

EXTENSION_MIN = 7.0


def _phase_pair(bars: pd.DataFrame, overlay: IndicatorOverlay) -> tuple[float, float] | None:
    """Return (prior, today) Phase Oscillator values, or None if uncomputable."""
    if len(bars) < 23:
        return None
    try:
        prior = float(phase_oscillator(bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError) as exc:
        logger.debug("phase_oscillator unavailable for vomy_down_extension prior bar: %s", exc)
        return None
    return prior, overlay.phase_oscillator


def vomy_down_extension_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        if overlay.bias_candle != "orange":
            continue
        if overlay.above_48ema:
            continue
        if overlay.ribbon_state not in ("chopzilla", "bearish"):
            continue
        if overlay.extension <= EXTENSION_MIN:
            continue
        bars = bars_by_ticker[ticker]
        pair = _phase_pair(bars, overlay)
        if pair is None:
            continue
        prior, today = pair
        if not (today < prior):
            continue
        hits.append(make_hit(
            ticker=ticker, scan_id="vomy_down_extension",
            lane="reversion", role="trigger",
            overlay=overlay, bars=bars,
            evidence={
                "bias_candle": overlay.bias_candle,
                "ribbon_state": overlay.ribbon_state,
                "extension": overlay.extension,
                "phase_today": today,
                "phase_prior": prior,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_down_extension", lane="reversion", role="trigger",
    mode="swing", fn=vomy_down_extension_scan, weight=2,
))
