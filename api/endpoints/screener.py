"""Screener orchestrator — batch Saty analysis + momentum scanner.

Saty scan: reuses canonical data-fetching helpers from satyland.py.
Momentum scan: replicates TOS Saty Momentum Scanner using yfinance bulk download.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Literal

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
    _fetch_premarket,
)
from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import price_structure
from api.utils.market_hours import resolve_use_current_close

# Default chart timeframe for each trading mode (reverse of TIMEFRAME_TO_MODE).
# Used by scanners that specify a trading_mode but need intraday_df for the
# two-DataFrame ATR pattern.
_MODE_DEFAULT_TF: dict[str, str] = {
    "day": "15m",
    "multiday": "1h",
    "swing": "1d",
    "position": "1w",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "skip": 3}


class ScanRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=100)
    timeframe: str = Field(default="1d")
    direction: str = Field(default="bullish")
    vix: float | None = Field(
        default=None, description="Current VIX level for bias filter"
    )


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
        await asyncio.to_thread(_fetch_daily, ticker)
        if mode != "day"
        else atr_source_df
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
                    ticker,
                    request.timeframe,
                    request.direction,
                    request.vix,
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
        default=None,
        max_length=500,
        description="Extra tickers to include",
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
        auto_adjust=True,
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

    # Score against momentum criteria (off event loop — iterates 700+ tickers)
    hits, errors, skipped = await asyncio.to_thread(
        _compute_momentum,
        raw_df,
        tickers,
        request.min_price,
    )

    # Sort by max_pct_change descending
    hits.sort(key=lambda h: h.max_pct_change, reverse=True)

    duration = round(time.monotonic() - t0, 2)
    logger.info(
        "Momentum scan complete: %d hits, %d errors, %d skipped, %.1fs",
        len(hits),
        errors,
        skipped,
        duration,
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


# ---------------------------------------------------------------------------
# Golden Gate Scanner — ATR-based signal scanner
# ---------------------------------------------------------------------------


class GoldenGateScanRequest(BaseModel):
    """Request for the Golden Gate ATR scanner."""

    universes: list[str] = Field(
        default=["sp500", "nasdaq100"],
        description="Universe keys: sp500, nasdaq100, russell2000, or all",
    )
    trading_mode: Literal["day", "multiday", "swing", "position"] = Field(
        default="day",
        description="ATR trading mode",
    )
    signal_type: Literal[
        "golden_gate",
        "golden_gate_up",
        "golden_gate_down",
        "call_trigger",
        "put_trigger",
    ] = Field(
        default="golden_gate_up",
        description="Signal type to scan for",
    )
    min_price: float = Field(default=4.0, ge=0, description="Minimum price filter")
    custom_tickers: list[str] | None = Field(
        default=None,
        max_length=500,
        description="Extra tickers to include",
    )
    include_premarket: bool = Field(
        default=True,
        description="Use premarket high/low for Day mode",
    )


class GoldenGateHit(BaseModel):
    """A stock that triggered a golden gate / trigger signal."""

    ticker: str
    last_close: float
    signal: str
    direction: str
    pdc: float
    atr: float
    gate_level: float
    midrange_level: float
    distance_pct: float
    atr_status: str
    atr_covered_pct: float
    trend: str
    trading_mode: str
    premarket_high: float | None = None
    premarket_low: float | None = None


class GoldenGateScanResponse(BaseModel):
    """Response for the Golden Gate scanner."""

    hits: list[GoldenGateHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    signal_type: str
    trading_mode: str


def _check_golden_gate_signal(
    atr_result: dict,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    signal_type: str,
) -> list[dict]:
    """Check if a ticker matches the golden gate / trigger signal.

    Supports five signal_type values:
      - "golden_gate_up":   bullish only
      - "golden_gate_down": bearish only
      - "golden_gate":      combined — checks both, can return up to 2 signals
      - "call_trigger":     bullish trigger (tighter zone)
      - "put_trigger":      bearish trigger (tighter zone)

    TOS formulas:
      Bullish golden gate:
        golden_gate_bull <= bar_high AND mid_range_bull > bar_high AND pdc <= bar_close
      Bearish golden gate:
        golden_gate_bear >= bar_low AND mid_range_bear < bar_low AND pdc >= bar_close
      Call trigger:
        trigger_bull <= bar_high AND golden_gate_bull > bar_high AND pdc <= bar_close
      Put trigger:
        trigger_bear >= bar_low AND golden_gate_bear < bar_low AND pdc >= bar_close
    """
    levels = atr_result["levels"]
    pdc = atr_result["pdc"]
    signals: list[dict] = []

    if signal_type in ("golden_gate", "golden_gate_up", "golden_gate_down"):
        # Bull: golden_gate_bull <= bar_high AND midrange_bull > bar_high AND pdc <= bar_close
        if signal_type in ("golden_gate", "golden_gate_up"):
            gg_bull = levels["golden_gate_bull"]["price"]
            mr_bull = levels["mid_range_bull"]["price"]
            if gg_bull <= bar_high and mr_bull > bar_high and pdc <= bar_close:
                signals.append(
                    {
                        "signal": "golden_gate_up",
                        "direction": "bullish",
                        "gate_level": gg_bull,
                        "midrange_level": mr_bull,
                    }
                )

        # Bear: golden_gate_bear >= bar_low AND midrange_bear < bar_low AND pdc >= bar_close
        if signal_type in ("golden_gate", "golden_gate_down"):
            gg_bear = levels["golden_gate_bear"]["price"]
            mr_bear = levels["mid_range_bear"]["price"]
            if gg_bear >= bar_low and mr_bear < bar_low and pdc >= bar_close:
                signals.append(
                    {
                        "signal": "golden_gate_down",
                        "direction": "bearish",
                        "gate_level": gg_bear,
                        "midrange_level": mr_bear,
                    }
                )

    elif signal_type == "call_trigger":
        ct = levels["trigger_bull"]["price"]
        gg_bull = levels["golden_gate_bull"]["price"]
        if ct <= bar_high and gg_bull > bar_high and pdc <= bar_close:
            signals.append(
                {
                    "signal": "call_trigger",
                    "direction": "bullish",
                    "gate_level": ct,
                    "midrange_level": gg_bull,
                }
            )

    elif signal_type == "put_trigger":
        pt = levels["trigger_bear"]["price"]
        gg_bear = levels["golden_gate_bear"]["price"]
        if pt >= bar_low and gg_bear < bar_low and pdc >= bar_close:
            signals.append(
                {
                    "signal": "put_trigger",
                    "direction": "bearish",
                    "gate_level": pt,
                    "midrange_level": gg_bear,
                }
            )

    return signals


@router.post("/golden-gate-scan")
async def golden_gate_scan(request: GoldenGateScanRequest) -> GoldenGateScanResponse:
    """Scan universe for Golden Gate / trigger signals using ATR Levels.

    For each ticker, computes ATR Levels at the requested trading mode,
    then checks whether the bar's high/low/close crosses the signal level.
    Day mode can optionally use premarket data for the bar comparison.
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

    logger.info(
        "Golden Gate scan: %d tickers, mode=%s, signal=%s",
        len(tickers),
        request.trading_mode,
        request.signal_type,
    )

    ucc = resolve_use_current_close()
    sem = asyncio.Semaphore(10)
    hits: list[GoldenGateHit] = []
    errors = 0
    skipped_low_price = 0

    async def _process_ticker(ticker: str) -> GoldenGateHit | None:
        nonlocal errors, skipped_low_price
        async with sem:
            try:
                chart_tf = _MODE_DEFAULT_TF.get(request.trading_mode, "15m")
                atr_source_df = await asyncio.to_thread(
                    _fetch_atr_source, ticker, request.trading_mode
                )
                intraday_df = await asyncio.to_thread(_fetch_intraday, ticker, chart_tf)
                atr_result = atr_levels(
                    atr_source_df,
                    intraday_df=intraday_df,
                    trading_mode=request.trading_mode,
                    use_current_close=ucc,
                )
                last_close = atr_result["current_price"]

                if last_close < request.min_price:
                    skipped_low_price += 1
                    return None

                bar_high = float(atr_source_df["high"].iloc[-1])
                bar_low = float(atr_source_df["low"].iloc[-1])
                bar_close = last_close
                pm_high: float | None = None
                pm_low: float | None = None

                if request.trading_mode == "day" and request.include_premarket:
                    pm_df = await asyncio.to_thread(_fetch_premarket, ticker)
                    if pm_df is not None and not pm_df.empty:
                        pm_high = float(pm_df["high"].max())
                        pm_low = float(pm_df["low"].min())
                        pm_close = float(pm_df["close"].iloc[-1])
                        bar_high = max(bar_high, pm_high)
                        bar_low = min(bar_low, pm_low)
                        bar_close = pm_close

                matched = _check_golden_gate_signal(
                    atr_result, bar_high, bar_low, bar_close, request.signal_type
                )
                if not matched:
                    return None

                sig = matched[0]
                gate = sig["gate_level"]
                distance = ((bar_close - gate) / gate) * 100 if gate > 0 else 0.0

                return GoldenGateHit(
                    ticker=ticker.upper(),
                    last_close=round(bar_close, 2),
                    signal=sig["signal"],
                    direction=sig["direction"],
                    pdc=atr_result["pdc"],
                    atr=atr_result["atr"],
                    gate_level=round(gate, 4),
                    midrange_level=round(sig["midrange_level"], 4),
                    distance_pct=round(distance, 2),
                    atr_status=atr_result["atr_status"],
                    atr_covered_pct=atr_result["atr_covered_pct"],
                    trend=atr_result["trend"],
                    trading_mode=request.trading_mode,
                    premarket_high=round(pm_high, 4) if pm_high else None,
                    premarket_low=round(pm_low, 4) if pm_low else None,
                )
            except Exception as exc:
                logger.debug("Golden Gate scan error for %s: %s", ticker, exc)
                errors += 1
                return None

    results = await asyncio.gather(*(_process_ticker(t) for t in tickers))
    hits = [r for r in results if r is not None]
    hits.sort(key=lambda h: abs(h.distance_pct))
    elapsed = round(time.monotonic() - t0, 2)

    return GoldenGateScanResponse(
        hits=hits,
        total_scanned=len(tickers),
        total_hits=len(hits),
        total_errors=errors,
        skipped_low_price=skipped_low_price,
        scan_duration_seconds=elapsed,
        signal_type=request.signal_type,
        trading_mode=request.trading_mode,
    )


