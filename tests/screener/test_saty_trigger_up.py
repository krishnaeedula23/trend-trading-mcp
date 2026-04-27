"""Tests for Saty Trigger Up Day/Multiday/Swing scans."""
from __future__ import annotations

import importlib

import pandas as pd
import pytest

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import make_daily_bars


def _force_register():
    """Re-register all Saty Trigger Up variants from a clean registry."""
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_trigger_up as mod
    clear_registry()
    importlib.reload(mod)


def _scan_fn(scan_id):
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id(scan_id)
    assert desc is not None, f"missing scan {scan_id}"
    return desc.fn


def test_saty_trigger_up_day_skips_when_close_below_trigger():
    """A flat 60-bar input lands close at PDC (not above call_trigger), so day-variant skips."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_saty_trigger_up_day_skips_when_levels_missing():
    """Empty saty_levels_by_mode → silent skip, no exception."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars).model_copy(update={"saty_levels_by_mode": {}})
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_up_day_fires_when_close_in_band():
    """Construct overlay with custom Saty levels so close lands strictly between call_trigger and mid_50_bull."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 99.0, "fib": 0.382},
                "mid_50_bull":      {"price": 105.0, "fib": 0.5},
                "fib_786_bull":     {"price": 110.0, "fib": 0.786},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    # close = 100 is above call_trigger (95) and below mid_50_bull (105)
    fn = _scan_fn("saty_trigger_up_day")
    hits = fn({"NVDA": bars}, {"NVDA": overlay}, {})
    assert len(hits) == 1
    assert hits[0].evidence["call_trigger"] == 95.0
    assert hits[0].evidence["mid_50_bull"] == 105.0
    assert hits[0].evidence["mode"] == "day"


def test_saty_trigger_up_skips_at_call_trigger_boundary():
    """close == call_trigger must reject (spec: strict > call_trigger)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 100.0,   # close exactly here
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 100.0, "fib": 0.236},
                "golden_gate_bull": {"price": 102.0, "fib": 0.382},
                "mid_50_bull":      {"price": 105.0, "fib": 0.5},
                "fib_786_bull":     {"price": 110.0, "fib": 0.786},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_up_skips_at_mid_50_boundary():
    """close == mid_50_bull must reject (spec: strict < mid_50_bull)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 98.0, "fib": 0.382},
                "mid_50_bull":      {"price": 100.0, "fib": 0.5},   # close exactly here
                "fib_786_bull":     {"price": 110.0, "fib": 0.786},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_up_three_variants_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_trigger_up_day", "saty_trigger_up_multiday", "saty_trigger_up_swing"):
        desc = get_scan_by_id(sid)
        assert desc is not None, f"missing variant {sid}"
        assert desc.weight == 3
        assert desc.lane == "breakout"
        assert desc.role == "trigger"


def test_saty_trigger_up_multiday_uses_multiday_levels():
    """multiday variant reads saty_levels_by_mode['multiday'], not ['day']."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "multiday": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 99.0, "fib": 0.382},
                "mid_50_bull":      {"price": 105.0, "fib": 0.5},
                "fib_786_bull":     {"price": 110.0, "fib": 0.786},
            },
        },
        # day mode missing
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    multiday_fn = _scan_fn("saty_trigger_up_multiday")
    day_fn = _scan_fn("saty_trigger_up_day")
    # multiday should fire (close=100 between trigger=95 and mid_50=105)
    multi_hits = multiday_fn({"AAPL": bars}, {"AAPL": overlay}, {})
    assert len(multi_hits) == 1
    assert multi_hits[0].evidence["mode"] == "multiday"
    # day should NOT fire (no levels for day mode)
    day_hits = day_fn({"AAPL": bars}, {"AAPL": overlay}, {})
    assert day_hits == []
