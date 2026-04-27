"""Tests for Saty Golden Gate Up Day/Multiday/Swing scans."""
from __future__ import annotations

import importlib

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import make_daily_bars


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_golden_gate_up as mod
    clear_registry()
    importlib.reload(mod)


def _scan_fn(scan_id):
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id(scan_id)
    assert desc is not None, f"missing scan {scan_id}"
    return desc.fn


def test_saty_gg_up_skips_when_levels_missing():
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars).model_copy(update={"saty_levels_by_mode": {}})
    fn = _scan_fn("saty_golden_gate_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_saty_gg_up_fires_when_close_in_band():
    """Inject custom levels: close=100 lands in [99, 105) GG zone."""
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
                "mid_50_bull":      {"price": 100.0, "fib": 0.5},
                "mid_range_bull":   {"price": 101.0, "fib": 0.618},
                "fib_786_bull":     {"price": 105.0, "fib": 0.786},
                "full_range_bull":  {"price": 110.0, "fib": 1.0},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_golden_gate_up_day")
    hits = fn({"AAPL": bars}, {"AAPL": overlay})
    assert len(hits) == 1
    ev = hits[0].evidence
    assert ev["golden_gate"] == 99.0
    assert ev["fib_786"] == 105.0
    assert ev["mode"] == "day"


def test_saty_gg_up_fires_at_golden_gate_lower_boundary():
    """close == golden_gate_bull must FIRE (spec: >= golden_gate_bull, inclusive)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 100.0, "fib": 0.382},   # close exactly here
                "mid_50_bull":      {"price": 102.0, "fib": 0.5},
                "fib_786_bull":     {"price": 105.0, "fib": 0.786},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_golden_gate_up_day")
    hits = fn({"AAPL": bars}, {"AAPL": overlay})
    assert len(hits) == 1, "Equality on golden_gate_bull should fire (inclusive lower bound)"


def test_saty_gg_up_skips_at_fib_786_upper_boundary():
    """close == fib_786_bull must REJECT (spec: < fib_786_bull, strict)."""
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
                "mid_50_bull":      {"price": 99.0, "fib": 0.5},
                "fib_786_bull":     {"price": 100.0, "fib": 0.786},   # close exactly here
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_golden_gate_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_saty_gg_up_skips_when_close_below_golden_gate():
    """close < golden_gate_bull → no fire."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 105.0, "fib": 0.382},   # close (100) below
                "mid_50_bull":      {"price": 107.0, "fib": 0.5},
                "fib_786_bull":     {"price": 110.0, "fib": 0.786},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    fn = _scan_fn("saty_golden_gate_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_saty_gg_up_three_variants_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_golden_gate_up_day", "saty_golden_gate_up_multiday", "saty_golden_gate_up_swing"):
        desc = get_scan_by_id(sid)
        assert desc is not None
        assert desc.weight == 3
        assert desc.lane == "breakout"
        assert desc.role == "trigger"


def test_saty_gg_up_swing_uses_swing_levels():
    """swing variant reads saty_levels_by_mode['swing'], not other modes."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "swing": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 99.0, "fib": 0.382},
                "mid_50_bull":      {"price": 102.0, "fib": 0.5},
                "fib_786_bull":     {"price": 105.0, "fib": 0.786},
            },
        },
        # day and multiday absent
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    swing_fn = _scan_fn("saty_golden_gate_up_swing")
    day_fn = _scan_fn("saty_golden_gate_up_day")
    swing_hits = swing_fn({"AAPL": bars}, {"AAPL": overlay})
    assert len(swing_hits) == 1
    assert swing_hits[0].evidence["mode"] == "swing"
    day_hits = day_fn({"AAPL": bars}, {"AAPL": overlay})
    assert day_hits == []
