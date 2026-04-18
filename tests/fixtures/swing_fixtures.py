from typing import Any
from unittest.mock import MagicMock

import pytest


class FakeSupabaseTable:
    """In-memory stand-in for supabase_client.table() returning rows."""

    def __init__(self, initial_rows: list[dict[str, Any]] | None = None):
        self.rows: list[dict[str, Any]] = list(initial_rows or [])
        self._where: list[tuple[str, Any, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self._where.append((col, "eq", val))
        return self

    def is_(self, col, val):
        self._where.append((col, "is", val))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, rows):
        if isinstance(rows, dict):
            rows = [rows]
        self.rows.extend(rows)
        return MagicMock(execute=lambda: MagicMock(data=rows))

    def update(self, patch):
        matched = self._apply_where()
        for r in matched:
            r.update(patch)
        return MagicMock(execute=lambda: MagicMock(data=matched))

    def upsert(self, rows, on_conflict=None):
        return self.insert(rows)

    def delete(self):
        matched = self._apply_where()
        for r in matched:
            self.rows.remove(r)
        return MagicMock(execute=lambda: MagicMock(data=matched))

    def execute(self):
        rows = self._apply_where()
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit:
            rows = rows[: self._limit]
        return MagicMock(data=rows)

    def _apply_where(self) -> list[dict[str, Any]]:
        def match(row):
            for col, op, val in self._where:
                if op == "eq" and row.get(col) != val:
                    return False
                if op == "is" and row.get(col) is not val:
                    return False
            return True
        return [r for r in self.rows if match(r)]


class FakeSupabaseClient:
    def __init__(self):
        self.tables: dict[str, FakeSupabaseTable] = {}

    def table(self, name: str) -> FakeSupabaseTable:
        return self.tables.setdefault(name, FakeSupabaseTable())


@pytest.fixture
def fake_supabase():
    return FakeSupabaseClient()
