"""Market Monitor — Stockbee-style breadth scans + sector theme tracking.

Computes 10 breadth scans daily (4% 1d, 25% 20d, 50% 20d, 13% 34d, 25% 65d,
each up and down) across a filtered universe (>=$1B market cap). Results are
persisted to Supabase for the frontend heat-map visualization.

Endpoints:
    POST /api/market-monitor/refresh-universe  — Seed/update universe from Schwab
    POST /api/market-monitor/compute           — Run breadth scans for today
    GET  /api/market-monitor/snapshots         — Last N days of breadth counts
    GET  /api/market-monitor/drill-down        — Ticker list for a scan+date
    GET  /api/market-monitor/theme-tracker     — Sector rankings for a date
    GET  /api/market-monitor/sector-stocks     — Stocks in a sector for a date
    POST /api/market-monitor/backfill          — Bulk historical backfill
"""

import asyncio
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
from supabase import Client, create_client

from api.endpoints.screener import _load_universe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-monitor", tags=["market-monitor"])

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

_supabase: Client | None = None


def _get_supabase() -> Client:
    """Return a singleton Supabase client."""
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# Breadth scan definitions
# ---------------------------------------------------------------------------

BREADTH_SCANS: list[dict] = [
    {"key": "4pct_up_1d", "direction": "up", "threshold": 0.04, "lookback": 1},
    {"key": "4pct_down_1d", "direction": "down", "threshold": 0.04, "lookback": 1},
    {"key": "25pct_up_20d", "direction": "up", "threshold": 0.25, "lookback": 20},
    {"key": "25pct_down_20d", "direction": "down", "threshold": 0.25, "lookback": 20},
    {"key": "50pct_up_20d", "direction": "up", "threshold": 0.50, "lookback": 20},
    {"key": "50pct_down_20d", "direction": "down", "threshold": 0.50, "lookback": 20},
    {"key": "13pct_up_34d", "direction": "up", "threshold": 0.13, "lookback": 34},
    {"key": "13pct_down_34d", "direction": "down", "threshold": 0.13, "lookback": 34},
    {"key": "25pct_up_65d", "direction": "up", "threshold": 0.25, "lookback": 65},
    {"key": "25pct_down_65d", "direction": "down", "threshold": 0.25, "lookback": 65},
]

THEME_PERIODS = {"1d": 1, "1w": 5, "1m": 20, "3m": 65}


# ---------------------------------------------------------------------------
# Pure computation helpers (testable without DB/HTTP)
# ---------------------------------------------------------------------------


def _compute_breadth_scans(
    df: pd.DataFrame,
    tickers: list[str],
    as_of_idx: int = -1,
) -> dict[str, dict]:
    """Compute all 10 Stockbee-style breadth scans.

    Args:
        df: MultiIndex DataFrame from yf.download
            (columns: Price x Ticker, e.g. ("Close", "AAPL")).
        tickers: List of tickers to scan.
        as_of_idx: Row index to treat as "today" (-1 = last row).

    Returns:
        Dict keyed by scan name, each value is
        ``{"count": int, "tickers": list[str]}``.
    """
    is_multi = isinstance(df.columns, pd.MultiIndex)
    results: dict[str, dict] = {}

    for scan in BREADTH_SCANS:
        hits: list[str] = []
        for ticker in tickers:
            try:
                # Extract close and volume series
                if is_multi:
                    if ("Close", ticker) not in df.columns:
                        continue
                    close = df[("Close", ticker)]
                    vol = df[("Volume", ticker)] if ("Volume", ticker) in df.columns else None
                else:
                    close = df["Close"]
                    vol = df.get("Volume")

                close = close.iloc[: len(close) + as_of_idx + 1] if as_of_idx != -1 else close
                close = close.dropna()

                if vol is not None:
                    vol = vol.iloc[: len(vol) + as_of_idx + 1] if as_of_idx != -1 else vol
                    vol = vol.dropna()

                lookback = scan["lookback"]

                if len(close) < lookback + 1:
                    continue

                # Volume filter: avg(close, 20) * avg(volume, 20) >= 250_000
                if vol is not None and len(vol) >= 20:
                    avg_close_20 = float(close.iloc[-20:].mean())
                    avg_vol_20 = float(vol.iloc[-20:].mean())
                    if avg_close_20 * avg_vol_20 < 250_000:
                        continue

                current_close = float(close.iloc[-1])

                if lookback == 1:
                    # Daily scan: pct = (close - prev_close) / prev_close
                    prev_close = float(close.iloc[-2])
                    if prev_close <= 0:
                        continue
                    pct = (current_close - prev_close) / prev_close
                else:
                    # Multi-day scans
                    window = close.iloc[-(lookback + 1) :]
                    if scan["direction"] == "up":
                        # pct = (close - min_close_over_lookback) / min_close_over_lookback
                        min_close = float(window.iloc[:-1].min())
                        if min_close <= 0:
                            continue
                        pct = (current_close - min_close) / min_close
                    else:
                        # pct = (close - max_close_over_lookback) / max_close_over_lookback
                        max_close = float(window.iloc[:-1].max())
                        if max_close <= 0:
                            continue
                        pct = (current_close - max_close) / max_close

                # Direction check
                if scan["direction"] == "up" and pct >= scan["threshold"]:
                    hits.append(ticker)
                elif scan["direction"] == "down" and pct <= -scan["threshold"]:
                    hits.append(ticker)

            except Exception:
                logger.debug("Breadth scan error for %s/%s", ticker, scan["key"])

        results[scan["key"]] = {"count": len(hits), "tickers": hits}

    return results