# ---------------------------------------------------------------------------
# VOMY / iVOMY Scanner — EMA crossover flip detector
# ---------------------------------------------------------------------------

# Timeframe → trading mode for ATR enrichment (distinct from _MODE_DEFAULT_TF)
_VOMY_TF_TO_MODE: dict[str, str] = {
    "1h": "multiday",
    "4h": "swing",
    "1d": "swing",
    "1w": "position",
}

# Friendly labels for ATR Fibonacci levels (used by nearest-level column)
_ATR_LEVEL_LABELS: dict[str, str] = {
    "trigger_bull": "Call Trigger",
    "trigger_bear": "Put Trigger",
    "golden_gate_bull": "Golden Gate \u2191",
    "golden_gate_bear": "Golden Gate \u2193",
    "mid_50_bull": "Mid 50 \u2191",
    "mid_50_bear": "Mid 50 \u2193",
    "mid_range_bull": "Mid Range \u2191",
    "mid_range_bear": "Mid Range \u2193",
    "fib_786_bull": "Fib 786 \u2191",
    "fib_786_bear": "Fib 786 \u2193",
    "full_range_bull": "Full Range \u2191",
    "full_range_bear": "Full Range \u2193",
}


class VomyScanRequest(BaseModel):
    """Request for the VOMY / iVOMY scanner."""

    universes: list[str] = Field(
        default=["sp500", "nasdaq100"],
        description="Universe keys: sp500, nasdaq100, russell2000, or all",
    )
    timeframe: Literal["1h", "4h", "1d", "1w"] = Field(
        default="1d",
        description="Chart timeframe for EMA computation",
    )
    signal_type: Literal["vomy", "ivomy", "both"] = Field(
        default="both",
        description="Signal type: vomy (bearish), ivomy (bullish), or both",
    )
    min_price: float = Field(default=4.0, ge=0, description="Minimum close price")
    custom_tickers: list[str] | None = Field(
        default=None,
        max_length=500,
        description="Extra tickers to include",
    )
    include_premarket: bool = Field(
        default=True,
        description="Include premarket data (reserved for future use)",
    )


