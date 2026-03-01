"""Screener orchestrator — batch Saty analysis with grade ranking."""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import price_structure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "skip": 3}


class ScanRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=100)
    timeframe: str = Field(default="1d")
    direction: str = Field(default="bullish")


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


def calculate_trade_plan(ticker: str, timeframe: str, direction: str) -> dict[str, Any]:
    """Run the full Saty indicator stack for a single ticker.

    This mirrors the logic in api/endpoints/satyland.py trade_plan endpoint
    but is importable for batch use.
    """
    import yfinance as yf

    period_map = {
        "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
        "1h": "730d", "4h": "730d", "1d": "2y", "1w": "10y",
    }
    period = period_map.get(timeframe, "2y")
    interval = timeframe if timeframe != "4h" else "1h"

    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        raise ValueError(f"No data for {ticker} at {timeframe}")

    # Flatten multi-index if present (yfinance returns multi-level columns)
    if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)

    # Lowercase column names for indicator compatibility
    df.columns = [c.lower() for c in df.columns]

    atr_result = atr_levels(df)
    ribbon_result = pivot_ribbon(df)
    phase_result = phase_oscillator(df)
    structure_result = price_structure(df)
    flag_result = green_flag_checklist(
        atr=atr_result,
        ribbon=ribbon_result,
        phase=phase_result,
        structure=structure_result,
        direction=direction,
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
    """Scan tickers through the Saty indicator stack and return graded results."""
    results: list[ScanResultItem] = []
    errors = 0

    for ticker in request.tickers:
        try:
            plan = calculate_trade_plan(ticker, request.timeframe, request.direction)
            results.append(ScanResultItem(
                ticker=ticker.upper(),
                grade=plan["green_flag"]["grade"],
                score=plan["green_flag"]["score"],
                atr_levels=plan["atr_levels"],
                pivot_ribbon=plan["pivot_ribbon"],
                phase_oscillator=plan["phase_oscillator"],
                green_flag=plan["green_flag"],
                price_structure=plan["price_structure"],
            ))
        except Exception as exc:
            logger.warning("Screener failed for %s: %s", ticker, exc)
            errors += 1
            results.append(ScanResultItem(
                ticker=ticker.upper(),
                grade="skip",
                score=0,
                atr_levels={},
                pivot_ribbon={},
                phase_oscillator={},
                green_flag={},
                price_structure={},
                error=str(exc),
            ))

    # Sort: A+ first, then A, then B, then skip. Within same grade, higher score first.
    results.sort(key=lambda r: (GRADE_ORDER.get(r.grade, 99), -r.score))

    return ScanResponse(
        results=results,
        total=len(request.tickers),
        scanned=len(request.tickers) - errors,
        errors=errors,
    )
