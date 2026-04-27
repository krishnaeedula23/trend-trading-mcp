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
from datetime import date, datetime, timezone

import pandas as pd
from supabase import Client

from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.persistence import save_run, update_coiled_watchlist
from api.indicators.screener.registry import get_scans_for_mode
from api.schemas.screener import (
    IndicatorOverlay,
    Mode,
    ScreenerRunResponse,
    TickerResult,
)


logger = logging.getLogger(__name__)


def run_screener(
    sb: Client,
    mode: Mode,
    bars_by_ticker: dict[str, pd.DataFrame],
    today: date,
    scan_ids: list[str] | None = None,
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

    coiled_tickers: set[str] = set()
    for desc in descriptors:
        try:
            hits = desc.fn(eligible_bars, overlays)
        except Exception:
            logger.exception("scan %s failed; skipping its hits for this run", desc.scan_id)
            continue
        for hit in hits:
            hits_by_ticker.setdefault(hit.ticker, []).append(hit.scan_id)
            if hit.scan_id == "coiled_spring":
                coiled_tickers.add(hit.ticker)

    # TODO(plan-2): wire backfill_days_in_compression for newly-detected coiled
    # tickers so existing coils don't reset to day 1 on first observation.
    # Requires threading bars_by_ticker + is_coiled_fn into the persistence
    # call site (or computing the per-ticker initial day count here and
    # passing as an optional dict to update_coiled_watchlist).
    update_coiled_watchlist(sb, mode=mode, coiled_tickers=coiled_tickers, today=today)

    weights_by_id = {d.scan_id: d.weight for d in descriptors}
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
    )
