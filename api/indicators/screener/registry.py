"""Scan registry — scans declare themselves at import time.

A ScanDescriptor is (scan_id, lane, role, mode, fn). The runner iterates over
descriptors filtered by mode and dispatches each fn with the shared
(bars_by_ticker, overlays_by_ticker) context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from api.schemas.screener import IndicatorOverlay, Lane, Mode, Role, ScanHit


ScanFn = Callable[
    [dict[str, pd.DataFrame], dict[str, IndicatorOverlay]],
    list[ScanHit],
]


@dataclass(frozen=True)
class ScanDescriptor:
    scan_id: str
    lane: Lane
    role: Role
    mode: Mode
    fn: ScanFn
    weight: int = 1


_REGISTRY: dict[str, ScanDescriptor] = {}


def register_scan(desc: ScanDescriptor) -> None:
    if desc.scan_id in _REGISTRY:
        raise ValueError(f"Scan '{desc.scan_id}' already registered.")
    _REGISTRY[desc.scan_id] = desc


def get_scan_by_id(scan_id: str) -> ScanDescriptor | None:
    return _REGISTRY.get(scan_id)


def get_scans_for_mode(mode: Mode) -> list[ScanDescriptor]:
    return [d for d in _REGISTRY.values() if d.mode == mode]


def all_scans() -> list[ScanDescriptor]:
    return list(_REGISTRY.values())


def clear_registry() -> None:
    """Test-only: empty the registry."""
    _REGISTRY.clear()


def make_hit(
    ticker: str,
    scan_id: str,
    lane: Lane,
    role: Role,
    overlay: IndicatorOverlay,
    bars: pd.DataFrame,
    evidence: dict | None = None,
) -> ScanHit:
    """Construct a ScanHit with baseline evidence (close, dollar_volume_today)
    automatically populated from the overlay/bars. Per-scan evidence kwargs
    are merged on top.
    """
    base_evidence = {
        "close": float(bars["close"].iloc[-1]),
        "dollar_volume_today": overlay.dollar_volume_today,
    }
    if evidence:
        base_evidence.update(evidence)
    return ScanHit(
        ticker=ticker, scan_id=scan_id,
        lane=lane, role=role, evidence=base_evidence,
    )
