"""
Satyland indicator endpoints — exact ports of Saty Trading System Pine Scripts.

ATR Levels use higher-timeframe data based on the trading mode:
  Day (intraday charts) → daily ATR/PDC
  Multiday (hourly charts) → weekly ATR/PDC
  Swing (daily charts) → monthly ATR/PDC
  Position (weekly charts) → quarterly ATR/PDC

Pivot Ribbon and Phase Oscillator run on the requested chart timeframe.
"""

import asyncio
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
from api.indicators.satyland.price_structure import price_structure, key_pivots
from api.utils.market_hours import resolve_use_current_close

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


# Chart timeframe → default ATR trading mode (Pine Script mapping)
TIMEFRAME_TO_MODE: dict[str, str] = {
    "1m": "day", "5m": "day", "15m": "day",       # intraday → daily ATR
    "1h": "multiday", "4h": "multiday",             # hourly → weekly ATR
    "1d": "swing",                                   # daily → monthly ATR
    "1w": "position",                                # weekly → quarterly ATR
}

# Chart timeframe → higher timeframes to check for MTF ribbon alignment
HIGHER_TIMEFRAMES: dict[str, list[str]] = {
    "1m":  ["1h", "1d", "1w"],
    "5m":  ["1h", "1d", "1w"],
    "15m": ["1h", "1d", "1w"],
    "1h":  ["4h", "1d", "1w"],
    "4h":  ["1d", "1w"],
    "1d":  ["1w"],
    "1w":  [],
}


class CalculateRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    trading_mode: Literal["day", "multiday", "swing", "position"] | None = Field(
        None, description="ATR trading mode. Auto-derived from timeframe if not set."
    )
    atr_period: int = Field(14, ge=5, le=50)
    include_extensions: bool = Field(False, description="Include Valhalla extension levels beyond 100%")
    use_current_close: bool | None = Field(
        None, description="Anchor at current bar (True) or previous bar (False). Auto-detects from market hours if None."
    )


class BatchCalculateRequest(BaseModel):
    tickers: list[str] = Field(..., description="List of ticker symbols (max 20)", min_length=1, max_length=20)
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    direction: Literal["bullish", "bearish"] = Field("bullish")
    trading_mode: Literal["day", "multiday", "swing", "position"] | None = Field(None)
    atr_period: int = Field(14, ge=5, le=50)
    use_current_close: bool | None = Field(None)


class TradePlanRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    trading_mode: Literal["day", "multiday", "swing", "position"] | None = Field(
        None, description="ATR trading mode. Auto-derived from timeframe if not set."
    )
    direction: Literal["bullish", "bearish"] = Field(..., description="Trade direction")
    vix: float | None = Field(None, description="Current VIX level for bias filter")
    atr_period: int = Field(14, ge=5, le=50)
    include_extensions: bool = Field(False)
    use_current_close: bool | None = Field(None)


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


