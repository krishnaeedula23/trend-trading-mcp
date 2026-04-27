"""Tests for the Coiled Spring multi-condition scan."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.scans.coiled import (
    PHASE_OSCILLATOR_LOWER, PHASE_OSCILLATOR_UPPER,
    is_coiled, coiled_scan,
)


def _bars_with_compression(start_close=100.0, days=120, compress_window=40):
    """Build 120 bars: a long flat base preceded by a small step-up.

    The flat period must be long enough for EMA21 to fully converge to the
    current close (so `close - EMA21 ≈ 0` and Phase Oscillator → 0). Bars
    in the flat period have realistic ±0.5 intra-bar ranges so ATR stays at
    a meaningful value rather than collapsing.

    Layout:
      - first (days - compress_window) bars at start_close * 0.99
      - last compress_window bars at start_close (a 1% step-up)

    Result on default args (days=120, compress_window=40):
      - 80 bars at 99.0 then 40 bars at 100.0
      - SMA50 of the last 50 bars = (10 * 99 + 40 * 100) / 50 = 99.8
      - close (100.0) > SMA50 (99.8) ✓ (trend gate)
      - EMA21 fully converged to ~100 over 40 flat bars → oscillator near 0 ✓
      - Donchian width ≈ 1 + noise ≈ 2 ⇒ 2% of close ⇒ < 8% ✓
      - TTM Squeeze ON: BB std collapses on flat closes; ATR ≈ 1, KC wider ✓
    """
    rng = np.random.default_rng(42)
    closes = [start_close * 0.99] * (days - compress_window) + [start_close] * compress_window
    dates = pd.date_range("2025-12-01", periods=days, freq="B")
    highs = [c + float(rng.uniform(0.4, 0.6)) for c in closes]
    lows  = [c - float(rng.uniform(0.4, 0.6)) for c in closes]
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [5_000_000] * days,
    })


def _bars_no_compression():
    """Random-walk bars, definitely not compressed."""
    rng = np.random.default_rng(7)
    closes = [100.0]
    for _ in range(119):
        closes.append(closes[-1] * (1 + rng.normal(0, 0.03)))
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.04 for c in closes],
        "low": [c * 0.96 for c in closes],
        "close": closes,
        "volume": [5_000_000] * 120,
    })


def test_is_coiled_detects_compression():
    bars = _bars_with_compression()
    assert is_coiled(bars) is True


def test_is_coiled_rejects_random_walk():
    bars = _bars_no_compression()
    assert is_coiled(bars) is False


def test_is_coiled_requires_above_50ma():
    """Trend gate: close < SMA50 -> never coiled."""
    closes = list(np.linspace(200.0, 50.0, 120))  # downtrend
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    bars = pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [5_000_000] * 120,
    })
    assert is_coiled(bars) is False


def test_coiled_scan_emits_hit_for_compressed_ticker():
    bars = _bars_with_compression()
    bars_by_ticker = {"FAKE": bars}
    overlays_by_ticker = {"FAKE": compute_overlay(bars)}
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker, {})
    assert len(hits) == 1
    assert hits[0].ticker == "FAKE"
    assert hits[0].lane == "breakout"
    assert hits[0].role == "coiled"
    assert hits[0].scan_id == "coiled_spring"
    assert "donchian_width_pct" in hits[0].evidence


def test_coiled_scan_skips_random_ticker():
    bars = _bars_no_compression()
    bars_by_ticker = {"NOISE": bars}
    overlays_by_ticker = {"NOISE": compute_overlay(bars)}
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker, {})
    assert hits == []


def test_phase_oscillator_thresholds_are_minus_20_to_plus_20():
    """Spec §4: Phase Oscillator must be in compression zone (-20 to +20)."""
    assert PHASE_OSCILLATOR_LOWER == -20.0
    assert PHASE_OSCILLATOR_UPPER == 20.0


def test_is_coiled_rejects_when_phase_oscillator_outside_band():
    """Strong uptrend pushes oscillator above +20, so coiled must reject even if other gates would pass."""
    closes = [100.0 + i * 1.5 for i in range(120)]
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    bars = pd.DataFrame({
        "date": dates,
        "open": closes,
        "high":  [c * 1.005 for c in closes],
        "low":   [c * 0.995 for c in closes],
        "close": closes, "volume": [5_000_000] * 120,
    })
    assert is_coiled(bars) is False
