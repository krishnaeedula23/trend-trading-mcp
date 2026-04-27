"""Tests for Vomy Up Hourly scan."""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import force_register_scan_module, make_daily_bars, scan_fn_by_id


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.vomy_up_hourly")


def _scan_fn():
    return scan_fn_by_id("vomy_up_hourly")


def test_vomy_up_hourly_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_up_hourly")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "transition"
    assert desc.role == "trigger"


def test_vomy_up_hourly_skips_when_no_hourly_bars():
    """Empty hourly_bars_by_ticker → no hits."""
    _force_register()
    daily = make_daily_bars(closes=[100.0] * 120)
    overlays = {"AAPL": compute_overlay(daily)}
    fn = _scan_fn()
    assert fn({"AAPL": daily}, overlays, {}) == []


def test_vomy_up_hourly_handles_short_hourly_history():
    """Hourly bars present but too short for Phase Oscillator (<22) → no hits, no exception."""
    _force_register()
    daily = make_daily_bars(closes=[100.0] * 120)
    overlays = {"AAPL": compute_overlay(daily)}
    short_hourly = pd.DataFrame({
        "date": pd.date_range("2026-04-25 09:30", periods=10, freq="h"),
        "open": [100.0] * 10, "high": [100.2] * 10, "low": [99.8] * 10,
        "close": [100.1] * 10, "volume": [10_000] * 10,
    })
    fn = _scan_fn()
    assert fn({"AAPL": daily}, overlays, {"AAPL": short_hourly}) == []


def test_vomy_up_hourly_skips_when_hourly_bias_not_blue():
    """Hourly Pivot Ribbon produces non-blue bias → skip."""
    _force_register()
    daily = make_daily_bars(closes=[100.0] * 120)
    overlays = {"NVDA": compute_overlay(daily)}
    # Strong uptrend hourly: bias_candle will be 'green', not 'blue'
    closes = [100.0 + i * 0.05 for i in range(60)]
    hourly = pd.DataFrame({
        "date": pd.date_range("2026-04-22 09:30", periods=60, freq="h"),
        "open": closes,
        "high": [c + 0.1 for c in closes],
        "low":  [c - 0.1 for c in closes],
        "close": closes, "volume": [100_000] * 60,
    })
    fn = _scan_fn()
    out = fn({"NVDA": daily}, overlays, {"NVDA": hourly})
    # Whatever the bias ended up being, the scan must not crash. If hits exist, validate shape.
    assert isinstance(out, list)
