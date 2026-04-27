"""Runner: orchestrates a single screener run.

Inputs:
  - sb: Supabase client
  - mode: 'swing' | 'position'
  - bars_by_ticker: pre-fetched daily OHLCV per ticker
  - today: date stamp for coiled watchlist update

Steps:
  1. Compute indicator overlay per ticker (skip tickers with too few bars)
  2. Dispatch each registered scan for the mode
  3. Aggregate (ticker -> scans_hit list) confluence map
  4. Update coiled_watchlist for tickers whose hits include scan_id='coiled_spring'
  5. Persist screener_runs row
  6. Return ScreenerRunResponse
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from supabase import Client

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.persistence import save_run, update_coiled_watchlist, backfill_days_in_compression, get_active_coiled
from api.indicators.screener.scans.coiled import is_coiled
from api.indicators.screener.registry import get_scans_for_mode
from api.indicators.screener.sectors import get_sectors_bulk
from api.indicators.swing.earnings_calendar import next_earnings_date
from api.schemas.screener import (
    IndicatorOverlay,
    Mode,
    ScreenerRunResponse,
    TickerResult,
)


logger = logging.getLogger(__name__)

_EARNINGS_FILTERED_SCANS = frozenset({
    "pradeep_4pct_breakout",
    "qullamaggie_episodic_pivot",
    "saty_trigger_up_day", "saty_trigger_up_multiday", "saty_trigger_up_swing",
    "saty_golden_gate_up_day", "saty_golden_gate_up_multiday", "saty_golden_gate_up_swing",
})
EARNINGS_BLACKOUT_DAYS = 5


def _within_earnings_blackout(ticker: str, today: date) -> bool:
    """True if ticker has earnings within the next EARNINGS_BLACKOUT_DAYS days."""
    nxt = next_earnings_date(ticker)
    if nxt is None:
        return False
    return today <= nxt <= today + timedelta(days=EARNINGS_BLACKOUT_DAYS)


def run_screener(
    sb: Client,
    mode: Mode,
    bars_by_ticker: dict[str, pd.DataFrame],
    today: date,
    scan_ids: list[str] | None = None,
    hourly_bars_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> ScreenerRunResponse:
    started = time.time()

    overlays: dict[str, IndicatorOverlay] = {}
    for ticker, bars in bars_by_ticker.items():
        try:
            overlays[ticker] = compute_overlay(bars)
        except ValueError:
            continue

    eligible_bars = {t: bars_by_ticker[t] for t in overlays}

    descriptors = get_scans_for_mode(mode)
    if scan_ids is not None:
        descriptors = [d for d in descriptors if d.scan_id in scan_ids]

    hits_by_ticker: dict[str, list[str]] = {t: [] for t in overlays}

    hourly_bars = hourly_bars_by_ticker or {}
    weights_by_id = {d.scan_id: d.weight for d in descriptors}
    earnings_cache: dict[str, bool] = {}

    coiled_tickers: set[str] = set()
    for desc in descriptors:
        scan_started = time.time()
        try:
            hits = desc.fn(eligible_bars, overlays, hourly_bars)
        except Exception:
            logger.exception("scan %s failed; skipping its hits for this run", desc.scan_id)
            continue
        kept = 0
        for hit in hits:
            if desc.scan_id in _EARNINGS_FILTERED_SCANS:
                if hit.ticker not in earnings_cache:
                    earnings_cache[hit.ticker] = _within_earnings_blackout(hit.ticker, today)
                if earnings_cache[hit.ticker]:
                    continue
            hits_by_ticker.setdefault(hit.ticker, []).append(hit.scan_id)
            kept += 1
            if hit.scan_id == "coiled_spring":
                coiled_tickers.add(hit.ticker)
        logger.info(
            "screener.scan_complete",
            extra={
                "scan_id": desc.scan_id,
                "duration_ms": int((time.time() - scan_started) * 1000),
                "hits_raw": len(hits),
                "hits_kept": kept,
            },
        )

    existing_rows = get_active_coiled(sb, mode)
    existing_active = {r["ticker"] for r in existing_rows}
    new_coiled = coiled_tickers - existing_active
    initial_days = {
        ticker: backfill_days_in_compression(eligible_bars[ticker], is_coiled)
        for ticker in new_coiled
    }

    update_coiled_watchlist(
        sb,
        mode=mode,
        coiled_tickers=coiled_tickers,
        today=today,
        initial_days_by_ticker=initial_days,
        existing_rows=existing_rows,
    )

    ticker_results: list[TickerResult] = []
    for ticker, scans in hits_by_ticker.items():
        if not scans:
            continue
        weighted = sum(weights_by_id.get(s, 1) for s in scans)
        ticker_results.append(TickerResult(
            ticker=ticker,
            last_close=float(eligible_bars[ticker]["close"].iloc[-1]),
            overlay=overlays[ticker],
            scans_hit=scans,
            confluence=weighted,
        ))

    ticker_list = [t.ticker for t in ticker_results]
    sectors = get_sectors_bulk(ticker_list) if ticker_list else {}
    enriched: list[TickerResult] = []
    for t in ticker_results:
        sector = sectors.get(t.ticker, "Unknown")
        enriched.append(t.model_copy(update={"sector": sector}))
        logger.info(
            "screener.ticker_hit",
            extra={
                "ticker": t.ticker, "scans": t.scans_hit,
                "confluence": t.confluence, "sector": sector,
            },
        )
    ticker_results = enriched
    sector_summary = dict(Counter(t.sector for t in ticker_results))

    duration = time.time() - started

    payload = {
        "mode": mode,
        "universe_size": len(bars_by_ticker),
        "scan_count": len(descriptors),
        "hit_count": len(ticker_results),
        "duration_seconds": round(duration, 3),
        "results": {"tickers": [t.model_dump(mode="json") for t in ticker_results]},
    }
    run_id = save_run(sb, payload)

    return ScreenerRunResponse(
        run_id=run_id,
        mode=mode,
        ran_at=datetime.now(timezone.utc),
        universe_size=len(bars_by_ticker),
        scan_count=len(descriptors),
        hit_count=len(ticker_results),
        duration_seconds=round(duration, 3),
        tickers=ticker_results,
        sector_summary=sector_summary,
    )
