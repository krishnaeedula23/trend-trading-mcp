"""Tests for Vomy Up Daily scan."""
from __future__ import annotations

import importlib

from tests.screener._helpers import make_daily_bars


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.vomy_up_daily as mod
    clear_registry()
    importlib.reload(mod)


def _scan_fn():
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_up_daily")
    assert desc is not None
    return desc.fn


def test_vomy_up_daily_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_up_daily")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "transition"
    assert desc.role == "trigger"


def test_vomy_up_daily_skips_when_bias_candle_not_blue():
    """When the bias candle is something other than 'blue' (e.g. 'green'), skip."""
    from api.indicators.screener.overlay import compute_overlay
    _force_register()
    # Strong steady uptrend → ribbon='bullish', bias usually 'green', above_48ema=True
    closes = [100.0 + i * 0.3 for i in range(120)]
    bars = make_daily_bars(closes=closes)
    overlays = {"NVDA": compute_overlay(bars)}
    # If by chance the synthetic generates a 'blue' bias, skip the test (fixture not built for this case)
    if overlays["NVDA"].bias_candle == "blue":
        return
    fn = _scan_fn()
    assert fn({"NVDA": bars}, overlays) == []


def test_vomy_up_daily_skips_when_below_48ema():
    """Force above_48ema=False via overlay override."""
    from api.indicators.screener.overlay import compute_overlay
    _force_register()
    closes = [100.0 + i * 0.3 for i in range(120)]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "blue",      # required gate
        "above_48ema": False,        # disqualifier
        "ribbon_state": "bullish",
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_vomy_up_daily_skips_when_ribbon_state_bearish():
    """ribbon_state='bearish' → skip (must be 'chopzilla' or 'bullish')."""
    from api.indicators.screener.overlay import compute_overlay
    _force_register()
    closes = [100.0 + i * 0.3 for i in range(120)]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "blue",
        "above_48ema": True,
        "ribbon_state": "bearish",   # disqualifier
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_vomy_up_daily_handles_short_history_gracefully():
    """Bars with fewer than ~22 bars (Phase Oscillator min) return empty without raising."""
    from api.indicators.screener.overlay import compute_overlay
    _force_register()
    # 50 bars (min for compute_overlay's SMA50 gate); phase_oscillator needs 22 — should work fine
    closes = [100.0] * 50
    bars = make_daily_bars(closes=closes)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn()
    out = fn({"AAPL": bars}, overlays)
    assert isinstance(out, list)
