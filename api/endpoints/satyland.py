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
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import (
    key_pivots,
    open_gaps,
    price_structure,
)
from api.utils.market_hours import resolve_use_current_close

router = APIRouter(prefix="/api/satyland", tags=["satyland"])

# Intraday timeframe → (yfinance period, yfinance interval)
TIMEFRAME_MAP = {
    "1m": ("1d", "1m"),
    "5m": ("5d", "5m"),
    "15m": ("5d", "15m"),
    "1h": ("1mo", "1h"),
    "4h": ("3mo", "60m"),
    "1d": ("1y", "1d"),
    "1w": ("5y", "1wk"),
}


# Chart timeframe → default ATR trading mode (Pine Script mapping)
TIMEFRAME_TO_MODE: dict[str, str] = {
    "1m": "day",
    "5m": "day",
    "15m": "day",  # intraday → daily ATR
    "1h": "multiday",
    "4h": "multiday",  # hourly → weekly ATR
    "1d": "swing",  # daily → monthly ATR
    "1w": "position",  # weekly → quarterly ATR
}

# Chart timeframe → higher timeframes to check for MTF ribbon alignment
HIGHER_TIMEFRAMES: dict[str, list[str]] = {
    "1m": ["1h", "1d", "1w"],
    "5m": ["1h", "1d", "1w"],
    "15m": ["1h", "1d", "1w"],
    "1h": ["4h", "1d", "1w"],
    "4h": ["1d", "1w"],
    "1d": ["1w"],
    "1w": [],
}


class CalculateRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"] = Field("5m")
    trading_mode: Literal["day", "multiday", "swing", "position"] | None = Field(
        None, description="ATR trading mode. Auto-derived from timeframe if not set."
    )
    atr_period: int = Field(14, ge=5, le=50)
    include_extensions: bool = Field(
        False, description="Include Valhalla extension levels beyond 100%"
    )
    use_current_close: bool | None = Field(
        None,
        description="Anchor at current bar (True) or previous bar (False). Auto-detects from market hours if None.",
    )


class BatchCalculateRequest(BaseModel):
    tickers: list[str] = Field(
        ..., description="List of ticker symbols (max 20)", min_length=1, max_length=20
    )
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


class PremarketRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. SPY or ^VIX")


# Indices that truly have NO premarket data (price indices, not computed)
_NO_PREMARKET = {"^GSPC"}  # SPX = price index, no extended hours


def _fetch_premarket(ticker: str) -> pd.DataFrame | None:
    """Fetch today's premarket bars (4:00-9:30 AM ET) via yfinance.

    Uses yf.Ticker.history() instead of yf.download() — see _fetch_daily
    docstring for rationale.

    Skips only ^GSPC (price index — no extended hours).
    Allows ^VIX (CBOE publishes VIX during extended hours).
    Returns None gracefully on any failure — premarket is optional.
    """
    if ticker in _NO_PREMARKET:
        return None
    try:
        df = yf.Ticker(ticker).history(
            period="5d", interval="1m", prepost=True, auto_adjust=True
        )
        if df.empty:
            return None
        df = _normalise_columns(df)
        # Filter to today's premarket window (4:00-9:30 AM ET)
        ET = ZoneInfo("America/New_York")
        today = datetime.now(ET).strftime("%Y-%m-%d")
        start = pd.Timestamp(f"{today} 04:00", tz=ET)
        end = pd.Timestamp(f"{today} 09:30", tz=ET)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(ET)
        else:
            df.index = df.index.tz_convert(ET)
        pm = df.loc[(df.index >= start) & (df.index < end)]
        return pm if not pm.empty else None
    except Exception:
        return None


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance, lowercase, and select OHLCV.

    yf.Ticker.history() returns extra columns (Dividends, Stock Splits)
    that can contain NaN at edges. We select only OHLCV to prevent
    dropna() from discarding valid price bars due to NaN in those columns.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0].lower() for col in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    # Keep only OHLCV columns — extra columns from yf.Ticker.history()
    # (dividends, stock splits, capital gains) can cause false dropna() drops.
    ohlcv = ["open", "high", "low", "close", "volume"]
    available = [c for c in ohlcv if c in df.columns]
    df = df[available]
    return df.dropna()


