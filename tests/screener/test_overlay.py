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


def test_indicator_overlay_has_extended_fields():
    """Plan 2: schema must carry volume / move / phase / ribbon fields used by new scans."""
    from api.schemas.screener import IndicatorOverlay
    sample = IndicatorOverlay(
        atr_pct=0.02, pct_from_50ma=0.0, extension=0.0, sma_50=100.0, atr_14=2.0,
        volume_avg_50d=1_000_000.0, relative_volume=1.0, gap_pct_open=0.0,
        adr_pct_20d=0.04, pct_change_today=0.0, pct_change_30d=0.0,
        pct_change_90d=0.0, pct_change_180d=0.0, dollar_volume_today=100_000_000.0,
        phase_oscillator=0.0, phase_in_compression=False,
        ribbon_state="bullish", bias_candle="green", above_48ema=True,
        saty_levels_by_mode={},
    )
    assert sample.relative_volume == 1.0
    assert sample.phase_in_compression is False
    assert sample.ribbon_state == "bullish"


def test_overlay_computes_volume_metrics(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60, volume=2_000_000)
    out = compute_overlay(bars)
    assert out.volume_avg_50d == pytest.approx(2_000_000.0)
    assert out.relative_volume == pytest.approx(1.0)
    assert out.dollar_volume_today == pytest.approx(2_000_000.0 * 100.0)


def test_overlay_computes_pct_change_today(synth_daily_bars):
    closes = [100.0] * 59 + [105.0]
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    assert out.pct_change_today == pytest.approx(0.05, rel=1e-6)


def test_overlay_computes_gap_pct_open():
    import pandas as pd
    closes = [100.0] * 59 + [105.0]
    bars = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="B"),
        "open":  [100.0] * 59 + [103.0],
        "high":  [c * 1.005 for c in closes],
        "low":   [c * 0.995 for c in closes],
        "close": closes, "volume": [1_000_000] * 60,
    })
    out = compute_overlay(bars)
    assert out.gap_pct_open == pytest.approx(0.03, rel=1e-6)


def test_overlay_zero_pct_change_for_insufficient_lookback(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert out.pct_change_30d == pytest.approx(0.0, abs=1e-9)
    assert out.pct_change_90d == 0.0
    assert out.pct_change_180d == 0.0


def test_overlay_computes_adr_pct_20d():
    import pandas as pd
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="B"),
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low":  [c * 0.99 for c in closes],
        "close": closes, "volume": [1_000_000] * 60,
    })
    out = compute_overlay(bars)
    assert out.adr_pct_20d == pytest.approx(0.02, rel=1e-3)


def test_overlay_returns_phase_oscillator_value(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    # Flat closes → close == EMA21 exactly → raw_signal = 0 → oscillator = 0.
    assert out.phase_oscillator == pytest.approx(0.0, abs=1e-9)
    assert isinstance(out.phase_in_compression, bool)


def test_overlay_returns_ribbon_state_for_uptrend(synth_daily_bars):
    closes = [100.0 + i * 1.5 for i in range(120)]
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    assert out.ribbon_state == "bullish"
    assert out.above_48ema is True


def test_overlay_returns_saty_levels_for_day_mode(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert "day" in out.saty_levels_by_mode
    day = out.saty_levels_by_mode["day"]
    assert "call_trigger" in day
    assert "put_trigger" in day
    assert "levels" in day and "golden_gate_bull" in day["levels"]
    # Plan 2 review: confirm weekly/monthly modes also populate on a 60-bar input
    assert "multiday" in out.saty_levels_by_mode
    assert "swing" in out.saty_levels_by_mode
