"""Post-market snapshot pipeline.

Called by Plan 2's daily-dispatcher at 21:00 UTC. For each active swing idea:
  1. Fetch today's daily bar (yfinance, cached with other active tickers in one call)
  2. Recompute indicators from the fresh close
  3. Check cycle-stage transitions (reuse Plan 2's stage-detection helper)
  4. Check stop violations -> status='invalidated'
  5. Run exhaustion_extension detector -> set risk_flags + append event
  6. Upsert snapshot row (natural key (idea_id, snapshot_date, snapshot_type))
  7. Post Slack digest

Idempotent: re-running the same day is a no-op on snapshots (UNIQUE constraint)
and re-computes risk_flags without duplicating events (we dedupe by event_type+date).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import pandas as pd

from api.indicators.common.moving_averages import ema, sma
from api.indicators.swing.setups.exhaustion_extension import detect_exhaustion_extension

logger = logging.getLogger(__name__)


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


@dataclass
class PostmarketResult:
    ran_at: datetime
    active_ideas_processed: int
    stage_transitions: int
    exhaustion_warnings: int
    stop_violations: int
    snapshots_written: int


def _fetch_daily_bars(ticker: str) -> pd.DataFrame | None:
    """Fetch ~1 year of daily bars for a single ticker via yfinance."""
    import yfinance as yf
    try:
        raw = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return None
        df = raw.reset_index().rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning("Failed to fetch bars for %s: %s", ticker, e)
        return None


def _post_slack_digest(summary: dict) -> None:
    """Thin wrapper so tests can monkey-patch."""
    from api.indicators.swing.pipeline.slack import post_postmarket_digest
    post_postmarket_digest(summary)


def _last_base_breakout_idx(sb: SupabaseLike, idea_id: str, df: pd.DataFrame) -> int | None:
    """Find the index in df where this idea's last base_n_break fired (from events)."""
    events = (
        sb.table("swing_events").select("*").eq("idea_id", idea_id)
        .eq("event_type", "setup_fired").execute().data or []
    )
    for e in reversed(events):
        payload = e.get("payload") or {}
        if payload.get("setup_kell") == "base_n_break":
            occurred = e.get("occurred_at")
            if not occurred:
                continue
            target_date = pd.to_datetime(occurred).date()
            matches = df.index[df["date"].apply(lambda d: pd.to_datetime(d).date()) == target_date]
            if len(matches) > 0:
                return int(matches[0])
    return None