def _fetch_daily(ticker: str, lookback: str = "3mo") -> pd.DataFrame:
    """
    Fetch daily OHLCV — used for ATR Levels (PDC, daily ATR) and Price Structure.
    Pine Script fetches daily data regardless of chart timeframe for ATR Levels.

    Uses yf.Ticker.history() instead of yf.download() because download()
    auto-batches concurrent calls and returns merged MultiIndex DataFrames,
    causing all tickers to receive the same data.
    """
    df = yf.Ticker(ticker).history(period=lookback, interval="1d", auto_adjust=True)
    if df.empty:
        raise ValueError(f"No daily data for {ticker}")
    return _normalise_columns(df)


def _resample_to_quarterly(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly bars into quarterly OHLCV (yfinance has no 3M interval)."""
    return (
        monthly_df.resample("QS")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum" if "volume" in monthly_df.columns else "first",
            }
        )
        .dropna()
    )


def _fetch_atr_source(ticker: str, trading_mode: str) -> pd.DataFrame:
    """Fetch OHLCV at the timeframe matching the ATR trading mode.

    Uses yf.Ticker.history() instead of yf.download() — see _fetch_daily
    docstring for rationale.

    Pine Script mapping:
      Day      → daily bars   (request.security D)
      Multiday → weekly bars  (request.security W)
      Swing    → monthly bars (request.security M)
      Position → quarterly bars (request.security 3M, aggregated from monthly)
    """
    if trading_mode == "day":
        return _fetch_daily(ticker, lookback="3mo")
    elif trading_mode == "multiday":
        df = yf.Ticker(ticker).history(period="2y", interval="1wk", auto_adjust=True)
        if df.empty:
            raise ValueError(f"No weekly data for {ticker}")
        return _normalise_columns(df)
    elif trading_mode == "swing":
        df = yf.Ticker(ticker).history(period="10y", interval="1mo", auto_adjust=True)
        if df.empty:
            raise ValueError(f"No monthly data for {ticker}")
        return _normalise_columns(df)
    elif trading_mode == "position":
        df = yf.Ticker(ticker).history(period="10y", interval="1mo", auto_adjust=True)
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
    """Fetch intraday OHLCV for Pivot Ribbon and Phase Oscillator.

    Uses yf.Ticker.history() instead of yf.download() — see _fetch_daily
    docstring for rationale.
    """
    t = yf.Ticker(ticker)
    if timeframe == "1d":
        # If daily requested, use a longer window for EMA stability
        df = t.history(period="1y", interval="1d", auto_adjust=True)
    elif timeframe == "1w":
        df = t.history(period="5y", interval="1wk", auto_adjust=True)
    else:
        period, interval = TIMEFRAME_MAP[timeframe]
        df = t.history(period=period, interval=interval, auto_adjust=True)
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
        intraday_df = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr = atr_levels(
            atr_source_df,
            intraday_df=intraday_df,
            atr_period=req.atr_period,
            include_extensions=req.include_extensions,
            trading_mode=mode,
            use_current_close=ucc,
        )
        ribbon = pivot_ribbon(intraday_df)
        phase = phase_oscillator(intraday_df)

        return JSONResponse(
            content={
                "ticker": req.ticker.upper(),
                "timeframe": req.timeframe,
                "trading_mode": mode,
                "use_current_close": ucc,
                "bars": len(intraday_df),
                "atr_source_bars": len(atr_source_df),
                "atr_levels": atr,
                "pivot_ribbon": ribbon,
                "phase_oscillator": phase,
            },
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Calculation failed: {exc}"
        ) from exc


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
        daily_df = _fetch_daily(req.ticker) if mode != "day" else atr_source_df
        daily_long_df = _fetch_daily(req.ticker, lookback="2y")
        intraday_df = _fetch_intraday(req.ticker, req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        atr = atr_levels(
            atr_source_df,
            intraday_df=intraday_df,
            atr_period=req.atr_period,
            include_extensions=req.include_extensions,
            trading_mode=mode,
            use_current_close=ucc,
        )
        ribbon = pivot_ribbon(intraday_df)
        phase = phase_oscillator(intraday_df)

        # Fetch premarket data for SPY (skips ^GSPC automatically)
        premarket_df = _fetch_premarket(req.ticker)
        struct = price_structure(
            daily_df, premarket_df=premarket_df, use_current_close=ucc
        )

        # Add premarket last price if available (for real-time positioning)
        if premarket_df is not None and not premarket_df.empty:
            struct["premarket_price"] = round(float(premarket_df["close"].iloc[-1]), 4)
        pivots = key_pivots(daily_long_df, use_current_close=ucc)
        # Scan last ~6 months for unfilled gaps
        gaps_df = daily_long_df.loc[
            daily_long_df.index >= daily_long_df.index[-1] - pd.DateOffset(months=6)
        ]
        gaps = open_gaps(gaps_df)

        # Fetch MTF ribbons and phases in parallel
        mtf_ribbons, mtf_phases = await asyncio.gather(
            _fetch_mtf_ribbons(req.ticker, req.timeframe),
            _fetch_mtf_phases(req.ticker, req.timeframe),
        )

        flags = green_flag_checklist(
            atr, ribbon, phase, struct, req.direction, req.vix, mtf_ribbons=mtf_ribbons
        )

        return JSONResponse(
            content={
                "ticker": req.ticker.upper(),
                "timeframe": req.timeframe,
                "trading_mode": mode,
                "use_current_close": ucc,
                "direction": req.direction,
                "bars": len(intraday_df),
                "atr_levels": atr,
                "pivot_ribbon": ribbon,
                "phase_oscillator": phase,
                "price_structure": struct,
                "key_pivots": pivots,
                "open_gaps": gaps,
                "green_flag": flags,
                "mtf_ribbons": mtf_ribbons,
                "mtf_phases": mtf_phases,
            },
            headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Trade plan failed: {exc}"
        ) from exc


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
                daily_df = (
                    await asyncio.to_thread(_fetch_daily, ticker)
                    if mode != "day"
                    else atr_source_df
                )
                daily_long_df = await asyncio.to_thread(_fetch_daily, ticker, "2y")
                intraday_df = await asyncio.to_thread(
                    _fetch_intraday, ticker, req.timeframe
                )

                atr = atr_levels(
                    atr_source_df,
                    intraday_df=intraday_df,
                    atr_period=req.atr_period,
                    trading_mode=mode,
                    use_current_close=ucc,
                )
                ribbon = pivot_ribbon(intraday_df)
                phase = phase_oscillator(intraday_df)
                struct = price_structure(daily_df, use_current_close=ucc)
                pivots = key_pivots(daily_long_df, use_current_close=ucc)
                gaps_df = daily_long_df.loc[
                    daily_long_df.index
                    >= daily_long_df.index[-1] - pd.DateOffset(months=6)
                ]
                gaps = open_gaps(gaps_df)
                mtf, mtf_ph = await asyncio.gather(
                    _fetch_mtf_ribbons(ticker, req.timeframe),
                    _fetch_mtf_phases(ticker, req.timeframe),
                )
                flags = green_flag_checklist(
                    atr, ribbon, phase, struct, req.direction, mtf_ribbons=mtf
                )

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
                        "open_gaps": gaps,
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

    results = await asyncio.gather(*(process_one(t) for t in req.tickers))
    return JSONResponse(
        content={"results": results},
        headers={"Cache-Control": "s-maxage=60, stale-while-revalidate=300"},
    )


@router.post("/premarket")
async def get_premarket(req: PremarketRequest):
    """
    Return premarket high/low/last for a ticker.

    Works for SPY, ^VIX, and other tickers with extended hours data.
    Returns null values gracefully when no premarket data is available
    (e.g., after market close, weekends, or unsupported tickers).
    """
    pm = _fetch_premarket(req.ticker)
    if pm is None or pm.empty:
        return JSONResponse(
            content={
                "ticker": req.ticker.upper(),
                "price": None,
                "high": None,
                "low": None,
            },
            headers={"Cache-Control": "s-maxage=30, stale-while-revalidate=60"},
        )
    return JSONResponse(
        content={
            "ticker": req.ticker.upper(),
            "price": round(float(pm["close"].iloc[-1]), 4),
            "high": round(float(pm["high"].max()), 4),
            "low": round(float(pm["low"].min()), 4),
        },
        headers={"Cache-Control": "s-maxage=30, stale-while-revalidate=60"},
    )
