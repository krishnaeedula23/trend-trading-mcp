"""In-memory Supabase stand-in for swing tests.

Mirrors the narrow subset of supabase-py's fluent API that swing code uses:
select/eq/is_/order (multi-column)/limit/insert/update/upsert/delete/execute.

Fidelity notes for future maintainers:
- Each `sb.table(name)` call must yield a builder with clean per-query state
  (real supabase-py returns a fresh query builder per call). We preserve one
  row-store per table name but reset filter/order/limit state on every
  `.select()` / `.update()` / `.delete()` / `.insert()` / `.upsert()` call so
  two successive queries can't contaminate each other.
- `.is_(col, val)` uses `==`/`!=` (not Python `is`) so the mock matches
  supabase-py semantics for non-None sentinels as well as None.
- `.order(col, desc)` can be called multiple times — we apply sorts in reverse
  order (Python sort is stable) so the first `.order()` call is the primary key.
- Inserts against tables in `_SWING_SCHEMA` are validated to prevent schema drift:
  any column outside the allowlist raises ValueError at insert time. Mirrors the
  real schema from docs/schema/016_add_swing_tables.sql + 017_add_swing_detection_evidence.sql.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


# Column allowlist per swing table — mirrors docs/schema/016_add_swing_tables.sql
# + 017_add_swing_detection_evidence.sql. Keep this in sync if schema changes.
_SWING_SCHEMA: dict[str, set[str]] = {
    "swing_universe": {
        "id", "ticker", "source", "batch_id", "added_at", "removed_at", "extras",
    },
    "swing_ideas": {
        "id", "ticker", "direction", "detected_at", "cycle_stage", "setup_kell", "setup_saty",
        "confluence_score", "entry_zone_low", "entry_zone_high", "stop_price",
        "first_target", "second_target", "suggested_position_pct", "suggested_risk_bips",
        "fundamentals", "next_earnings_date", "beta", "avg_daily_dollar_volume",
        "base_thesis", "base_thesis_at", "thesis_status", "deep_thesis", "deep_thesis_at",
        "deep_thesis_sources", "market_health", "risk_flags", "status", "watching_since",
        "invalidated_at", "invalidated_reason", "user_notes", "tags",
        "detection_evidence",  # added by migration 017
    },
    "swing_idea_stage_transitions": {
        "id", "idea_id", "from_stage", "to_stage", "transitioned_at", "daily_close", "snapshot",
    },
    "swing_idea_snapshots": {
        "id", "idea_id", "snapshot_date", "snapshot_type", "daily_close", "daily_high",
        "daily_low", "daily_volume", "ema_10", "ema_20", "sma_50", "sma_200", "weekly_ema_10",
        "rs_vs_qqq_20d", "phase_osc_value", "kell_stage", "saty_setups_active",
        "claude_analysis", "claude_model", "analysis_sources", "deepvue_panel",
        "chart_daily_url", "chart_weekly_url", "chart_60m_url",
    },
    "swing_events": {
        "id", "idea_id", "event_type", "occurred_at", "payload", "summary",
    },
    "swing_model_book": {
        "id", "title", "ticker", "setup_kell", "outcome", "entry_date", "exit_date",
        "r_multiple", "source_idea_id", "ticker_fundamentals", "narrative",
        "key_takeaways", "tags", "created_at", "updated_at",
    },
    "swing_charts": {
        "id", "idea_id", "event_id", "model_book_id", "image_url", "thumbnail_url",
        "timeframe", "source", "annotations", "caption", "captured_at",
    },
    "swing_idempotency_keys": {"key", "endpoint", "response_json", "created_at"},
}


def _validate_row(table_name: str, row: dict) -> None:
    """Raise ValueError if row has a column not in _SWING_SCHEMA[table_name]."""
    allowed = _SWING_SCHEMA.get(table_name)
    if allowed is None:
        return  # non-swing table — no schema to enforce
    extra = set(row.keys()) - allowed
    if extra:
        raise ValueError(
            f"FakeSupabaseClient: unknown columns for {table_name}: {sorted(extra)}. "
            f"Check docs/schema/ migrations — either add to schema or remove from the insert."
        )


class FakeSupabaseTable:
    def __init__(self, rows: list[dict[str, Any]], table_name: str = ""):
        # Rows are shared across query builders on the same table.
        self.rows: list[dict[str, Any]] = rows
        self._table_name = table_name
        self._where: list[tuple[str, str, Any]] = []
        # Multiple .order() calls stack; execute() applies them in reverse.
        self._orders: list[tuple[str, bool]] = []
        self._limit: int | None = None

    # ------------------------------------------------------------------
    # Query starters — always reset builder state so each query is isolated.
    # ------------------------------------------------------------------
    def select(self, *_args, **_kwargs) -> "FakeSupabaseTable":
        self._reset_query_state()
        return self

    def insert(self, rows):
        self._reset_query_state()
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows:
            _validate_row(self._table_name, row)
        self.rows.extend(rows)
        return MagicMock(execute=lambda: MagicMock(data=rows))

    def upsert(self, rows, on_conflict=None):
        return self.insert(rows)

    def update(self, patch):
        # Capture the filter state *before* reset so the update sees any
        # eq()/is_() chained before .update().
        matched = self._apply_where()
        for r in matched:
            r.update(patch)
        self._reset_query_state()
        return MagicMock(execute=lambda: MagicMock(data=matched))

    def delete(self):
        matched = self._apply_where()
        for r in matched:
            self.rows.remove(r)
        self._reset_query_state()
        return MagicMock(execute=lambda: MagicMock(data=matched))

    # ------------------------------------------------------------------
    # Filter/sort/pagination chain (modifies query state).
    # ------------------------------------------------------------------
    def eq(self, col, val) -> "FakeSupabaseTable":
        self._where.append((col, "eq", val))
        return self

    def is_(self, col, val) -> "FakeSupabaseTable":
        self._where.append((col, "is", val))
        return self

    def order(self, col, desc=False) -> "FakeSupabaseTable":
        # Stack orders — execute() applies in reverse so first call is primary.
        self._orders.append((col, desc))
        return self

    def limit(self, n) -> "FakeSupabaseTable":
        self._limit = n
        return self

    # ------------------------------------------------------------------
    # Terminal execute().
    # ------------------------------------------------------------------
    def execute(self):
        rows = self._apply_where()
        # Apply orders in reverse (stable sort) so first .order() is primary.
        for col, desc in reversed(self._orders):
            rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col) or ""), reverse=desc)
        if self._limit:
            rows = rows[: self._limit]
        self._reset_query_state()
        return MagicMock(data=rows)

    # ------------------------------------------------------------------
    # Internals.
    # ------------------------------------------------------------------
    def _reset_query_state(self) -> None:
        self._where = []
        self._orders = []
        self._limit = None

    def _apply_where(self) -> list[dict[str, Any]]:
        def match(row):
            for col, op, val in self._where:
                cell = row.get(col)
                if op == "eq" and cell != val:
                    return False
                # `.is_(col, None)` must map to SQL `col IS NULL`, but for
                # non-None sentinels supabase-py treats this as equality.
                # Use `==` here so any other value also works as expected.
                if op == "is" and cell != val:
                    return False
            return True
        return [r for r in self.rows if match(r)]


class FakeSupabaseClient:
    def __init__(self):
        # Shared row-stores per table, but each .table() call returns a
        # fresh builder with clean filter state.
        self._rows_by_table: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> FakeSupabaseTable:
        rows = self._rows_by_table.setdefault(name, [])
        return FakeSupabaseTable(rows, table_name=name)


@pytest.fixture
def fake_supabase() -> FakeSupabaseClient:
    return FakeSupabaseClient()
