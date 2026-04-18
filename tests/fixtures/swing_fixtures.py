"""In-memory Supabase stand-in for swing tests.

Mirrors the narrow subset of supabase-py's fluent API that swing code uses:
select/eq/is_/order/limit/insert/update/upsert/delete/execute.

Fidelity notes for future maintainers:
- Each `sb.table(name)` call must yield a builder with clean per-query state
  (real supabase-py returns a fresh query builder per call). We preserve one
  row-store per table name but reset filter/order/limit state on every
  `.select()` / `.update()` / `.delete()` / `.insert()` / `.upsert()` call so
  two successive queries can't contaminate each other.
- `.is_(col, val)` uses `==`/`!=` (not Python `is`) so the mock matches
  supabase-py semantics for non-None sentinels as well as None.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


class FakeSupabaseTable:
    def __init__(self, rows: list[dict[str, Any]]):
        # Rows are shared across query builders on the same table.
        self.rows: list[dict[str, Any]] = rows
        self._where: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
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
        self._order = (col, desc)
        return self

    def limit(self, n) -> "FakeSupabaseTable":
        self._limit = n
        return self

    # ------------------------------------------------------------------
    # Terminal execute().
    # ------------------------------------------------------------------
    def execute(self):
        rows = self._apply_where()
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit:
            rows = rows[: self._limit]
        self._reset_query_state()
        return MagicMock(data=rows)

    # ------------------------------------------------------------------
    # Internals.
    # ------------------------------------------------------------------
    def _reset_query_state(self) -> None:
        self._where = []
        self._order = None
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
        return FakeSupabaseTable(rows)


@pytest.fixture
def fake_supabase() -> FakeSupabaseClient:
    return FakeSupabaseClient()
