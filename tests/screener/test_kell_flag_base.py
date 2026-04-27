"""Tests for Kell Flag Base scan."""
from __future__ import annotations

from api.indicators.screener.overlay import compute_overlay
from tests.screener._helpers import (
    force_register_scan_module,
    make_daily_bars,
    scan_fn_by_id,
)


def _force_register():
    force_register_scan_module("api.indicators.screener.scans.kell_flag_base")


def _scan_fn():
    return scan_fn_by_id("kell_flag_base")


def test_kell_flag_base_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_flag_base")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "breakout"
    assert desc.role == "setup_ready"


def test_kell_flag_base_skips_when_no_prior_impulse():
    """Flat bars → no impulse → skip."""
    _force_register()
    closes = [100.0] * 60
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_kell_flag_base_skips_when_base_not_tight():
    """Wide-range last 5 bars (large high-low spread) disqualify."""
    _force_register()
    n = 60
    # Impulse window [-25:-5] = bars 35-55: rise from 100 to 115 (15%)
    # Last 5 bars (55-60) have wild swings
    closes = [100.0] * 35 + list(range(101, 116)) + [115.0, 125.0, 110.0, 120.0, 115.0]
    # Pad to n=60: 35 + 15 + 5 = 55. Need 5 more before n=60.
    closes = [100.0] * (n - 25) + list(range(101, 116)) + [115.0, 125.0, 110.0, 120.0, 115.0]
    bars = make_daily_bars(closes=closes, high_mult=1.05, low_mult=0.95)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_kell_flag_base_skips_when_not_bullish_ribbon():
    """ribbon_state != 'bullish' → skip."""
    _force_register()
    n = 60
    closes = [100.0] * (n - 25) + list(range(101, 116)) + [115.0] * 5
    bars = make_daily_bars(closes=closes)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bearish",   # disqualifier
        "above_48ema": True,
    })
    fn = _scan_fn()
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_kell_flag_base_fires_when_all_conditions_met():
    """Construct: 35 flat bars, then 15-bar impulse 100→115, then 5 tight flat bars at 115 with low volume.

    Impulse: bars[-25:-5] = 20 bars total but last few are flat 115s, so peak/start
    needs to span >=15%. Build the impulse strictly within the [-25:-5] slice and
    have the flat tail in [-5:].
    """
    _force_register()
    n = 60
    # bars[0:36]   = 36 flat bars at 100  (one extra; the impulse window starts at index 35
    #                                       so this anchor IS the impulse window's first bar)
    # bars[36:55]  = 19 bars rising 100 → 116 (+16% impulse, fully in [-25:-5])
    # bars[55:60]  = 5 flat bars at 116 (tight base + drying)
    flat_pre = [100.0] * 36
    impulse = [100.0 + (16.0 * (i + 1) / 19.0) for i in range(19)]  # → 116.0
    flat_tail = [116.0] * 5
    closes = flat_pre + impulse + flat_tail
    assert len(closes) == n
    # Volume: prior 19 (impulse) at 1M, last 5 at 200k → ratio 0.2 < 0.8
    volumes = [1_000_000] * 36 + [1_000_000] * 19 + [200_000] * 5
    bars = make_daily_bars(closes=closes, volumes=volumes, high_mult=1.005, low_mult=0.995)
    overlay = compute_overlay(bars).model_copy(update={
        "ribbon_state": "bullish",
        "above_48ema": True,
    })
    fn = _scan_fn()
    hits = fn({"NVDA": bars}, {"NVDA": overlay}, {})
    assert len(hits) == 1, f"expected 1 hit; got {len(hits)} (evidence keys: {[h.evidence.keys() for h in hits]})"
    hit = hits[0]
    assert hit.scan_id == "kell_flag_base"
    assert hit.lane == "breakout"
    assert hit.role == "setup_ready"
    assert hit.evidence["impulse_pct"] >= 0.15
    assert hit.evidence["base_range_pct"] < 0.05
    assert hit.evidence["base_volume_ratio"] < 0.8
    assert "close" in hit.evidence
