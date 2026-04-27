"""Tests for Qullamaggie Episodic Pivot scan."""
from __future__ import annotations

import importlib

from tests.screener._helpers import make_daily_bars


def test_episodic_pivot_fires_on_8pct_up_through_yesterday_high():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    # Override `high_mult` won't work because we want different highs per bar.
    # Build directly with custom highs:
    bars = make_daily_bars(
        closes=closes,
        volumes=[1_000_000] * 59 + [1_500_000],
    )
    bars["high"] = [101.0] * 59 + [108.5]
    overlays = {"NVDA": compute_overlay(bars)}
    hits = qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays, {})
    assert len(hits) == 1
    assert hits[0].evidence["close"] > hits[0].evidence["yesterday_high"]


def test_episodic_pivot_rejects_below_yesterday_high():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    bars = make_daily_bars(closes=closes, volumes=[1_000_000] * 59 + [1_500_000])
    bars["high"] = [120.0] * 59 + [108.5]   # yesterday's high is much higher
    overlays = {"NVDA": compute_overlay(bars)}
    assert qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays, {}) == []


def test_episodic_pivot_rejects_low_dollar_volume():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    bars = make_daily_bars(closes=closes, volumes=[50_000] * 60)
    bars["high"] = [101.0] * 59 + [108.5]
    overlays = {"NVDA": compute_overlay(bars)}
    assert qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays, {}) == []


def test_episodic_pivot_rejects_at_dollar_volume_boundary():
    """dollar_volume_today exactly at $100M must reject (spec: strict > $100M)."""
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [92.0] * 59 + [100.0]   # pct_change ≈ 8.7%, above 7.5% gate
    volumes = [1_000_000] * 60       # 100.0 * 1_000_000 = $100M exactly
    bars = make_daily_bars(closes=closes, volumes=volumes)
    bars["high"] = [99.0] * 59 + [99.5]   # yesterday_high (99) < close (100), passes
    overlays = {"NVDA": compute_overlay(bars)}
    assert qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays, {}) == []


def test_episodic_pivot_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.qullamaggie_episodic_pivot as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("qullamaggie_episodic_pivot")
    assert desc is not None and desc.weight == 2