class VomyHit(BaseModel):
    """A stock that triggered a VOMY or iVOMY signal."""

    ticker: str
    last_close: float
    signal: str
    ema13: float
    ema21: float
    ema34: float
    ema48: float
    distance_from_ema48_pct: float
    atr: float
    pdc: float
    nearest_level_name: str
    nearest_level_pct: float
    atr_status: str
    atr_covered_pct: float
    trend: str
    trading_mode: str
    timeframe: str
    conviction_type: str | None = None
    conviction_bars_ago: int | None = None
    conviction_confirmed: bool = False


class VomyScanResponse(BaseModel):
    """Response for the VOMY / iVOMY scanner."""

    hits: list[VomyHit]
    total_scanned: int
    total_hits: int
    total_errors: int
    skipped_low_price: int
    scan_duration_seconds: float
    signal_type: str
    timeframe: str


def _check_vomy_signal(
    close: float,
    ema13: float,
    ema21: float,
    ema34: float,
    ema48: float,
    signal_type: str,
) -> str | None:
    """Check VOMY / iVOMY conditions on a single bar.

    VOMY  (bearish flip): ema13 >= close AND ema48 <= close AND ema13 >= ema21 >= ema34 >= ema48
    iVOMY (bullish flip): ema13 <= close AND ema48 >= close AND ema13 <= ema21 <= ema34 <= ema48

    Returns "vomy", "ivomy", or None.
    """
    if signal_type in ("vomy", "both"):
        if ema13 >= close and ema48 <= close and ema13 >= ema21 >= ema34 >= ema48:
            return "vomy"

    if signal_type in ("ivomy", "both"):
        if ema13 <= close and ema48 >= close and ema13 <= ema21 <= ema34 <= ema48:
            return "ivomy"

    return None


