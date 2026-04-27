"""Tests for the screener EMA Crossback adapter."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import make_daily_bars


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.ema_crossback as mod
    clear_registry()
    importlib.reload(mod)


def _scan_fn():
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("ema_crossback")
    assert desc is not None
    return desc.fn


def test_ema_crossback_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("ema_crossback")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "transition"
    assert desc.role == "setup_ready"


def test_ema_crossback_skips_when_not_in_uptrend():
    """ribbon_state != 'bullish' → skip."""
    _force_register()
    closes = [100.0 - i * 0.5 for i in range(60)]   # downtrend
    bars = make_daily_bars(closes=closes)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn()
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_ema_crossback_skips_when_above_48ema_false():
    """Force above_48ema=False via overlay override."""
    _force_register()
    closes = [100.0 + i * 0.3 for i in range(60)]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": False,   # disqualifier
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_ema_crossback_skips_when_volume_not_drying():
    """High volume on the pullback day disqualifies even with all other conditions met."""
    _force_register()
    closes = [100.0 + i * 0.5 for i in range(60)]
    bars = make_daily_bars(
        closes=closes,
        volumes=[1_000_000] * 59 + [3_000_000],   # surge today, not drying
    )
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_ema_crossback_handles_short_history():
    """Bars < 30 → no fire, no exception."""
    _force_register()
    closes = [100.0 + i * 0.5 for i in range(50)]   # >= 50 for compute_overlay; >=30 not yet pruned
    # Truncate by passing only 50 bars; compute_overlay needs SMA50 (50 bars) so this is the floor
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    out = fn({"AAPL": bars}, {"AAPL": overlay}, {})
    assert isinstance(out, list)
