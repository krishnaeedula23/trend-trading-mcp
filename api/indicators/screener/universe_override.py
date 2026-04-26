"""Universe overrides — manual ticker add/remove on top of resolved base universe.

Persisted to Supabase `universe_overrides` table. Per-mode (swing/position).
"""
from __future__ import annotations

from typing import Literal

from supabase import Client


Mode = Literal["swing", "position"]


def _insert_override_rows(
    sb: Client, mode: Mode, tickers: list[str], action: Literal["add", "remove"]
) -> None:
    """Normalize, dedupe, and insert override rows for the given action."""
    unique = sorted(set(t.upper().strip() for t in tickers if t.strip()))
    if not unique:
        return
    rows = [
        {"mode": mode, "ticker": t, "action": action, "source": "claude_skill"}
        for t in unique
    ]
    sb.table("universe_overrides").insert(rows).execute()


def add_overrides(sb: Client, mode: Mode, tickers: list[str]) -> None:
    """Insert add-overrides for the given tickers. Deduplicates input."""
    _insert_override_rows(sb, mode, tickers, "add")


def remove_overrides(sb: Client, mode: Mode, tickers: list[str]) -> None:
    """Insert remove-overrides for the given tickers. Deduplicates input."""
    _insert_override_rows(sb, mode, tickers, "remove")


def clear_overrides(sb: Client, mode: Mode) -> None:
    """Delete all overrides for the given mode."""
    sb.table("universe_overrides").delete().eq("mode", mode).execute()


def list_overrides(sb: Client, mode: Mode) -> tuple[list[str], list[str]]:
    """Return (added_tickers, removed_tickers) for the given mode."""
    res = (
        sb.table("universe_overrides")
        .select("*")
        .eq("mode", mode)
        .execute()
    )
    rows = res.data or []
    added = sorted({r["ticker"] for r in rows if r["action"] == "add"})
    removed = sorted({r["ticker"] for r in rows if r["action"] == "remove"})
    return added, removed


def apply_overrides(sb: Client, base_tickers: list[str], mode: Mode) -> list[str]:
    """Apply overrides to a base ticker list. Adds first, then removes."""
    added, removed = list_overrides(sb, mode)
    effective = set(base_tickers) | set(added)
    effective -= set(removed)
    return sorted(effective)
