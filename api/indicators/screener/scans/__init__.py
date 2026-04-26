"""Scan implementations.

Importing this package triggers self-registration of every scan via
`register_scan(...)` calls at module bottom. The runner discovers scans purely
through `get_scans_for_mode(...)` — so it must import this package (or the
specific scan modules) to populate the registry.
"""
from . import coiled  # noqa: F401  -- triggers register_scan(coiled_spring)
