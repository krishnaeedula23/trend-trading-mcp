"""Tests for Pradeep 4% Breakout scan."""
from __future__ import annotations

import importlib

from tests.screener._helpers import make_daily_bars


def test_pradeep_4pct_fires_on_5pct_up_with_volume_increase():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [1_000_000] * 59 + [2_000_000]
    bars = make_daily_bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    hits = pradeep_4pct_scan({"AAPL": bars}, overlays)
    assert len(hits) == 1
    assert hits[0].scan_id == "pradeep_4pct_breakout"
    assert hits[0].lane == "breakout"
    assert hits[0].role == "trigger"


def test_pradeep_4pct_rejects_3pct_up():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [103.0]
    volumes = [1_000_000] * 60
    bars = make_daily_bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_rejects_when_volume_decreasing():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [1_000_000] * 59 + [800_000]
    bars = make_daily_bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_rejects_when_volume_below_100k():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [50_000] * 59 + [80_000]
    bars = make_daily_bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_rejects_at_volume_boundary():
    """volume_today exactly at 100_000 must reject (spec: strict > 100_000)."""
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [99_000] * 59 + [100_000]   # today equals threshold
    bars = make_daily_bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.pradeep_4pct as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("pradeep_4pct_breakout")
    assert desc is not None
    assert desc.weight == 2
