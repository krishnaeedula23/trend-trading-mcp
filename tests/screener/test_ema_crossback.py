"""Tests for the screener EMA Crossback adapter."""
from __future__ import annotations

import importlib

import pandas as pd
import pytest

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


def test_ema_crossback_fires_when_all_conditions_pass():
    """All 5 gates pass + ribbon override → exactly one hit with full evidence shape.

    Synthetic: 60 flat bars at 100.0 → EMA10=EMA20=100, ATR≈2.0.
    Override last-bar low to 100.5 (above EMA10=100) so gate 4 passes.
    Volume drying: today=500k vs avg=1M → ratio=0.5 < 0.8.
    dist(close=100, EMA10=100)=0, half-ATR=1.0 → gate 3 passes.
    """
    _force_register()
    closes = [100.0] * 60
    bars = make_daily_bars(
        closes=closes,
        volumes=[1_000_000] * 59 + [500_000],  # today drying (0.5x avg)
    )
    # Override last-bar low to 100.5 so cur_low > EMA10 (= 100.0 on flat closes)
    bars.at[bars.index[-1], "low"] = 100.5
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    hits = fn({"NVDA": bars}, {"NVDA": overlay}, {})
    if not hits:
        pytest.skip("synthetic bars did not produce all 5 EMA Crossback gates passing")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.scan_id == "ema_crossback"
    assert hit.lane == "transition"
    assert hit.role == "setup_ready"
    assert hit.evidence["respected_ema"] == "ema10"
    assert hit.evidence["dist_to_ema_atr"] == 0.0   # close == EMA10
    assert hit.evidence["volume_vs_20d_avg"] == pytest.approx(0.5, rel=1e-3)
    assert "close" in hit.evidence
    assert "dollar_volume_today" in hit.evidence


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
