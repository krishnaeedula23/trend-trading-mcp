"""Tests for Kell Exhaustion Extension adapter."""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import (
    force_register_scan_module,
    make_daily_bars,
    scan_fn_by_id,
)


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.kell_exhaustion_extension")


def _scan_fn():
    return scan_fn_by_id("kell_exhaustion_extension")


def test_kell_exhaustion_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_exhaustion_extension")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "reversion"
    assert desc.role == "trigger"


def test_kell_exhaustion_skips_when_no_extension():
    """Flat bars → no extension → no fire."""
    _force_register()
    closes = [100.0] * 60
    bars = make_daily_bars(closes=closes)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn()
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_kell_exhaustion_fires_on_far_above_10ema():
    """Bars where last close is > 2 ATR above EMA10 → far_above_10ema flag fires."""
    _force_register()
    n = 60
    # Steep climax: 55 flat bars at 100, then 5 vertical bars 110, 115, 120, 130, 150
    closes = [100.0] * (n - 5) + [110.0, 115.0, 120.0, 130.0, 150.0]
    bars = make_daily_bars(closes=closes, high_mult=1.01, low_mult=0.99)
    overlays = {"NVDA": compute_overlay(bars)}
    fn = _scan_fn()
    hits = fn({"NVDA": bars}, overlays, {})
    assert len(hits) == 1
    hit = hits[0]
    assert hit.scan_id == "kell_exhaustion_extension"
    assert hit.lane == "reversion"
    assert hit.role == "trigger"
    assert hit.evidence["far_above_10ema"] is True


def test_kell_exhaustion_skips_qqq():
    """QQQ should be skipped — it's a benchmark, not a candidate."""
    _force_register()
    closes = [100.0] * 55 + [110.0, 115.0, 120.0, 130.0, 150.0]   # would normally fire
    bars = make_daily_bars(closes=closes)
    overlays = {"QQQ": compute_overlay(bars)}
    fn = _scan_fn()
    assert fn({"QQQ": bars}, overlays, {}) == []


def test_kell_exhaustion_skips_when_overlay_missing():
    """Ticker in bars but not overlays (e.g., <50 bars) → skip silently."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    # Note: bars_by_ticker has AAPL, but overlays_by_ticker is empty
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {}, {}) == []
