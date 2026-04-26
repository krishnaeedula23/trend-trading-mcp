"""Tests for the Coiled Spring multi-condition scan."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.scans.coiled import (
    is_coiled,
    coiled_scan,
)


def _bars_with_compression(start_close=100.0, days=120, compress_window=20):
    """Build 120 bars: trend up, then a flat compression for last N bars.

    compress_window must be >= BB_PERIOD (20) so that the Bollinger Band and
    SMA windows fall entirely within the flat region, triggering TTM squeeze.
    """
    rng = np.random.default_rng(42)
    closes = list(np.linspace(start_close, start_close * 1.6, days - compress_window))
    flat = [closes[-1]] * compress_window
    closes = closes + flat
    dates = pd.date_range("2025-12-01", periods=days, freq="B")
    highs = [c + rng.uniform(0.0, 0.2) for c in closes[:-compress_window]] + [
        flat[0] + 0.05 for _ in range(compress_window)
    ]
    lows = [c - rng.uniform(0.0, 0.2) for c in closes[:-compress_window]] + [
        flat[0] - 0.05 for _ in range(compress_window)
    ]
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
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker)
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
    hits = coiled_scan(bars_by_ticker, overlays_by_ticker)
    assert hits == []
