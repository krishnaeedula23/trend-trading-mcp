"""Pre-market swing detection pipeline orchestrator.

Orchestrates:
  1. Resolve universe
  2. Fetch bars (yfinance default or injected fetcher)
  3. Compute market health from QQQ
  4. Run all 5 detectors per ticker
  5. Detect stage transitions
  6. Upsert swing_ideas (idempotent against DB unique index)
  7. Persist stage transitions (swing_idea_stage_transitions)
  8. Capture daily snapshots (swing_idea_snapshots, snapshot_type='premarket')
  9. Post Slack digest

Invalidations (Wedge Drop detector) are deferred to Plan 4.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from api.indicators.common.moving_averages import ema, sma, weekly_resample
from api.indicators.common.atr import atr
from api.indicators.common.relative_strength import rs_vs_benchmark
from api.indicators.common.phase_oscillator import phase_oscillator_daily
from api.indicators.swing.setups.wedge_pop import detect as detect_wedge_pop
from api.indicators.swing.setups.ema_crossback import detect as detect_ema_crossback
from api.indicators.swing.setups.base_n_break import detect as detect_base_n_break
from api.indicators.swing.setups.reversal_extension import detect as detect_reversal_extension
from api.indicators.swing.setups.post_eps_flag import detect as detect_post_eps_flag
from api.indicators.swing.market_health import compute_market_health
from api.indicators.swing.confluence import score_hits
from api.indicators.swing.slack_digest import post_premarket_digest
from api.indicators.swing.universe.resolver import resolve_universe

logger = logging.getLogger(__name__)

_DETECTORS = [
    detect_wedge_pop,
    detect_ema_crossback,
    detect_base_n_break,
    detect_reversal_extension,
    detect_post_eps_flag,
]

_MIN_BARS = 25
_ACTIVE_STATUSES = ("active", "watching")


def _default_fetch_bars(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch bars via yfinance.  Returns dict of ticker → lowercase-columns DataFrame."""
    import yfinance as yf

    raw = yf.download(tickers, period=period, group_by="ticker", auto_adjust=False, progress=False)

    if len(tickers) == 1:
        ticker = tickers[0]
        df = raw.copy()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename_axis(None, axis=1).reset_index().rename(columns={"Date": "date"})
        df.columns = [c.lower() for c in df.columns]
        if "close" not in df.columns:
            return {}
        df = df.dropna(subset=["close"])
        return {ticker: df} if len(df) >= _MIN_BARS else {}

    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            df = raw[ticker].copy()
            df.columns = [c.lower() for c in df.columns]
            df = df.reset_index().rename(columns={"Date": "date"})
            df.columns = [c.lower() for c in df.columns]
            df = df.dropna(subset=["close"])
            if len(df) >= _MIN_BARS:
                result[ticker] = df
        except (KeyError, TypeError):
            logger.warning("yfinance: no data for %s", ticker)
    return result


def _compute_rs_10d(ticker: str, ticker_bars: pd.DataFrame, qqq_bars: pd.DataFrame) -> float:
    try:
        val = rs_vs_benchmark(ticker_bars, qqq_bars, 10).iloc[-1]
        return 0.0 if pd.isna(val) else float(val)
    except Exception as exc:
        logger.warning("rs_vs_benchmark failed for %s: %s", ticker, exc)
        return 0.0


def _safe_last(series: pd.Series) -> float | None:
    """Return last non-NaN value as float, or None."""
    try:
        val = series.iloc[-1]
        return None if pd.isna(val) else float(val)
    except Exception:
        return None


def _weekly_ema_10(bars: pd.DataFrame) -> float | None:
    try:
        weekly = weekly_resample(bars)
        if len(weekly) < 10:
            return None
        return _safe_last(ema(weekly, 10))
    except Exception:
        return None


def _extract_theme_leaders(extras_by_ticker: dict[str, dict]) -> list[str]:
    return [t for t, e in extras_by_ticker.items() if e.get("theme_leader")]