@router.post("/vomy-scan")
async def vomy_scan(request: VomyScanRequest) -> VomyScanResponse:
    """Scan universe for VOMY / iVOMY EMA crossover flip signals.

    For each ticker, computes 4 EMAs (13/21/34/48) on the close series and
    checks whether the last bar satisfies the sandwich condition.  Hits are
    enriched with ATR levels for context.
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

    logger.info(
        "VOMY scan: %d tickers, timeframe=%s, signal=%s",
        len(tickers),
        request.timeframe,
        request.signal_type,
    )

    ucc = resolve_use_current_close()
    sem = asyncio.Semaphore(10)
    hits: list[VomyHit] = []
    errors = 0
    skipped_low_price = 0

    async def _process_ticker(ticker: str) -> VomyHit | None:
        nonlocal errors, skipped_low_price
        async with sem:
            try:
                # Fetch price data for EMA computation
                intraday_df = await asyncio.to_thread(
                    _fetch_intraday, ticker, request.timeframe
                )

                close_series = intraday_df["close"]
                last_close = float(close_series.iloc[-1])

                # Price filter
                if last_close < request.min_price:
                    skipped_low_price += 1
                    return None

                # Compute EMAs (span-based, NOT Wilder)
                ema13_series = close_series.ewm(span=13, adjust=False).mean()
                ema48_series = close_series.ewm(span=48, adjust=False).mean()
                ema13 = float(ema13_series.iloc[-1])
                ema21 = float(close_series.ewm(span=21, adjust=False).mean().iloc[-1])
                ema34 = float(close_series.ewm(span=34, adjust=False).mean().iloc[-1])
                ema48 = float(ema48_series.iloc[-1])

                # Check signal
                signal = _check_vomy_signal(
                    last_close, ema13, ema21, ema34, ema48, request.signal_type
                )
                if signal is None:
                    return None

                # --- 13/48 conviction crossover (within 4 bars) ---
                conviction_type: str | None = None
                conviction_bars_ago: int | None = None
                n = len(ema13_series)
                lookback = min(4, n - 2)
                for bars_ago in range(1, lookback + 1):
                    idx = n - 1 - bars_ago
                    prev_13_above = float(ema13_series.iloc[idx - 1]) >= float(
                        ema48_series.iloc[idx - 1]
                    )
                    curr_13_above = float(ema13_series.iloc[idx]) >= float(
                        ema48_series.iloc[idx]
                    )
                    if not prev_13_above and curr_13_above:
                        conviction_type = "bullish_crossover"
                        conviction_bars_ago = bars_ago
                        break
                    elif prev_13_above and not curr_13_above:
                        conviction_type = "bearish_crossover"
                        conviction_bars_ago = bars_ago
                        break

                conviction_confirmed = (
                    signal == "vomy" and conviction_type == "bearish_crossover"
                ) or (signal == "ivomy" and conviction_type == "bullish_crossover")

                # Enrich hits with ATR data
                mode = _VOMY_TF_TO_MODE.get(request.timeframe, "swing")
                atr_source_df = await asyncio.to_thread(_fetch_atr_source, ticker, mode)
                atr_result = atr_levels(
                    atr_source_df,
                    intraday_df=intraday_df,
                    trading_mode=mode,
                    use_current_close=ucc,
                )

                # Distance from EMA48 as %
                distance_pct = (
                    ((last_close - ema48) / ema48) * 100 if ema48 > 0 else 0.0
                )

                # Find closest ATR Fibonacci level to current price
                atr_lvls = atr_result["levels"]
                best_key, best_dist = "", float("inf")
                for key, lvl in atr_lvls.items():
                    dist = abs(lvl["price"] - last_close)
                    if dist < best_dist:
                        best_dist = dist
                        best_key = key
                nearest_pct = (
                    ((atr_lvls[best_key]["price"] - last_close) / last_close) * 100
                    if best_key
                    else 0.0
                )
                nearest_name = _ATR_LEVEL_LABELS.get(best_key, best_key)

                return VomyHit(
                    ticker=ticker.upper(),
                    last_close=round(last_close, 2),
                    signal=signal,
                    ema13=round(ema13, 4),
                    ema21=round(ema21, 4),
                    ema34=round(ema34, 4),
                    ema48=round(ema48, 4),
                    distance_from_ema48_pct=round(distance_pct, 2),
                    atr=atr_result["atr"],
                    pdc=atr_result["pdc"],
                    nearest_level_name=nearest_name,
                    nearest_level_pct=round(nearest_pct, 2),
                    atr_status=atr_result["atr_status"],
                    atr_covered_pct=atr_result["atr_covered_pct"],
                    trend=atr_result["trend"],
                    trading_mode=mode,
                    timeframe=request.timeframe,
                    conviction_type=conviction_type,
                    conviction_bars_ago=conviction_bars_ago,
                    conviction_confirmed=conviction_confirmed,
                )
            except Exception as exc:
                logger.debug("VOMY scan error for %s: %s", ticker, exc)
                errors += 1
                return None

    results = await asyncio.gather(*(_process_ticker(t) for t in tickers))
    hits = [r for r in results if r is not None]

    # Sort by abs(distance_from_ema48_pct) ascending — freshest transitions first
    hits.sort(key=lambda h: abs(h.distance_from_ema48_pct))

    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "VOMY scan complete: %d hits, %d errors, %d skipped, %.1fs",
        len(hits),
        errors,
        skipped_low_price,
        elapsed,
    )

    return VomyScanResponse(
        hits=hits,
        total_scanned=len(tickers),
        total_hits=len(hits),
        total_errors=errors,
        skipped_low_price=skipped_low_price,
        scan_duration_seconds=elapsed,
        signal_type=request.signal_type,
        timeframe=request.timeframe,
    )
