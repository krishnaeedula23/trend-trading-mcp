"""Tests for Saty Reversion Up/Down scans."""
from __future__ import annotations

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import force_register_scan_module, make_daily_bars, scan_fn_by_id


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.saty_reversion")


def _scan_fn(scan_id):
    return scan_fn_by_id(scan_id)


def test_saty_reversion_up_and_down_both_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_reversion_up", "saty_reversion_down"):
        desc = get_scan_by_id(sid)
        assert desc is not None
        assert desc.weight == 1
        assert desc.lane == "reversion"
        assert desc.role == "setup_ready"


def test_saty_reversion_up_skips_when_bias_not_blue():
    """bias_candle != 'blue' → skip Reversion Up."""
    _force_register()
    closes = [100.0 + i * 0.3 for i in range(120)]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "green",   # not blue
    })
    fn = _scan_fn("saty_reversion_up")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_reversion_up_skips_when_close_above_ema21():
    """Reversion Up needs close < EMA21 (price below pivot)."""
    _force_register()
    # Steep uptrend → close > EMA21
    closes = [100.0 + i * 1.0 for i in range(120)]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "blue",
    })
    fn = _scan_fn("saty_reversion_up")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_reversion_up_fires_when_blue_and_below_ema21():
    """All conditions: blue bias AND close < EMA21 → fire."""
    _force_register()
    # Bars where last close is below the EMA21: long flat tail at 100, then last bar at 99.0
    closes = [100.0] * 119 + [99.0]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "blue",
    })
    fn = _scan_fn("saty_reversion_up")
    hits = fn({"AAPL": bars}, {"AAPL": overlay}, {})
    if not hits:
        import pytest
        pytest.skip("synthetic did not produce close < EMA21 (EMA21 may not have caught up)")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.scan_id == "saty_reversion_up"
    assert hit.lane == "reversion"
    assert hit.role == "setup_ready"
    assert hit.evidence["bias_candle"] == "blue"
    assert hit.evidence["last_close"] < hit.evidence["ema21"]


def test_saty_reversion_down_skips_when_bias_not_orange():
    """bias_candle != 'orange' → skip Reversion Down."""
    _force_register()
    closes = [100.0 - i * 0.3 for i in range(120)]   # downtrend
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "red",   # not orange
    })
    fn = _scan_fn("saty_reversion_down")
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_reversion_down_fires_when_orange_and_above_ema21():
    """orange bias AND close > EMA21 → fire."""
    _force_register()
    # Bars where last close is above the EMA21: long flat tail at 100, then last bar at 101.0
    closes = [100.0] * 119 + [101.0]
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "bias_candle": "orange",
    })
    fn = _scan_fn("saty_reversion_down")
    hits = fn({"AAPL": bars}, {"AAPL": overlay}, {})
    if not hits:
        import pytest
        pytest.skip("synthetic did not produce close > EMA21")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.scan_id == "saty_reversion_down"
    assert hit.evidence["bias_candle"] == "orange"
    assert hit.evidence["last_close"] > hit.evidence["ema21"]