def _build_snapshot_row(
    *,
    idea_id: str,
    snapshot_date: str,
    ticker_bars: pd.DataFrame,
    qqq_bars: pd.DataFrame,
    kell_stage: str,
) -> dict:
    """Assemble a swing_idea_snapshots row matching docs/schema/016_add_swing_tables.sql."""
    return {
        "idea_id": idea_id,
        "snapshot_date": snapshot_date,
        "snapshot_type": "premarket",
        "daily_close": _safe_last(ticker_bars["close"]),
        "daily_high": _safe_last(ticker_bars["high"]),
        "daily_low": _safe_last(ticker_bars["low"]),
        "daily_volume": int(ticker_bars["volume"].iloc[-1]) if len(ticker_bars) else None,
        "ema_10": _safe_last(ema(ticker_bars, 10)),
        "ema_20": _safe_last(ema(ticker_bars, 20)),
        "sma_50": _safe_last(sma(ticker_bars, 50)) if len(ticker_bars) >= 50 else None,
        "sma_200": _safe_last(sma(ticker_bars, 200)) if len(ticker_bars) >= 200 else None,
        "weekly_ema_10": _weekly_ema_10(ticker_bars),
        "rs_vs_qqq_20d": _safe_last(rs_vs_benchmark(ticker_bars, qqq_bars, 20)),
        "phase_osc_value": _safe_last(phase_oscillator_daily(ticker_bars)),
        "kell_stage": kell_stage,
    }


