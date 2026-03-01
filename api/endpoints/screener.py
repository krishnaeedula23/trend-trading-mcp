"""Screener orchestrator — batch Saty analysis with grade ranking.

Reuses the canonical data-fetching helpers from satyland.py to ensure
correct trading mode derivation, two-DataFrame ATR pattern, and MTF ribbons.
"""

import asyncio
import logging
from typing import Any

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
