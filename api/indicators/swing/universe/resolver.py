# api/indicators/swing/universe/resolver.py
"""Resolve the active universe: Deepvue CSV first, backend-generated fallback.

Freshness window: 7 days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4


FRESHNESS_DAYS = 7


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


@dataclass
class ResolvedUniverse:
    tickers: list[str]
    source: str
    latest_upload: datetime | None
    extras_by_ticker: dict[str, dict]


def _all_active_rows(sb: SupabaseLike) -> list[dict]:
    """Fetch all active (removed_at IS NULL) rows from swing_universe in one query."""
    rows = (
        sb.table("swing_universe")
        .select("*")
        .is_("removed_at", None)
        .order("added_at", desc=True)
        .execute()
        .data
    )
    return rows or []


def resolve_universe(sb: SupabaseLike) -> ResolvedUniverse:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESHNESS_DAYS)

    all_rows = _all_active_rows(sb)
    by_source: dict[str, list[dict]] = {}
    for r in all_rows:
        by_source.setdefault(r["source"], []).append(r)

    deepvue_rows = by_source.get("deepvue-csv", []) + by_source.get("manual", [])
    if deepvue_rows:
        latest = max(_parse_ts(r["added_at"]) for r in deepvue_rows)
        if latest >= cutoff:
            return ResolvedUniverse(
                tickers=[r["ticker"] for r in deepvue_rows],
                source="deepvue",
                latest_upload=latest,
                extras_by_ticker={r["ticker"]: (r.get("extras") or {}) for r in deepvue_rows},
            )

    backend_rows = by_source.get("backend-generated", [])
    if backend_rows:
        latest = max(_parse_ts(r["added_at"]) for r in backend_rows)
        if latest >= cutoff:
            return ResolvedUniverse(
                tickers=[r["ticker"] for r in backend_rows],
                source="backend-stale-deepvue",
                latest_upload=latest,
                extras_by_ticker={r["ticker"]: (r.get("extras") or {}) for r in backend_rows},
            )

    return ResolvedUniverse(tickers=[], source="empty", latest_upload=None, extras_by_ticker={})


def save_universe_batch(
    sb: SupabaseLike,
    tickers_with_extras: dict[str, dict],
    source: str,
    mode: str = "replace",
) -> UUID:
    """Insert new batch. If mode='replace', soft-delete all prior active rows of this source."""
    batch_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    if mode == "replace":
        sb.table("swing_universe").update({"removed_at": now}).eq("source", source).is_("removed_at", None).execute()

    rows = [
        {
            "ticker": t,
            "source": source,
            "batch_id": str(batch_id),
            "added_at": now,
            "removed_at": None,
            "extras": extras,
        }
        for t, extras in tickers_with_extras.items()
    ]
    if rows:
        sb.table("swing_universe").insert(rows).execute()

    return batch_id


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
