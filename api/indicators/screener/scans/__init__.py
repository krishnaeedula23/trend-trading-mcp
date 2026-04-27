"""Scan implementations.

Importing this package triggers self-registration of every scan via
`register_scan(...)` calls at module bottom.

## Scan iteration contract

Each scan function has the signature:
    scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],          # daily bars
        overlays_by_ticker: dict[str, IndicatorOverlay],
        hourly_bars_by_ticker: dict[str, pd.DataFrame],   # may be empty
    ) -> list[ScanHit]

The runner guarantees `overlays_by_ticker.keys() ⊆ bars_by_ticker.keys()` —
every ticker that has an overlay also has daily bars. Daily-bar scans iterate
`overlays_by_ticker.items()` and use `bars_by_ticker[ticker]` as a direct
lookup (no `is None` guards needed).

Hourly-bar scans (e.g. vomy_up_hourly) iterate `hourly_bars_by_ticker.items()`
because not every universe ticker has hourly data. Those scans MUST guard
against missing daily/overlay keys before calling `make_hit` (which uses
the daily close + dollar volume for evidence enrichment).

Scans that don't read hourly data accept the third arg with `# noqa: ARG001`.
"""
from . import coiled         # noqa: F401
from . import pradeep_4pct   # noqa: F401
from . import qullamaggie_episodic_pivot   # noqa: F401
from . import qullamaggie_continuation_base   # noqa: F401
from . import saty_trigger_up   # noqa: F401
from . import saty_golden_gate_up   # noqa: F401
from . import vomy_up_daily   # noqa: F401
from . import vomy_up_hourly   # noqa: F401