def _resample_to_quarterly(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly bars into quarterly OHLCV (yfinance has no 3M interval)."""
    return monthly_df.resample("QS").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum" if "volume" in monthly_df.columns else "first",
    }).dropna()


def _fetch_atr_source(ticker: str, trading_mode: str) -> pd.DataFrame:
    """
    Fetch OHLCV at the timeframe matching the ATR trading mode.

    Pine Script mapping:
      Day      → daily bars   (request.security D)
      Multiday → weekly bars  (request.security W)
      Swing    → monthly bars (request.security M)
      Position → quarterly bars (request.security 3M, aggregated from monthly)
    """
    if trading_mode == "day":
        return _fetch_daily(ticker, lookback="3mo")
    elif trading_mode == "multiday":
        df = yf.download(ticker, period="2y", interval="1wk",
                         auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No weekly data for {ticker}")
        return _normalise_columns(df)
    elif trading_mode == "swing":
        df = yf.download(ticker, period="10y", interval="1mo",
                         auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No monthly data for {ticker}")
        return _normalise_columns(df)
    elif trading_mode == "position":
        df = yf.download(ticker, period="10y", interval="1mo",
                         auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No monthly data for {ticker}")
        monthly = _normalise_columns(df)
        quarterly = _resample_to_quarterly(monthly)
        if len(quarterly) < 2:
            raise ValueError(f"Not enough quarterly data for {ticker}")
        return quarterly
    else:
        return _fetch_daily(ticker, lookback="3mo")


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

    ATR Levels use higher-timeframe data based on trading mode (auto-derived
    from chart timeframe if not specified). Pivot Ribbon and Phase Oscillator
    use the requested chart timeframe.
    """
    mode = req.trading_mode or TIMEFRAME_TO_MODE.get(req.timeframe, "day")
    ucc = resolve_use_current_close(req.use_current_close)
    try:
        atr_source_df = _fetch_atr_source(req.ticker, mode)
        intraday_df   = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr    = atr_levels(atr_source_df, intraday_df=intraday_df,
                            atr_period=req.atr_period,
                            include_extensions=req.include_extensions,
                            trading_mode=mode,
                            use_current_close=ucc)
        ribbon = pivot_ribbon(intraday_df)
        phase  = phase_oscillator(intraday_df)

        return JSONResponse(
            content={
                "ticker":           req.ticker.upper(),
                "timeframe":        req.timeframe,
                "trading_mode":     mode,
                "use_current_close": ucc,
                "bars":             len(intraday_df),
                "atr_source_bars":  len(atr_source_df),
                "atr_levels":       atr,
                "pivot_ribbon":     ribbon,
                "phase_oscillator": phase,
            },
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {exc}") from exc


async def _fetch_mtf_ribbons(ticker: str, timeframe: str) -> dict[str, dict]:
    """Fetch pivot ribbon for each higher timeframe in parallel."""
    higher_tfs = HIGHER_TIMEFRAMES.get(timeframe, [])
    if not higher_tfs:
        return {}

    async def _compute_ribbon(tf: str) -> tuple[str, dict | None]:
        try:
            df = await asyncio.to_thread(_fetch_intraday, ticker, tf)
            return tf, pivot_ribbon(df)
        except Exception:
            return tf, None

    results = await asyncio.gather(*(_compute_ribbon(tf) for tf in higher_tfs))
    return {tf: r for tf, r in results if r is not None}


async def _fetch_mtf_phases(ticker: str, timeframe: str) -> dict[str, dict]:
    """Fetch phase oscillator for each higher timeframe in parallel."""
    higher_tfs = HIGHER_TIMEFRAMES.get(timeframe, [])
    if not higher_tfs:
        return {}

    async def _compute_phase(tf: str) -> tuple[str, dict | None]:
        try:
            df = await asyncio.to_thread(_fetch_intraday, ticker, tf)
            return tf, phase_oscillator(df)
        except Exception:
            return tf, None

    results = await asyncio.gather(*(_compute_phase(tf) for tf in higher_tfs))
    return {tf: r for tf, r in results if r is not None}


@router.post("/trade-plan")
async def trade_plan(req: TradePlanRequest):
    """
    Full Saty trade plan: all indicators + price structure + Green Flag Checklist.
    Returns A+/A/B/skip grade with verbal audit.

    ATR Levels use the trading mode's timeframe. Price Structure always uses
    daily data (PDH/PDL are inherently daily concepts).
    """
    mode = req.trading_mode or TIMEFRAME_TO_MODE.get(req.timeframe, "day")
    ucc = resolve_use_current_close(req.use_current_close)
    try:
        atr_source_df = _fetch_atr_source(req.ticker, mode)
        daily_df      = _fetch_daily(req.ticker) if mode != "day" else atr_source_df
        daily_long_df = _fetch_daily(req.ticker, lookback="2y")
        intraday_df   = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr    = atr_levels(atr_source_df, intraday_df=intraday_df,
                            atr_period=req.atr_period,
                            include_extensions=req.include_extensions,
                            trading_mode=mode,
                            use_current_close=ucc)
        ribbon = pivot_ribbon(intraday_df)
        phase  = phase_oscillator(intraday_df)
        struct = price_structure(daily_df, use_current_close=ucc)
        pivots = key_pivots(daily_long_df, use_current_close=ucc)

        # Fetch MTF ribbons and phases in parallel
        mtf_ribbons, mtf_phases = await asyncio.gather(
            _fetch_mtf_ribbons(req.ticker, req.timeframe),
            _fetch_mtf_phases(req.ticker, req.timeframe),
        )

        flags  = green_flag_checklist(atr, ribbon, phase, struct, req.direction,
                                      req.vix, mtf_ribbons=mtf_ribbons)

        return JSONResponse(
            content={
                "ticker":           req.ticker.upper(),
                "timeframe":        req.timeframe,
                "trading_mode":     mode,
                "use_current_close": ucc,
                "direction":        req.direction,
                "bars":             len(intraday_df),
                "atr_levels":       atr,
                "pivot_ribbon":     ribbon,
                "phase_oscillator": phase,
                "price_structure":  struct,
                "key_pivots":       pivots,
                "green_flag":       flags,
                "mtf_ribbons":      mtf_ribbons,
                "mtf_phases":       mtf_phases,
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


@router.post("/batch-calculate")
async def batch_calculate(req: BatchCalculateRequest):
    """
    Run trade-plan calculation for multiple tickers in parallel.
    Returns { results: [{ ticker, success, data?, error? }, ...] }.
    """
    mode = req.trading_mode or TIMEFRAME_TO_MODE.get(req.timeframe, "day")
    ucc = resolve_use_current_close(req.use_current_close)
    sem = asyncio.Semaphore(5)

    async def process_one(ticker: str) -> dict:
        async with sem:
            try:
                atr_source_df = await asyncio.to_thread(_fetch_atr_source, ticker, mode)
                daily_df = await asyncio.to_thread(_fetch_daily, ticker) if mode != "day" else atr_source_df
                daily_long_df = await asyncio.to_thread(_fetch_daily, ticker, "2y")
                intraday_df = await asyncio.to_thread(_fetch_intraday, ticker, req.timeframe)

                atr = atr_levels(atr_source_df, intraday_df=intraday_df,
                                 atr_period=req.atr_period, trading_mode=mode,
                                 use_current_close=ucc)
                ribbon = pivot_ribbon(intraday_df)
                phase = phase_oscillator(intraday_df)
                struct = price_structure(daily_df, use_current_close=ucc)
                pivots = key_pivots(daily_long_df, use_current_close=ucc)
                mtf, mtf_ph = await asyncio.gather(
                    _fetch_mtf_ribbons(ticker, req.timeframe),
                    _fetch_mtf_phases(ticker, req.timeframe),
                )
                flags = green_flag_checklist(atr, ribbon, phase, struct, req.direction,
                                             mtf_ribbons=mtf)

                return {
                    "ticker": ticker.upper(),
                    "success": True,
                    "data": {
                        "ticker": ticker.upper(),
                        "timeframe": req.timeframe,
                        "trading_mode": mode,
                        "use_current_close": ucc,
                        "direction": req.direction,
                        "atr_levels": atr,
                        "pivot_ribbon": ribbon,
                        "phase_oscillator": phase,
                        "price_structure": struct,
                        "key_pivots": pivots,
                        "green_flag": flags,
                        "mtf_ribbons": mtf,
                        "mtf_phases": mtf_ph,
                    },
                }
            except Exception as exc:
                return {
                    "ticker": ticker.upper(),
                    "success": False,
                    "error": str(exc),
                }

    results = await asyncio.gather(
        *(process_one(t) for t in req.tickers)
    )
    return JSONResponse(
        content={"results": results},
        headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
    )
