"""Supabase CRUD for screener_runs and coiled_watchlist."""
from __future__ import annotations

from datetime import date
from typing import Callable, Literal

import pandas as pd
from supabase import Client


Mode = Literal["swing", "position"]


def save_run(sb: Client, payload: dict) -> str | None:
    """Insert a row into screener_runs and return the new id (or None if PostgREST
    didn't return a representation row — should not happen with default settings)."""
    res = sb.table("screener_runs").insert(payload).execute()
    rows = res.data or []
    return rows[0]["id"] if rows else None


def get_active_coiled(sb: Client, mode: Mode) -> list[dict]:
    """Return all currently-active coiled rows for the given mode."""
    res = (
        sb.table("coiled_watchlist")
        .select("*")
        .eq("mode", mode)
        .eq("status", "active")
        .execute()
    )
    return res.data or []


def update_coiled_watchlist(
    sb: Client,
    mode: Mode,
    coiled_tickers: set[str],
    today: date,
    initial_days_by_ticker: dict[str, int] | None = None,
) -> None:
    """Reconcile active coiled rows with today's coiled set.

    initial_days_by_ticker: when a ticker is **newly** detected (no prior row),
        seed days_in_compression from this dict (the backfilled count) instead
        of 1. Existing tickers ignore this dict and increment as before.
    """
    initial = initial_days_by_ticker or {}
    existing = get_active_coiled(sb, mode)
    existing_by_ticker = {r["ticker"]: r for r in existing}

    upserts: list[dict] = []
    for ticker in coiled_tickers:
        prior = existing_by_ticker.get(ticker)
        if prior:
            upserts.append({
                "ticker": ticker, "mode": mode,
                "first_detected_at": prior["first_detected_at"],
                "last_seen_at": today.isoformat(),
                "days_in_compression": int(prior["days_in_compression"]) + 1,
                "status": "active",
            })
        else:
            seeded = max(1, int(initial.get(ticker, 1)))
            upserts.append({
                "ticker": ticker, "mode": mode,
                "first_detected_at": today.isoformat(),
                "last_seen_at": today.isoformat(),
                "days_in_compression": seeded,
                "status": "active",
            })
    for ticker, prior in existing_by_ticker.items():
        if ticker in coiled_tickers:
            continue
        upserts.append({
            "ticker": ticker, "mode": mode,
            "first_detected_at": prior["first_detected_at"],
            "last_seen_at": prior["last_seen_at"],
            "days_in_compression": int(prior["days_in_compression"]),
            "status": "broken",
        })
    if upserts:
        sb.table("coiled_watchlist").upsert(
            upserts, on_conflict="ticker,mode,first_detected_at",
        ).execute()


def backfill_days_in_compression(
    bars: pd.DataFrame,
    is_coiled_fn: Callable[[pd.DataFrame], bool],
    max_lookback: int = 60,
) -> int:
    """Count consecutive trailing days where is_coiled_fn(bars[:i+1]) is True.

    Used on first run so existing coils don't reset to day 1. Walks backward
    from the latest bar; stops at the first non-coiled day.
    """
    n = len(bars)
    end = n
    days = 0
    for offset in range(min(max_lookback, n)):
        window = bars.iloc[: end - offset]
        if not is_coiled_fn(window):
            break
        days += 1
    return days