def _compute_theme_tracker(
    df: pd.DataFrame,
    tickers: list[str],
    sector_map: dict[str, str],
) -> dict[str, list[dict]]:
    """Compute sector theme rankings for each lookback period.

    Args:
        df: MultiIndex DataFrame from yf.download.
        tickers: List of tickers to scan.
        sector_map: Mapping of ticker -> sector.

    Returns:
        Dict keyed by period label ("1d", "1w", "1m", "3m"), each value
        is a list of dicts sorted by net (descending):
        ``[{"sector": str, "gainers": int, "losers": int, "net": int}, ...]``
    """
    is_multi = isinstance(df.columns, pd.MultiIndex)
    result: dict[str, list[dict]] = {}

    for period_label, lookback in THEME_PERIODS.items():
        sector_counts: dict[str, dict[str, int]] = {}

        for ticker in tickers:
            sector = sector_map.get(ticker, "Unknown")
            if sector not in sector_counts:
                sector_counts[sector] = {"gainers": 0, "losers": 0}

            try:
                if is_multi:
                    if ("Close", ticker) not in df.columns:
                        continue
                    close = df[("Close", ticker)].dropna()
                else:
                    close = df["Close"].dropna()

                if len(close) < lookback + 1:
                    continue

                current_close = float(close.iloc[-1])
                past_close = float(close.iloc[-(lookback + 1)])

                if past_close <= 0:
                    continue

                pct_change = (current_close - past_close) / past_close

                if pct_change > 0:
                    sector_counts[sector]["gainers"] += 1
                elif pct_change < 0:
                    sector_counts[sector]["losers"] += 1

            except Exception:
                logger.debug("Theme tracker error for %s/%s", ticker, period_label)

        # Build ranked list
        ranked = []
        for sector, counts in sector_counts.items():
            net = counts["gainers"] - counts["losers"]
            ranked.append(
                {
                    "sector": sector,
                    "gainers": counts["gainers"],
                    "losers": counts["losers"],
                    "net": net,
                }
            )

        ranked.sort(key=lambda x: x["net"], reverse=True)
        result[period_label] = ranked

    return result


# ---------------------------------------------------------------------------
# 1) POST /refresh-universe
# ---------------------------------------------------------------------------


@router.post("/refresh-universe")
async def refresh_universe():
    """Load seed tickers, fetch fundamentals from Schwab, filter to >= $1B market cap,
    and upsert to Supabase ``monitor_universe`` table.
    """
    from api.integrations.schwab.client import get_quotes

    t0 = time.monotonic()

    # Load all seed tickers
    tickers = await asyncio.to_thread(_load_universe, ["all"])
    logger.info("Refreshing universe: %d seed tickers", len(tickers))

    # Batch-fetch fundamentals from Schwab in chunks of 100
    records: list[dict] = []
    batch_size = 100
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            quotes = await asyncio.to_thread(get_quotes, batch)
            for symbol, data in quotes.items():
                inner = data.get(symbol, data)
                if not isinstance(inner, dict):
                    continue
                fund = inner.get("fundamental", {})
                ref = inner.get("reference", {})
                mcap = fund.get("marketCap", 0) or 0
                sector = fund.get("sector", "Unknown") or "Unknown"
                industry = fund.get("industry", "Unknown") or "Unknown"
                name = ref.get("description", "") or ""

                if mcap >= 1_000_000_000:
                    records.append(
                        {
                            "symbol": symbol.upper(),
                            "name": name,
                            "market_cap": int(mcap),
                            "sector": sector,
                            "industry": industry,
                            "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
        except Exception as exc:
            logger.warning("Schwab batch %d-%d failed: %s", i, i + batch_size, exc)

    # Upsert to Supabase
    if records:
        sb = _get_supabase()
        upsert_batch_size = 500
        for i in range(0, len(records), upsert_batch_size):
            batch = records[i : i + upsert_batch_size]
            sb.table("monitor_universe").upsert(batch, on_conflict="symbol").execute()

    elapsed = round(time.monotonic() - t0, 2)
    logger.info("Universe refresh: %d qualified stocks in %.1fs", len(records), elapsed)

    return {
        "status": "ok",
        "total_seed": len(tickers),
        "qualified": len(records),
        "duration_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# 2) POST /compute
# ---------------------------------------------------------------------------


@router.post("/compute")
async def compute_breadth():
    """Run all breadth scans for today: download price data, compute scans +
    theme tracker, and upsert to ``breadth_snapshots``.
    """
    t0 = time.monotonic()
    sb = _get_supabase()

    # Read universe from Supabase
    resp = sb.table("monitor_universe").select("symbol, sector").execute()
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=400, detail="Universe is empty. Run /refresh-universe first.")

    tickers = [r["symbol"] for r in rows]
    sector_map = {r["symbol"]: r.get("sector", "Unknown") for r in rows}
    logger.info("Computing breadth for %d tickers", len(tickers))

    # Bulk download ~5 months of daily data
    raw_df = await asyncio.to_thread(
        yf.download,
        tickers,
        period="5mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw_df is None or raw_df.empty:
        raise HTTPException(status_code=502, detail="yfinance download returned empty data.")

    # Compute breadth scans
    scans = await asyncio.to_thread(_compute_breadth_scans, raw_df, tickers)

    # Compute theme tracker
    theme = await asyncio.to_thread(_compute_theme_tracker, raw_df, tickers, sector_map)

    # Build snapshot (strip ticker lists for the summary, keep them in scans)
    today = date.today().isoformat()
    snapshot = {
        "date": today,
        "universe": "large_cap_1b",
        "scans": scans,
        "theme_tracker": theme,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    sb.table("breadth_snapshots").upsert(snapshot, on_conflict="date").execute()

    elapsed = round(time.monotonic() - t0, 2)

    # Summary counts for the response
    summary = {k: v["count"] for k, v in scans.items()}
    return {
        "status": "ok",
        "date": today,
        "universe_size": len(tickers),
        "scans": summary,
        "duration_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# 3) GET /snapshots
# ---------------------------------------------------------------------------


@router.get("/snapshots")
async def get_snapshots(days: int = Query(default=30, ge=1, le=365)):
    """Return last N days of breadth snapshots (counts only, no ticker lists)."""
    sb = _get_supabase()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    resp = (
        sb.table("breadth_snapshots")
        .select("date, universe, scans, computed_at")
        .gte("date", cutoff)
        .order("date", desc=True)
        .execute()
    )

    snapshots = []
    for row in resp.data or []:
        scans = row.get("scans", {})
        # Strip ticker lists for performance — return counts only
        counts = {k: v.get("count", 0) if isinstance(v, dict) else 0 for k, v in scans.items()}
        snapshots.append(
            {
                "date": row["date"],
                "universe": row.get("universe", "large_cap_1b"),
                "scans": counts,
                "computed_at": row.get("computed_at"),
            }
        )

    return {"snapshots": snapshots, "days": days, "count": len(snapshots)}


# ---------------------------------------------------------------------------
# 4) GET /drill-down
# ---------------------------------------------------------------------------


@router.get("/drill-down")
async def drill_down(
    scan: str = Query(..., description="Scan key, e.g. '4pct_up_1d'"),
    date_str: str = Query(default="", alias="date", description="ISO date (default: today)"),
):
    """Return the full ticker list for a specific scan and date."""
    sb = _get_supabase()
    target_date = date_str or date.today().isoformat()

    resp = (
        sb.table("breadth_snapshots")
        .select("scans")
        .eq("date", target_date)
        .execute()
    )

    rows = resp.data or []
    if not rows:
        return {"scan": scan, "date": target_date, "count": 0, "tickers": []}

    scans = rows[0].get("scans", {})
    scan_data = scans.get(scan, {})
    tickers = scan_data.get("tickers", [])

    return {"scan": scan, "date": target_date, "count": len(tickers), "tickers": tickers}


# ---------------------------------------------------------------------------
# 5) GET /theme-tracker
# ---------------------------------------------------------------------------


@router.get("/theme-tracker")
async def get_theme_tracker(
    date_str: str = Query(default="", alias="date", description="ISO date (default: latest)"),
):
    """Return sector theme rankings for a date (or the most recent snapshot)."""
    sb = _get_supabase()

    if date_str:
        resp = (
            sb.table("breadth_snapshots")
            .select("date, theme_tracker")
            .eq("date", date_str)
            .execute()
        )
    else:
        resp = (
            sb.table("breadth_snapshots")
            .select("date, theme_tracker")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )

    rows = resp.data or []
    if not rows:
        return {"date": date_str or "N/A", "theme_tracker": {}}

    row = rows[0]
    return {"date": row["date"], "theme_tracker": row.get("theme_tracker", {})}


# ---------------------------------------------------------------------------
# 6) GET /sector-stocks
# ---------------------------------------------------------------------------


@router.get("/sector-stocks")
async def get_sector_stocks(
    sector: str = Query(..., description="Sector name, e.g. 'Technology'"),
    date_str: str = Query(default="", alias="date", description="ISO date (default: today)"),
):
    """Return all stocks from a specific sector that appear in breadth scans for a date."""
    sb = _get_supabase()
    target_date = date_str or date.today().isoformat()

    # Get snapshot for the date
    snap_resp = (
        sb.table("breadth_snapshots")
        .select("scans")
        .eq("date", target_date)
        .execute()
    )

    # Get sector members from universe
    univ_resp = (
        sb.table("monitor_universe")
        .select("symbol, name, market_cap, industry")
        .eq("sector", sector)
        .order("market_cap", desc=True)
        .execute()
    )

    # Cross-reference: which scans does each sector stock appear in?
    scans_data = {}
    if snap_resp.data:
        scans_data = snap_resp.data[0].get("scans", {})

    # Build result with scan membership
    stocks = []
    for row in univ_resp.data or []:
        symbol = row["symbol"]
        active_scans = [
            scan_key
            for scan_key, scan_val in scans_data.items()
            if symbol in scan_val.get("tickers", [])
        ]
        stocks.append(
            {
                "symbol": symbol,
                "name": row.get("name", ""),
                "market_cap": row.get("market_cap"),
                "industry": row.get("industry", ""),
                "active_scans": active_scans,
            }
        )

    return {
        "sector": sector,
        "date": target_date,
        "count": len(stocks),
        "stocks": stocks,
    }


# ---------------------------------------------------------------------------
# 7) POST /backfill
# ---------------------------------------------------------------------------


@router.post("/backfill")
async def backfill(days: int = Query(default=65, ge=1, le=365)):
    """Bulk backfill: download 1 year of data, then compute breadth for each
    historical trading day and batch-upsert to ``breadth_snapshots``.
    """
    t0 = time.monotonic()
    sb = _get_supabase()

    # Read universe
    resp = sb.table("monitor_universe").select("symbol, sector").execute()
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=400, detail="Universe is empty. Run /refresh-universe first.")

    tickers = [r["symbol"] for r in rows]
    sector_map = {r["symbol"]: r.get("sector", "Unknown") for r in rows}
    logger.info("Backfill: %d tickers, %d days", len(tickers), days)

    # Single bulk download with period="1y" for ample history
    raw_df = await asyncio.to_thread(
        yf.download,
        tickers,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw_df is None or raw_df.empty:
        raise HTTPException(status_code=502, detail="yfinance download returned empty data.")

    # Determine trading days to backfill
    trading_days = raw_df.index[-days:]
    snapshots: list[dict] = []

    for i, trade_date in enumerate(trading_days):
        # Slice DataFrame up to and including this date
        slice_df = raw_df.loc[:trade_date]

        if len(slice_df) < 70:
            # Not enough history for 65-day lookback scans
            continue

        scans = _compute_breadth_scans(slice_df, tickers)
        theme = _compute_theme_tracker(slice_df, tickers, sector_map)

        snap_date = trade_date.date() if hasattr(trade_date, "date") else trade_date
        snapshots.append(
            {
                "date": str(snap_date),
                "universe": "large_cap_1b",
                "scans": scans,
                "theme_tracker": theme,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Batch upsert
    if snapshots:
        upsert_batch_size = 50
        for i in range(0, len(snapshots), upsert_batch_size):
            batch = snapshots[i : i + upsert_batch_size]
            sb.table("breadth_snapshots").upsert(batch, on_conflict="date").execute()

    elapsed = round(time.monotonic() - t0, 2)
    logger.info("Backfill complete: %d snapshots in %.1fs", len(snapshots), elapsed)

    return {
        "status": "ok",
        "snapshots_created": len(snapshots),
        "days_requested": days,
        "duration_seconds": elapsed,
    }
