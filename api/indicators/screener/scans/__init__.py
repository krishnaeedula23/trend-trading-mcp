"""Scan implementations.

Importing this package triggers self-registration of every scan via
`register_scan(...)` calls at module bottom.

## Scan iteration contract

Each scan function has the signature:
    scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
    ) -> list[ScanHit]

The runner guarantees `overlays_by_ticker.keys() ⊆ bars_by_ticker.keys()` —
every ticker that has an overlay also has bars. Scans iterate
`overlays_by_ticker.items()` and use `bars_by_ticker[ticker]` as a direct
lookup (no `is None` guards needed).
"""
from . import coiled         # noqa: F401
from . import pradeep_4pct   # noqa: F401