def run_swing_postmarket_snapshot(sb: SupabaseLike) -> PostmarketResult:
    now = datetime.now(timezone.utc)
    today = now.date()

    active = (
        sb.table("swing_ideas").select("*")
        .execute().data or []
    )
    active = [i for i in active if i["status"] not in ("exited", "invalidated")]

    stage_transitions = 0
    exhaustion_warnings = 0
    stop_violations = 0
    snapshots_written = 0

    for idea in active:
        ticker = idea["ticker"]
        df = _fetch_daily_bars(ticker)
        if df is None or df.empty:
            logger.warning("No bars for %s; skipping", ticker)
            continue

        last_close = float(df["close"].iloc[-1])

        # 1. Stop violation
        if last_close < float(idea["stop_price"]):
            sb.table("swing_ideas").update({
                "status": "invalidated",
                "invalidated_at": now.isoformat(),
                "invalidated_reason": f"stop violation: close {last_close:.2f} < stop {idea['stop_price']:.2f}",
            }).eq("id", idea["id"]).execute()
            sb.table("swing_events").insert({
                "idea_id": idea["id"],
                "event_type": "invalidation",
                "occurred_at": now.isoformat(),
                "summary": f"Stop violated at {last_close:.2f}",
                "payload": {"close": last_close, "stop": idea["stop_price"]},
            }).execute()
            stop_violations += 1
            continue

        # 2. Exhaustion detector
        breakout_idx = _last_base_breakout_idx(sb, idea["id"], df)
        flag = detect_exhaustion_extension(df, last_base_breakout_idx=breakout_idx)
        if flag.any():
            current_flags = idea.get("risk_flags") or {}
            new_flags = {
                **current_flags,
                "kell_2nd_extension": flag.kell_2nd_extension,
                "climax_bar": flag.climax_bar,
                "far_above_10ema": flag.far_above_10ema,
                "weekly_air": flag.weekly_air,
                "last_flagged_at": now.isoformat(),
            }
            patch = {"risk_flags": new_flags}
            if idea["status"] in ("triggered", "adding"):
                patch["status"] = "trailing"
            sb.table("swing_ideas").update(patch).eq("id", idea["id"]).execute()

            existing = sb.table("swing_events").select("*").eq("idea_id", idea["id"]).eq("event_type", "exhaustion_warning").execute().data or []
            already_today = any(
                pd.to_datetime(e.get("occurred_at")).date() == today for e in existing if e.get("occurred_at")
            )
            if not already_today:
                sb.table("swing_events").insert({
                    "idea_id": idea["id"],
                    "event_type": "exhaustion_warning",
                    "occurred_at": now.isoformat(),
                    "summary": _summarize_flag(flag),
                    "payload": {
                        "kell_2nd_extension": flag.kell_2nd_extension,
                        "climax_bar": flag.climax_bar,
                        "far_above_10ema": flag.far_above_10ema,
                        "weekly_air": flag.weekly_air,
                    },
                }).execute()
            exhaustion_warnings += 1

        # 3. Upsert snapshot
        # NOTE: ema/sma helpers take the full DataFrame, not a Series
        ema10 = float(ema(df, 10).iloc[-1])
        ema20 = float(ema(df, 20).iloc[-1])
        sma50 = float(sma(df, 50).iloc[-1]) if len(df) >= 50 else None
        sma200 = float(sma(df, 200).iloc[-1]) if len(df) >= 200 else None

        existing_snap = sb.table("swing_idea_snapshots").select("*").eq("idea_id", idea["id"]).eq("snapshot_date", today.isoformat()).eq("snapshot_type", "daily").execute().data or []
        snap_row = {
            "idea_id": idea["id"],
            "snapshot_date": today.isoformat(),
            "snapshot_type": "daily",
            "daily_close": last_close,
            "daily_high": float(df["high"].iloc[-1]),
            "daily_low": float(df["low"].iloc[-1]),
            "daily_volume": int(df["volume"].iloc[-1]),
            "ema_10": ema10,
            "ema_20": ema20,
            "sma_50": sma50,
            "sma_200": sma200,
            "kell_stage": idea.get("cycle_stage"),
        }
        if existing_snap:
            sb.table("swing_idea_snapshots").update(snap_row).eq("idea_id", idea["id"]).eq("snapshot_date", today.isoformat()).eq("snapshot_type", "daily").execute()
        else:
            sb.table("swing_idea_snapshots").insert(snap_row).execute()
            snapshots_written += 1

    _post_slack_digest({
        "active_ideas": len(active),
        "stage_transitions": stage_transitions,
        "exhaustion_warnings": exhaustion_warnings,
        "stop_violations": stop_violations,
    })

    return PostmarketResult(
        ran_at=now,
        active_ideas_processed=len(active),
        stage_transitions=stage_transitions,
        exhaustion_warnings=exhaustion_warnings,
        stop_violations=stop_violations,
        snapshots_written=snapshots_written,
    )


def _summarize_flag(flag) -> str:
    parts = []
    if flag.kell_2nd_extension: parts.append("2nd extension from 10-EMA")
    if flag.climax_bar: parts.append("climax bar")
    if flag.far_above_10ema: parts.append("far above 10-EMA (H)")
    if flag.weekly_air: parts.append("weekly Air (H)")
    return "Exhaustion warning: " + ", ".join(parts)
