"""Pre-market swing detection pipeline orchestrator.

Orchestrates:
  1. Resolve universe
  2. Fetch bars (yfinance default or injected fetcher)
  3. Compute market health from QQQ
  4. Run all 5 detectors per ticker
  5. Detect stage transitions
  6. Upsert swing_ideas (idempotent)
  7. Capture swing_daily_snapshots
  8. Post Slack digest

Invalidations (Wedge Drop detector) are deferred to Plan 4.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from uuid import uuid4

import pandas as pd

from api.indicators.common.moving_averages import ema
from api.indicators.common.atr import atr
from api.indicators.common.relative_strength import rs_vs_benchmark
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
        return {ticker: df.dropna(subset=["close"])} if "close" in df.columns else {}

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


def _compute_rs_10d(ticker_bars: pd.DataFrame, qqq_bars: pd.DataFrame) -> float:
    try:
        val = rs_vs_benchmark(ticker_bars, qqq_bars, 10).iloc[-1]
        return 0.0 if pd.isna(val) else float(val)
    except Exception:
        return 0.0


def _extract_theme_leaders(extras_by_ticker: dict[str, dict]) -> list[str]:
    return [t for t, e in extras_by_ticker.items() if e.get("theme_leader")]


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
            "universe_source": str,
            "universe_size": int,
            "market_health": dict,  # from MarketHealth.snapshot
        }
    """
    if fetch_bars is None:
        fetch_bars = _default_fetch_bars

    # ── Step 1: Resolve universe ───────────────────────────────────────────────
    resolved = resolve_universe(sb)
    if len(resolved.tickers) == 0:
        return {
            "new_ideas": 0,
            "transitions": 0,
            "invalidations": 0,
            "universe_source": resolved.source,
            "universe_size": 0,
            "market_health": {},
        }

    # ── Step 2: Fetch bars ─────────────────────────────────────────────────────
    all_tickers = resolved.tickers + ["QQQ"]
    all_bars = fetch_bars(all_tickers)

    qqq_bars = all_bars.get("QQQ")
    if qqq_bars is None or len(qqq_bars) < 20:
        logger.error("QQQ bars missing or too short — aborting pipeline")
        return {
            "new_ideas": 0,
            "transitions": 0,
            "invalidations": 0,
            "universe_source": resolved.source,
            "universe_size": len(resolved.tickers),
            "market_health": {},
        }

    # ── Step 3: Market health ──────────────────────────────────────────────────
    market_health = compute_market_health(qqq_bars)

    # ── Steps 4–5: Per-ticker detection + transition accumulation ─────────────
    today_str = datetime.now(timezone.utc).date().isoformat()
    theme_leaders = _extract_theme_leaders(resolved.extras_by_ticker)

    # prior_ideas per ticker (last 30 days window, fetched once per ticker below)
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

        # Fetch prior ideas for idempotency and transition detection
        try:
            raw_prior = sb.table("swing_ideas").select("*").eq("ticker", ticker).execute().data or []
        except Exception:
            raw_prior = []

        # Filter to last 30 calendar days in Python
        prior_ideas = [
            p for p in raw_prior
            if _idea_within_30_days(p.get("detected_at", ""))
        ]
        prior_ideas_by_ticker[ticker] = prior_ideas

        ctx = {
            "ticker": ticker,
            "universe_extras": resolved.extras_by_ticker.get(ticker, {}),
            "prior_ideas": prior_ideas,
            "today": date.today(),
            "rs_10d": _compute_rs_10d(ticker_bars, qqq_bars),
            "theme_leaders": theme_leaders,
        }

        hits = []
        for detector in _DETECTORS:
            try:
                hit = detector(ticker_bars, qqq_bars, ctx)
                if hit is not None:
                    hits.append(hit)
            except Exception as exc:
                logger.warning("Detector %s failed for %s: %s", detector.__name__, ticker, exc)

        if hits:
            scored = score_hits(hits, ticker, ctx, market_health)
            per_ticker_hits[ticker] = scored
            all_hits_with_scores.extend(scored)

    # ── Step 5: Stage transitions ──────────────────────────────────────────────
    transitions: list[dict] = []
    for ticker, hits_scored in per_ticker_hits.items():
        setups_today = {h.setup_kell for h, _ in hits_scored}
        prior_setups = {p["setup_kell"] for p in prior_ideas_by_ticker.get(ticker, [])}
        for setup in setups_today:
            for prior in prior_setups:
                if setup != prior:
                    transitions.append({"ticker": ticker, "from_stage": prior, "to_stage": setup})

    # ── Steps 6–7: Upsert ideas and snapshots ──────────────────────────────────
    new_ideas = 0
    for hit, score in all_hits_with_scores:
        ticker = hit.ticker

        # Idempotency: skip if same ticker+setup_kell already inserted today
        try:
            existing = (
                sb.table("swing_ideas")
                .select("*")
                .eq("ticker", ticker)
                .eq("setup_kell", hit.setup_kell)
                .execute()
                .data or []
            )
            if any(e.get("detected_at", "")[:10] == today_str for e in existing):
                logger.debug("Skipping dup idea: %s/%s already exists for today", ticker, hit.setup_kell)
                continue
        except Exception as exc:
            logger.warning("Idempotency check failed for %s: %s — inserting anyway", ticker, exc)

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
            logger.error("Failed to insert idea for %s/%s: %s", ticker, hit.setup_kell, exc)
            continue

        # Step 7: Daily snapshot
        try:
            snapshot_row = {
                "id": str(uuid4()),
                "idea_id": idea_id,
                "snapshot_date": today_str,
                "price_snapshot": {
                    "close": float(ticker_bars["close"].iloc[-1]),
                    "high": float(ticker_bars["high"].iloc[-1]),
                    "low": float(ticker_bars["low"].iloc[-1]),
                    "volume": float(ticker_bars["volume"].iloc[-1]),
                },
                "indicator_snapshot": {
                    "ema10": float(ema(ticker_bars, 10).iloc[-1]),
                    "ema20": float(ema(ticker_bars, 20).iloc[-1]),
                    "atr14": float(atr(ticker_bars, 14).iloc[-1]),
                },
                "claude_analysis": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            sb.table("swing_daily_snapshots").insert(snapshot_row).execute()
        except Exception as exc:
            logger.warning("Failed to insert snapshot for idea %s: %s", idea_id, exc)

    # ── Step 8: Invalidations (deferred to Plan 4 — Wedge Drop detector) ──────
    invalidations: list[dict] = []

    # ── Step 9: Post Slack digest ──────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    universe_age_days = (
        (now - resolved.latest_upload).days if resolved.latest_upload else 0
    )
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

    # ── Step 10: Return counts ─────────────────────────────────────────────────
    return {
        "new_ideas": new_ideas,
        "transitions": len(transitions),
        "invalidations": 0,
        "universe_source": resolved.source,
        "universe_size": len(resolved.tickers),
        "market_health": market_health.snapshot,
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
