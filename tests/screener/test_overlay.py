"""Tests for the indicator overlay computer."""
from __future__ import annotations

import pytest

from api.indicators.screener.overlay import compute_overlay


def test_overlay_returns_all_metrics(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert out.atr_pct >= 0
    assert out.sma_50 == pytest.approx(100.0)
    assert out.atr_14 >= 0
    assert out.pct_from_50ma == pytest.approx(0.0, abs=1e-9)
    assert out.extension == pytest.approx(0.0, abs=1e-9)


def test_extension_uses_jfsrev_formula(synth_daily_bars):
    """Extension = ((close - SMA50) * close) / (SMA50 * ATR).

    Construct bars where SMA50 ≈ 70, close = 100, ATR ≈ 3.
    """
    closes = [70.0] * 50 + [100.0] * 10
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    # B = (100 - SMA50)/SMA50; A = ATR/100; Ext = B/A
    expected_b = (100.0 - out.sma_50) / out.sma_50
    expected_a = out.atr_14 / 100.0
    assert out.extension == pytest.approx(expected_b / expected_a, rel=1e-6)


def test_atr_magnitude_is_reasonable(synth_daily_bars):
    """Lock down ATR computation independently of the extension formula.

    synth_daily_bars uses high=close*1.005, low=close*0.995 ⇒ true range ≈ close * 0.01.
    For close=100 that means ATR(14) should land roughly in [0.5, 2.0].
    """
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert 0.5 < out.atr_14 < 2.0, f"ATR out of expected range: {out.atr_14}"


def test_overlay_raises_when_insufficient_bars(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 49)
    with pytest.raises(ValueError, match="at least 50"):
        compute_overlay(bars)
