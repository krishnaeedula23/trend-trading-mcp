"""Tests for the scan registry."""
from __future__ import annotations

import pytest

from api.indicators.screener.registry import (
    ScanDescriptor,
    register_scan,
    get_scans_for_mode,
    get_scan_by_id,
    clear_registry,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_lookup_by_id():
    def dummy_fn(bars_by_ticker, overlays_by_ticker):
        return []
    desc = ScanDescriptor(
        scan_id="dummy",
        lane="breakout",
        role="trigger",
        mode="swing",
        fn=dummy_fn,
    )
    register_scan(desc)
    assert get_scan_by_id("dummy") is desc


def test_get_scans_for_mode_filters():
    def fn(_, __):
        return []
    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", fn))
    register_scan(ScanDescriptor("b", "breakout", "trigger", "position", fn))
    register_scan(ScanDescriptor("c", "transition", "coiled", "swing", fn))
    swing = get_scans_for_mode("swing")
    ids = sorted(s.scan_id for s in swing)
    assert ids == ["a", "c"]


def test_register_duplicate_raises():
    def fn(_, __):
        return []
    register_scan(ScanDescriptor("dup", "breakout", "trigger", "swing", fn))
    with pytest.raises(ValueError, match="already registered"):
        register_scan(ScanDescriptor("dup", "breakout", "trigger", "swing", fn))
