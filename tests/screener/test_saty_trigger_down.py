"""Tests for Saty Trigger Down (Day) scan."""
from __future__ import annotations

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import (
    force_register_scan_module,
    make_daily_bars,
    scan_fn_by_id,
)


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.saty_trigger_down")


def _scan_fn():
    return scan_fn_by_id("saty_trigger_down_day")


def test_saty_trigger_down_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("saty_trigger_down_day")
    assert desc is not None
    assert desc.weight == 3
    assert desc.lane == "reversion"
    assert desc.role == "trigger"


def test_saty_trigger_down_skips_when_levels_missing():
    """Empty saty_levels_by_mode → silent skip."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars).model_copy(update={"saty_levels_by_mode": {}})
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_down_fires_when_close_in_band():
    """close = 100 lands strictly between mid_50_bear (90) and put_trigger (105)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 110.0,
            "put_trigger": 105.0,
            "levels": {
                "trigger_bear":  {"price": 105.0, "fib": 0.236},
                "mid_50_bear":   {"price":  90.0, "fib": 0.5},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn()
    hits = fn({"NVDA": bars}, {"NVDA": overlay}, {})
    assert len(hits) == 1
    assert hits[0].evidence["put_trigger"] == 105.0
    assert hits[0].evidence["mid_50_bear"] == 90.0


def test_saty_trigger_down_skips_at_put_trigger_boundary():
    """close == put_trigger must reject (spec: strict < put_trigger)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 110.0,
            "put_trigger": 100.0,   # close exactly here
            "levels": {
                "trigger_bear":  {"price": 100.0, "fib": 0.236},
                "mid_50_bear":   {"price":  90.0, "fib": 0.5},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_down_skips_at_mid_50_bear_boundary():
    """close == mid_50_bear must reject (spec: strict > mid_50_bear)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 110.0,
            "put_trigger": 105.0,
            "levels": {
                "trigger_bear":  {"price": 105.0, "fib": 0.236},
                "mid_50_bear":   {"price": 100.0, "fib": 0.5},   # close exactly here
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_down_skips_when_close_above_put_trigger():
    """close > put_trigger → no fire."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,   # close (100) above put_trigger
            "levels": {
                "trigger_bear":  {"price": 90.0, "fib": 0.236},
                "mid_50_bear":   {"price": 80.0, "fib": 0.5},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []
