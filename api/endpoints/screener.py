"""Screener orchestrator — batch Saty analysis + momentum scanner.

Saty scan: reuses canonical data-fetching helpers from satyland.py.
Momentum scan: replicates TOS Saty Momentum Scanner using yfinance bulk download.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.endpoints.satyland import (
    TIMEFRAME_TO_MODE,
    _fetch_atr_source,
    _fetch_daily,
    _fetch_intraday,
    _fetch_mtf_ribbons,
)
from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import price_structure
from api.utils.market_hours import resolve_use_current_close

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "skip": 3}


class ScanRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=100)
    timeframe: str = Field(default="1d")
    direction: str = Field(default="bullish")
    vix: float | None = Field(default=None, description="Current VIX level for bias filter")


class ScanResultItem(BaseModel):
    ticker: str
    grade: str
    score: int
    atr_levels: dict[str, Any]
    pivot_ribbon: dict[str, Any]
    phase_oscillator: dict[str, Any]
    green_flag: dict[str, Any]
    price_structure: dict[str, Any]
    error: str | None = None


class ScanResponse(BaseModel):
    results: list[ScanResultItem]
    total: int
    scanned: int
    errors: int


async def calculate_trade_plan(
    ticker: str,
    timeframe: str,
    direction: str,
    vix: float | None = None,
) -> dict[str, Any]:
    """Run the full Saty indicator stack for a single ticker.

    Uses the canonical satyland.py helpers for data fetching to ensure:
    - Correct trading mode derivation from timeframe
    - Two-DataFrame ATR pattern (atr_source_df + intraday_df)
    - Canonical TIMEFRAME_MAP for yfinance intervals
    - MTF ribbon alignment for Green Flag grading
    """
    mode = TIMEFRAME_TO_MODE.get(timeframe, "day")
    ucc = resolve_use_current_close()

    # Fetch data off the event loop using canonical helpers
    atr_source_df = await asyncio.to_thread(_fetch_atr_source, ticker, mode)
    daily_df = (
        await asyncio.to_thread(_fetch_daily, ticker) if mode != "day" else atr_source_df
    )
    intraday_df = await asyncio.to_thread(_fetch_intraday, ticker, timeframe)

    # Run indicators with correct two-DataFrame pattern
    atr_result = atr_levels(
        atr_source_df,
        intraday_df=intraday_df,
        trading_mode=mode,
        use_current_close=ucc,
    )
    ribbon_result = pivot_ribbon(intraday_df)
    phase_result = phase_oscillator(intraday_df)
    structure_result = price_structure(daily_df, use_current_close=ucc)

    # Fetch MTF ribbons for Green Flag alignment check
    mtf_ribbons = await _fetch_mtf_ribbons(ticker, timeframe)

    flag_result = green_flag_checklist(
        atr_result,
        ribbon_result,
        phase_result,
        structure_result,
        direction,
        vix,
        mtf_ribbons=mtf_ribbons,
    )

    return {
        "ticker": ticker,
        "atr_levels": atr_result,
        "pivot_ribbon": ribbon_result,
        "phase_oscillator": phase_result,
        "price_structure": structure_result,
        "green_flag": flag_result,
        "direction": direction,
    }


@router.post("/scan")
async def scan(request: ScanRequest) -> ScanResponse:
    """Scan tickers through the Saty indicator stack and return graded results.

    Processes tickers concurrently (max 5 at a time) using asyncio.gather
    with a semaphore, matching the satyland.py batch_calculate pattern.
    """
    sem = asyncio.Semaphore(5)

    async def _process_one(ticker: str) -> ScanResultItem:
        async with sem:
            try:
                plan = await calculate_trade_plan(
                    ticker, request.timeframe, request.direction, request.vix,
                )
                return ScanResultItem(
                    ticker=ticker.upper(),
                    grade=plan["green_flag"]["grade"],
                    score=plan["green_flag"]["score"],
                    atr_levels=plan["atr_levels"],
                    pivot_ribbon=plan["pivot_ribbon"],
                    phase_oscillator=plan["phase_oscillator"],
                    green_flag=plan["green_flag"],
                    price_structure=plan["price_structure"],
                )
            except Exception as exc:
                logger.warning("Screener failed for %s: %s", ticker, exc)
                return ScanResultItem(
                    ticker=ticker.upper(),
                    grade="skip",
                    score=0,
                    atr_levels={},
                    pivot_ribbon={},
                    phase_oscillator={},
                    green_flag={},
                    price_structure={},
                    error=str(exc),
                )

    results = list(await asyncio.gather(*(_process_one(t) for t in request.tickers)))
    errors = sum(1 for r in results if r.grade == "skip" and r.error)

    # Sort: A+ first, then A, then B, then skip. Within same grade, higher score first.
    results.sort(key=lambda r: (GRADE_ORDER.get(r.grade, 99), -r.score))

    return ScanResponse(
        results=results,
        total=len(request.tickers),
        scanned=len(request.tickers) - errors,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Momentum Scanner — replicates TOS "Saty's Momentum Scanner"
# ---------------------------------------------------------------------------

UNIVERSE_PATH = Path(__file__).parent.parent / "data" / "universe.json"

# TOS criteria: (label, trading_days_lookback, pct_threshold)
MOMENTUM_CRITERIA = [
    ("weekly_10pct", 5, 10.0),
    ("monthly_25pct", 21, 25.0),
    ("3month_50pct", 63, 50.0),
    ("6month_100pct", 126, 100.0),
]


class MomentumScanRequest(BaseModel):
    """Request for the momentum scanner."""

    universes: list[str] = Field(
        default=["sp500", "nasdaq100"],
        description="Universe keys: sp500, nasdaq100, russell2000, or all",
    )
    min_price: float = Field(default=4.0, ge=0, description="Minimum ask/close price")
    custom_tickers: list[str] | None = Field(
        default=None, max_length=500, description="Extra tickers to include",
    )


class MomentumCriterion(BaseModel):
    """A single momentum criterion that was met."""

    label: str
    pct_change: float
    threshold: float
    lookback_days: int


class MomentumHit(BaseModel):
    """A stock that passed at least one momentum criterion."""

    ticker: str
    last_close: float
    criteria_met: list[MomentumCriterion]
    max_pct_change: float
    weekly_pct: float | None = None
    monthly_pct: float | None = None
    three_month_pct: float | None = None
    six_month_pct: float | None = None


class MomentumScanResponse(BaseModel):
    """Response for the momentum scanner."""

    hits: list[MomentumHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    universes_used: list[str]


def _load_universe(universes: list[str]) -> list[str]:
    """Load and merge ticker lists from universe.json.

    Args:
        universes: Keys to merge (sp500, nasdaq100, russell2000, all).

    Returns:
        Deduplicated sorted list of tickers.
    """
    if not UNIVERSE_PATH.exists():
        raise FileNotFoundError(
            f"Universe file not found at {UNIVERSE_PATH}. "
            "Run: python scripts/seed_universe.py"
        )

    data = json.loads(UNIVERSE_PATH.read_text())

    # "all" is a shortcut for the pre-built deduplicated list
    if "all" in universes:
        return data["all_unique"]

    seen: set[str] = set()
    result: list[str] = []
    for key in universes:
        for ticker in data.get(key, []):
            upper = ticker.upper()
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
    result.sort()
    return result


def _compute_momentum(
    raw_df: pd.DataFrame,
    tickers: list[str],
    min_price: float,
) -> tuple[list[MomentumHit], int, int]:
    """Score tickers against TOS momentum criteria.

    Args:
        raw_df: MultiIndex DataFrame from yf.download (columns: Price x Ticker).
        tickers: List of tickers to process.
        min_price: Minimum last close price to include.

    Returns:
        (hits, error_count, skipped_low_price_count)
    """
    hits: list[MomentumHit] = []
    errors = 0
    skipped = 0

    is_multi = isinstance(raw_df.columns, pd.MultiIndex)

    for ticker in tickers:
        try:
            # Extract close series for this ticker
            if is_multi:
                if ("Close", ticker) not in raw_df.columns:
                    errors += 1
                    continue
                close = raw_df[("Close", ticker)].dropna()
            else:
                # Single-ticker download returns flat columns
                if "Close" not in raw_df.columns:
                    errors += 1
                    continue
                close = raw_df["Close"].dropna()

            if len(close) < 2:
                errors += 1
                continue

            last_close = float(close.iloc[-1])

            # Price filter (TOS: Ask >= $4.00)
            if last_close < min_price:
                skipped += 1
                continue

            # Compute % changes at each lookback
            pct_changes: dict[str, float | None] = {}
            criteria_met: list[MomentumCriterion] = []

            pct_label_map = {
                "weekly_10pct": "weekly_pct",
                "monthly_25pct": "monthly_pct",
                "3month_50pct": "three_month_pct",
                "6month_100pct": "six_month_pct",
            }

            for label, lookback, threshold in MOMENTUM_CRITERIA:
                if len(close) > lookback:
                    past_close = float(close.iloc[-(lookback + 1)])
                    if past_close > 0:
                        pct = ((last_close - past_close) / past_close) * 100
                    else:
                        pct = 0.0
                    pct_changes[pct_label_map[label]] = round(pct, 2)

                    if pct >= threshold:
                        criteria_met.append(
                            MomentumCriterion(
                                label=label,
                                pct_change=round(pct, 2),
                                threshold=threshold,
                                lookback_days=lookback,
                            )
                        )
                else:
                    pct_changes[pct_label_map[label]] = None

            if criteria_met:
                max_pct = max(c.pct_change for c in criteria_met)
                hits.append(
                    MomentumHit(
                        ticker=ticker,
                        last_close=round(last_close, 2),
                        criteria_met=criteria_met,
                        max_pct_change=round(max_pct, 2),
                        **pct_changes,
                    )
                )

        except Exception as exc:
            logger.debug("Momentum scan error for %s: %s", ticker, exc)
            errors += 1

    return hits, errors, skipped


@router.post("/momentum-scan")
async def momentum_scan(request: MomentumScanRequest) -> MomentumScanResponse:
    """Scan universe for momentum breakouts (replicates TOS Saty Momentum Scanner).

    Downloads ~7 months of daily data via yfinance bulk download, then filters
    stocks by price and checks 4 momentum criteria (OR logic):
    - Weekly close >= 10% above 1 week ago
    - Monthly close >= 25% above 1 month ago
    - 3-month close >= 50% above 3 months ago
    - 6-month close >= 100% above 6 months ago
    """
    t0 = time.monotonic()

    # Build ticker list
    tickers = await asyncio.to_thread(_load_universe, request.universes)
    if request.custom_tickers:
        existing = set(tickers)
        for t in request.custom_tickers:
            upper = t.strip().upper()
            if upper and upper not in existing:
                tickers.append(upper)
                existing.add(upper)

    logger.info("Momentum scan: %d tickers from %s", len(tickers), request.universes)

    # Bulk download ~7 months of daily data (covers 126 trading days + buffer)
    raw_df = await asyncio.to_thread(
        yf.download,
        tickers,
        period="7mo",
        interval="1d",
        progress=False,
        threads=True,
    )

    if raw_df is None or raw_df.empty:
        return MomentumScanResponse(
            hits=[],
            total_scanned=len(tickers),
            total_hits=0,
            total_errors=len(tickers),
            skipped_low_price=0,
            scan_duration_seconds=round(time.monotonic() - t0, 2),
            universes_used=request.universes,
        )

    # Score against momentum criteria
    hits, errors, skipped = _compute_momentum(raw_df, tickers, request.min_price)

    # Sort by max_pct_change descending
    hits.sort(key=lambda h: h.max_pct_change, reverse=True)

    duration = round(time.monotonic() - t0, 2)
    logger.info(
        "Momentum scan complete: %d hits, %d errors, %d skipped, %.1fs",
        len(hits), errors, skipped, duration,
    )

    return MomentumScanResponse(
        hits=hits,
        total_scanned=len(tickers),
        total_hits=len(hits),
        total_errors=errors,
        skipped_low_price=skipped,
        scan_duration_seconds=duration,
        universes_used=request.universes,
    )
