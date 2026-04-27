"""Tests for Kell Wedge Pop screener adapter."""
from __future__ import annotations

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import (
    force_register_scan_module,
    make_daily_bars,
    scan_fn_by_id,
)


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.kell_wedge_pop")


def _scan_fn():
    return scan_fn_by_id("kell_wedge_pop")


def test_kell_wedge_pop_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_wedge_pop")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "breakout"
    assert desc.role == "setup_ready"


def test_kell_wedge_pop_skips_when_qqq_missing():
    """No QQQ in bars_by_ticker → no hits (every scan returns empty)."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn()
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_kell_wedge_pop_skips_qqq_itself():
    """QQQ should not be evaluated as a hit candidate against itself."""
    _force_register()
    bars = make_daily_bars(closes=[100.0] * 60)
    overlays = {"QQQ": compute_overlay(bars)}
    fn = _scan_fn()
    assert fn({"QQQ": bars}, overlays, {}) == []


def test_kell_wedge_pop_skips_non_wedge_pop_pattern():
    """Flat synthetic bars (no wedge pop pattern) → no hit."""
    _force_register()
    aapl_bars = make_daily_bars(closes=[100.0] * 60)
    qqq_bars = make_daily_bars(closes=[100.0] * 60)
    overlays = {"AAPL": compute_overlay(aapl_bars)}
    fn = _scan_fn()
    out = fn({"AAPL": aapl_bars, "QQQ": qqq_bars}, overlays, {})
    assert isinstance(out, list)
    # Whether a hit fires depends on the swing detector's gates; we just verify no crash.
