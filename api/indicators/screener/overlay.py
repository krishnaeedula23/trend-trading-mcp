"""Indicator overlay: ATR, volume, move metrics, Phase Oscillator, Pivot Ribbon, ATR Levels."""
from __future__ import annotations

import logging

import pandas as pd
import talib

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.schemas.screener import IndicatorOverlay


logger = logging.getLogger(__name__)


SMA_PERIOD = 50
ATR_PERIOD = 14
VOLUME_AVG_PERIOD = 50
ADR_PERIOD = 20


def _resample(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample daily OHLCV to a wider timeframe (W=weekly, M=monthly)."""
    df = bars.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    agg = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return agg.reset_index()


def _safe_pct_change(close: pd.Series, lookback: int) -> float:
    if len(close) < lookback + 1:
        return 0.0
    base = float(close.iloc[-(lookback + 1)])
    last = float(close.iloc[-1])
    return (last / base) - 1.0 if base > 0 else 0.0


def compute_overlay(bars: pd.DataFrame) -> IndicatorOverlay:
    """Compute the full indicator overlay from a daily bar DataFrame.

    Requires >= 50 bars (SMA50). Optional fields (90d/180d move, weekly/monthly
    Saty Levels) degrade to safe defaults rather than raising.
    """
    if len(bars) < SMA_PERIOD:
        raise ValueError(
            f"compute_overlay requires at least {SMA_PERIOD} bars; got {len(bars)}."
        )

    high   = bars["high"].astype(float).values
    low    = bars["low"].astype(float).values
    close  = bars["close"].astype(float).values
    volume = bars["volume"].astype(float).values

    last_close = float(close[-1])
    sma_50 = float(pd.Series(close).rolling(SMA_PERIOD).mean().iloc[-1])
    atr_arr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)
    atr_14 = float(atr_arr[-1]) if not pd.isna(atr_arr[-1]) else 0.0

    atr_pct = atr_14 / last_close if last_close > 0 else 0.0
    pct_from_50ma = (last_close - sma_50) / sma_50 if sma_50 > 0 else 0.0
    extension = (pct_from_50ma / atr_pct) if atr_pct > 0 else 0.0

    # Volume — len(bars) >= 50 enforced above, so .tail(50).mean() is safe.
    volume_avg_50d = float(pd.Series(volume).tail(VOLUME_AVG_PERIOD).mean())
    last_volume = float(volume[-1])
    relative_volume = last_volume / volume_avg_50d if volume_avg_50d > 0 else 0.0
    dollar_volume_today = last_close * last_volume

    # Move
    close_series = pd.Series(close)
    if len(close) >= 2 and float(close[-2]) > 0:
        prev_close = float(close[-2])
        pct_change_today = (last_close / prev_close) - 1.0
        today_open_raw = float(bars["open"].iloc[-1])
        if pd.isna(today_open_raw):
            gap_pct_open = 0.0
        else:
            gap_pct_open = (today_open_raw - prev_close) / prev_close
    else:
        pct_change_today = 0.0
        gap_pct_open = 0.0
    pct_change_30d = _safe_pct_change(close_series, 30)
    pct_change_90d = _safe_pct_change(close_series, 90)
    pct_change_180d = _safe_pct_change(close_series, 180)

    # ADR% — len(bars) >= 50 (>= ADR_PERIOD) enforced above.
    rng = (bars["high"].astype(float) - bars["low"].astype(float)) / bars["close"].astype(float).replace(0, float("nan"))
    adr_pct_20d = float(rng.tail(ADR_PERIOD).mean())

    # Phase Oscillator
    try:
        po = phase_oscillator(bars)
        phase_value = float(po["oscillator"])
        phase_compression = bool(po["in_compression"])
    except (ValueError, KeyError) as exc:
        logger.debug("phase_oscillator unavailable: %s", exc)
        phase_value, phase_compression = 0.0, False

    # Pivot Ribbon
    try:
        pr = pivot_ribbon(bars)
        ribbon_state = pr["ribbon_state"]
        bias_candle = pr["bias_candle"]
        above_48ema = bool(pr["above_48ema"])
    except (ValueError, KeyError) as exc:
        logger.debug("pivot_ribbon unavailable: %s", exc)
        ribbon_state, bias_candle, above_48ema = "chopzilla", "gray", False

    # Saty ATR Levels by mode
    levels_by_mode: dict = {}
    try:
        levels_by_mode["day"] = atr_levels(bars, trading_mode="day", use_current_close=True)
    except (ValueError, KeyError) as exc:
        logger.debug("atr_levels unavailable for mode=day: %s", exc)
    weekly = _resample(bars, "W")
    if len(weekly) >= 2:
        try:
            levels_by_mode["multiday"] = atr_levels(weekly, trading_mode="multiday", use_current_close=True)
        except (ValueError, KeyError) as exc:
            logger.debug("atr_levels unavailable for mode=multiday: %s", exc)
    monthly = _resample(bars, "ME")
    if len(monthly) >= 2:
        try:
            levels_by_mode["swing"] = atr_levels(monthly, trading_mode="swing", use_current_close=True)
        except (ValueError, KeyError) as exc:
            logger.debug("atr_levels unavailable for mode=swing: %s", exc)

    return IndicatorOverlay(
        atr_pct=atr_pct, pct_from_50ma=pct_from_50ma, extension=extension,
        sma_50=sma_50, atr_14=atr_14,
        volume_avg_50d=volume_avg_50d, relative_volume=relative_volume,
        dollar_volume_today=dollar_volume_today,
        gap_pct_open=gap_pct_open, pct_change_today=pct_change_today,
        pct_change_30d=pct_change_30d, pct_change_90d=pct_change_90d,
        pct_change_180d=pct_change_180d, adr_pct_20d=adr_pct_20d,
        phase_oscillator=phase_value, phase_in_compression=phase_compression,
        ribbon_state=ribbon_state, bias_candle=bias_candle, above_48ema=above_48ema,
        saty_levels_by_mode=levels_by_mode,
    )
