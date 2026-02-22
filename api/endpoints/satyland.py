"""
Satyland indicator endpoints — exact ports of Saty Trading System Pine Scripts.

ATR Levels always run on DAILY data (matching Pine Script's daily-timeframe request).
Pivot Ribbon and Phase Oscillator run on the requested chart timeframe.
"""

from typing import Literal

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import price_structure

router = APIRouter(prefix="/api/satyland", tags=["satyland"])

# Intraday timeframe → (yfinance period, yfinance interval)
TIMEFRAME_MAP = {
    "1m":  ("1d",  "1m"),
    "5m":  ("5d",  "5m"),
    "15m": ("5d",  "15m"),
    "1h":  ("1mo", "1h"),
    "4h":  ("3mo", "60m"),
    "1d":  ("1y",  "1d"),
    "1w":  ("5y",  "1wk"),
}


class CalculateRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    atr_period: int = Field(14, ge=5, le=50)
    include_extensions: bool = Field(False, description="Include Valhalla extension levels beyond 100%")


class TradePlanRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    direction: Literal["bullish", "bearish"] = Field(..., description="Trade direction")
    vix: float | None = Field(None, description="Current VIX level for bias filter")
    atr_period: int = Field(14, ge=5, le=50)
    include_extensions: bool = Field(False)


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance and lowercase."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0].lower() for col in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    return df.dropna()


def _fetch_daily(ticker: str, lookback: str = "3mo") -> pd.DataFrame:
    """
    Fetch daily OHLCV — used for ATR Levels (PDC, daily ATR) and Price Structure.
    Pine Script fetches daily data regardless of chart timeframe for ATR Levels.
    """
    df = yf.download(ticker, period=lookback, interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No daily data for {ticker}")
    return _normalise_columns(df)


def _fetch_intraday(ticker: str, timeframe: str) -> pd.DataFrame:
    """Fetch intraday OHLCV for Pivot Ribbon and Phase Oscillator."""
    if timeframe == "1d":
        # If daily requested, use a longer window for EMA stability
        df = yf.download(ticker, period="1y", interval="1d",
                         auto_adjust=True, progress=False)
    elif timeframe == "1w":
        df = yf.download(ticker, period="5y", interval="1wk",
                         auto_adjust=True, progress=False)
    else:
        period, interval = TIMEFRAME_MAP[timeframe]
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No {timeframe} data for {ticker}")
    return _normalise_columns(df)


@router.post("/calculate")
async def calculate_indicators(req: CalculateRequest):
    """
    Run all three Saty indicators.

    ATR Levels always use daily OHLCV (PDC + daily ATR) per Pine Script.
    Pivot Ribbon and Phase Oscillator use the requested chart timeframe.
    """
    try:
        daily_df    = _fetch_daily(req.ticker)
        intraday_df = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr    = atr_levels(daily_df, intraday_df=intraday_df,
                            atr_period=req.atr_period,
                            include_extensions=req.include_extensions)
        ribbon = pivot_ribbon(intraday_df)
        phase  = phase_oscillator(intraday_df)

        return JSONResponse(
            content={
                "ticker":           req.ticker.upper(),
                "timeframe":        req.timeframe,
                "bars":             len(intraday_df),
                "daily_bars":       len(daily_df),
                "atr_levels":       atr,
                "pivot_ribbon":     ribbon,
                "phase_oscillator": phase,
            },
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {exc}") from exc


@router.post("/trade-plan")
async def trade_plan(req: TradePlanRequest):
    """
    Full Saty trade plan: all indicators + price structure + Green Flag Checklist.
    Returns A+/A/B/skip grade with verbal audit.
    """
    try:
        daily_df    = _fetch_daily(req.ticker)
        intraday_df = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr    = atr_levels(daily_df, intraday_df=intraday_df,
                            atr_period=req.atr_period,
                            include_extensions=req.include_extensions)
        ribbon = pivot_ribbon(intraday_df)
        phase  = phase_oscillator(intraday_df)
        struct = price_structure(daily_df)
        flags  = green_flag_checklist(atr, ribbon, phase, struct, req.direction, req.vix)

        return JSONResponse(
            content={
                "ticker":           req.ticker.upper(),
                "timeframe":        req.timeframe,
                "direction":        req.direction,
                "bars":             len(intraday_df),
                "atr_levels":       atr,
                "pivot_ribbon":     ribbon,
                "phase_oscillator": phase,
                "price_structure":  struct,
                "green_flag":       flags,
            },
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Trade plan failed: {exc}") from exc


@router.post("/price-structure")
async def get_price_structure(req: CalculateRequest):
    """Return PDH / PDL / PDC and structural bias from daily data."""
    try:
        daily_df = _fetch_daily(req.ticker)
        return JSONResponse(
            content={"ticker": req.ticker.upper(), **price_structure(daily_df)},
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
