"""Tests for Qullamaggie Continuation Base scan."""
from __future__ import annotations

import importlib

from tests.screener._helpers import make_daily_bars


def test_continuation_base_fires_when_all_conditions_met():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    # 60 bars: 50 at 50.0, then 10 at 55.0
    # SMA10 of last 10 bars = 55.0; last_close = 55.0; |55 - 55| / 55 = 0 ≤ 2% ✓
    # Volume: last 5 bars at 200k = sum 1M; prior 5 bars at 500k = sum 2.5M
    # Ratio = 1M / 2.5M = 0.4 < 0.5 ✓
    closes = [50.0] * 50 + [55.0] * 10
    volumes = [500_000] * 55 + [200_000] * 5
    bars = make_daily_bars(
        closes=closes,
        volumes=volumes,
        high_mult=1.04,
        low_mult=0.96,   # ADR ~ 8% so adr_pct_20d > 4% ✓
    )
    overlays = {"AAPL": compute_overlay(bars)}
    hits = qullamaggie_continuation_base_scan({"AAPL": bars}, overlays, {})
    assert len(hits) == 1
    ev = hits[0].evidence
    assert ev["last_5d_volume_ratio"] < 0.5


def test_continuation_base_rejects_below_5_dollars():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [3.0] * 60
    volumes = [500_000] * 60
    bars = make_daily_bars(closes=closes, volumes=volumes, high_mult=1.04, low_mult=0.96)
    overlays = {"PENNY": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"PENNY": bars}, overlays, {}) == []


def test_continuation_base_rejects_at_5_dollar_boundary():
    """last_close exactly $5 must reject (spec: strict > $5)."""
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [4.5] * 50 + [5.0] * 10   # last_close = 5.0 exactly
    volumes = [500_000] * 55 + [200_000] * 5
    bars = make_daily_bars(closes=closes, volumes=volumes, high_mult=1.04, low_mult=0.96)
    overlays = {"BORD": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"BORD": bars}, overlays, {}) == []


def test_continuation_base_rejects_when_too_far_from_10sma():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [50.0] * 50 + [55.0] * 9 + [80.0]   # last close 45% above 10-SMA
    volumes = [500_000] * 55 + [200_000] * 5
    bars = make_daily_bars(closes=closes, volumes=volumes, high_mult=1.04, low_mult=0.96)
    overlays = {"AAPL": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"AAPL": bars}, overlays, {}) == []


def test_continuation_base_rejects_when_volume_not_drying():
    """sum(last 5) / sum(prior 5) >= 0.5 should reject."""
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [50.0] * 50 + [55.0] * 10
    # Last 5 = 500k, prior 5 = 500k, ratio = 1.0 (not drying)
    volumes = [500_000] * 60
    bars = make_daily_bars(closes=closes, volumes=volumes, high_mult=1.04, low_mult=0.96)
    overlays = {"AAPL": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"AAPL": bars}, overlays, {}) == []


def test_continuation_base_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.qullamaggie_continuation_base as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("qullamaggie_continuation_base")
    assert desc is not None and desc.weight == 1