def run_premarket_detection(sb, fetch_bars=None) -> dict:
    """Orchestrate pre-market swing detection.

    Args:
        sb: Supabase client (real or FakeSupabaseClient).
        fetch_bars: optional injectable bars-fetcher with signature
          (tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]
          Defaults to yfinance-based _default_fetch_bars.

    Returns:
        {
            "new_ideas": int,
            "transitions": int,
            "invalidations": int,
            "errors": int,         # detector / DB errors swallowed during the run
            "universe_source": str,
            "universe_size": int,
            "market_health": dict,
        }
    """
    if fetch_bars is None:
        fetch_bars = _default_fetch_bars

    errors = 0

    # ── Step 1: Resolve universe ───────────────────────────────────────────────
    resolved = resolve_universe(sb)
    if len(resolved.tickers) == 0:
        return _empty_result(resolved.source, 0, errors)

    # ── Step 2: Fetch bars ─────────────────────────────────────────────────────
    all_tickers = resolved.tickers + ["QQQ"]
    all_bars = fetch_bars(all_tickers)

    qqq_bars = all_bars.get("QQQ")
    if qqq_bars is None or len(qqq_bars) < 20:
        logger.error("QQQ bars missing or too short — aborting pipeline")
        return _empty_result(resolved.source, len(resolved.tickers), errors)

    # ── Step 3: Market health ──────────────────────────────────────────────────
    market_health = compute_market_health(qqq_bars)

    # ── Steps 4–5: Per-ticker detection + transition accumulation ─────────────
    today_str = datetime.now(timezone.utc).date().isoformat()
    theme_leaders = _extract_theme_leaders(resolved.extras_by_ticker)

    prior_ideas_by_ticker: dict[str, list[dict]] = {}
    per_ticker_hits: dict[str, list[tuple]] = {}
    all_hits_with_scores: list[tuple] = []

    for ticker in resolved.tickers:
        ticker_bars = all_bars.get(ticker)
        if ticker_bars is None:
            logger.warning("No bars for ticker %s — skipping", ticker)
            continue
        if len(ticker_bars) < _MIN_BARS:
            logger.warning("Ticker %s has only %d bars (< %d) — skipping", ticker, len(ticker_bars), _MIN_BARS)
            continue

        try:
            raw_prior = sb.table("swing_ideas").select("*").eq("ticker", ticker).execute().data or []
        except Exception as exc:
            logger.warning("Prior-ideas fetch failed for %s: %s", ticker, exc, exc_info=True)
            errors += 1
            raw_prior = []

        prior_ideas = [p for p in raw_prior if _idea_within_30_days(p.get("detected_at", ""))]
        prior_ideas_by_ticker[ticker] = prior_ideas

        ctx = {
            "ticker": ticker,
            "universe_extras": resolved.extras_by_ticker.get(ticker, {}),
            "prior_ideas": prior_ideas,
            "today": datetime.now(timezone.utc).date(),
            "rs_10d": _compute_rs_10d(ticker, ticker_bars, qqq_bars),
            "theme_leaders": theme_leaders,
        }

        hits = []
        for detector in _DETECTORS:
            try:
                hit = detector(ticker_bars, qqq_bars, ctx)
                if hit is not None:
                    hits.append(hit)
            except Exception as exc:
                logger.warning(
                    "Detector %s failed for %s: %s", detector.__name__, ticker, exc, exc_info=True
                )
                errors += 1

        if hits:
            scored = score_hits(hits, ticker, ctx, market_health)
            per_ticker_hits[ticker] = scored
            all_hits_with_scores.extend(scored)

    # ── Step 5: Stage transitions (in-memory, persisted per idea below) ───────
    transitions: list[dict] = []
    for ticker, hits_scored in per_ticker_hits.items():
        setups_today = {h.setup_kell for h, _ in hits_scored}
        prior_setups = {p["setup_kell"] for p in prior_ideas_by_ticker.get(ticker, []) if p.get("setup_kell")}
        for setup in setups_today:
            for prior in prior_setups:
                if setup != prior:
                    transitions.append({"ticker": ticker, "from_stage": prior, "to_stage": setup})

    # ── Steps 6–8: Upsert ideas, persist transitions, capture snapshots ───────
    new_ideas = 0
    for hit, score in all_hits_with_scores:
        ticker = hit.ticker

        # Idempotency: skip if an active/watching idea with the same cycle_stage
        # already exists for this ticker (matches DB partial unique index).
        try:
            existing = (
                sb.table("swing_ideas")
                .select("id,status,cycle_stage")
                .eq("ticker", ticker)
                .eq("cycle_stage", hit.cycle_stage)
                .execute()
                .data or []
            )
            if any(e.get("status") in _ACTIVE_STATUSES for e in existing):
                logger.debug(
                    "Skipping dup idea: %s/%s already active", ticker, hit.cycle_stage
                )
                continue
        except Exception as exc:
            logger.warning("Idempotency check failed for %s: %s — skipping insert", ticker, exc, exc_info=True)
            errors += 1
            continue

        idea_id = str(uuid4())
        ticker_bars = all_bars[ticker]

        row = {
            "id": idea_id,
            "ticker": hit.ticker,
            "setup_kell": hit.setup_kell,
            "cycle_stage": hit.cycle_stage,
            "confluence_score": score,
            "entry_zone_low": hit.entry_zone[0],
            "entry_zone_high": hit.entry_zone[1],
            "stop_price": hit.stop_price,
            "first_target": hit.first_target,
            "second_target": hit.second_target,
            "status": "active",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "detection_evidence": hit.detection_evidence,
            "market_health": market_health.snapshot,
            "risk_flags": {},
            "base_thesis": None,
            "thesis_status": "pending",
        }
        try:
            sb.table("swing_ideas").insert(row).execute()
            new_ideas += 1
        except Exception as exc:
            logger.error("Failed to insert idea for %s/%s: %s", ticker, hit.setup_kell, exc, exc_info=True)
            errors += 1
            continue

        # Persist stage transitions that culminated in this idea.
        daily_close = _safe_last(ticker_bars["close"])
        for t in transitions:
            if t["ticker"] == ticker and t["to_stage"] == hit.setup_kell:
                try:
                    sb.table("swing_idea_stage_transitions").insert({
                        "idea_id": idea_id,
                        "from_stage": t["from_stage"],
                        "to_stage": t["to_stage"],
                        "transitioned_at": datetime.now(timezone.utc).isoformat(),
                        "daily_close": daily_close,
                        "snapshot": {"confluence_score": score},
                    }).execute()
                except Exception as exc:
                    logger.warning("Failed to persist transition for %s: %s", ticker, exc, exc_info=True)
                    errors += 1

        # Daily snapshot row (swing_idea_snapshots).
        try:
            snapshot_row = _build_snapshot_row(
                idea_id=idea_id,
                snapshot_date=today_str,
                ticker_bars=ticker_bars,
                qqq_bars=qqq_bars,
                kell_stage=hit.cycle_stage,
            )
            sb.table("swing_idea_snapshots").insert(snapshot_row).execute()
        except Exception as exc:
            logger.warning("Failed to insert snapshot for idea %s: %s", idea_id, exc, exc_info=True)
            errors += 1

    # ── Step 9: Invalidations (deferred to Plan 4 — Wedge Drop detector) ──────
    invalidations: list[dict] = []

    # ── Step 10: Post Slack digest ─────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    universe_age_days = (now - resolved.latest_upload).days if resolved.latest_upload else 0
    asyncio.run(
        post_premarket_digest(
            hits_with_scores=all_hits_with_scores,
            transitions=transitions,
            invalidations=invalidations,
            market_health=market_health,
            universe_source=resolved.source,
            universe_size=len(resolved.tickers),
            universe_age_days=universe_age_days,
        )
    )

    return {
        "new_ideas": new_ideas,
        "transitions": len(transitions),
        "invalidations": len(invalidations),
        "errors": errors,
        "universe_source": resolved.source,
        "universe_size": len(resolved.tickers),
        "market_health": market_health.snapshot,
    }


def _empty_result(source: str, size: int, errors: int) -> dict:
    return {
        "new_ideas": 0,
        "transitions": 0,
        "invalidations": 0,
        "errors": errors,
        "universe_source": source,
        "universe_size": size,
        "market_health": {},
    }


def _idea_within_30_days(detected_at: str) -> bool:
    """Return True if detected_at (ISO string) is within the last 30 days."""
    if not detected_at:
        return False
    try:
        ts = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return delta.days <= 30
    except Exception:
        return False
