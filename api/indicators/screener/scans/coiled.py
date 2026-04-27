"""Coiled Spring scan — multi-condition compression detector.

ALL must hold on the latest daily bar:
  1. Donchian width (20-day high - low) / close < 8%
  2. TTM Squeeze ON (BB inside KC)
  3. Phase Oscillator value in [-20, +20]
  4. close > SMA50

Lane: breakout. Role: coiled. Weight: 1.
"""
from __future__ import annotations

import pandas as pd
import talib

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


DONCHIAN_PERIOD = 20
DONCHIAN_WIDTH_THRESHOLD = 0.08
BB_PERIOD = 20
BB_STD = 2.0
KC_PERIOD = 20
KC_ATR_MULT = 1.5
PHASE_OSCILLATOR_LOWER = -20.0
PHASE_OSCILLATOR_UPPER = 20.0


def _ttm_squeeze_on(bars: pd.DataFrame) -> bool:
    high = bars["high"].astype(float).values
    low = bars["low"].astype(float).values
    close = bars["close"].astype(float).values
    if len(close) < max(BB_PERIOD, KC_PERIOD) + 1:
        return False
    upper_bb, _, lower_bb = talib.BBANDS(close, timeperiod=BB_PERIOD, nbdevup=BB_STD, nbdevdn=BB_STD)
    atr = talib.ATR(high, low, close, timeperiod=KC_PERIOD)
    sma = talib.SMA(close, timeperiod=KC_PERIOD)
    upper_kc = sma[-1] + KC_ATR_MULT * atr[-1]
    lower_kc = sma[-1] - KC_ATR_MULT * atr[-1]
    return bool(upper_bb[-1] <= upper_kc and lower_bb[-1] >= lower_kc)


def _donchian_width_pct(bars: pd.DataFrame) -> float:
    if len(bars) < DONCHIAN_PERIOD:
        return float("inf")
    window = bars.iloc[-DONCHIAN_PERIOD:]
    width = float(window["high"].max() - window["low"].min())
    last_close = float(bars["close"].iloc[-1])
    return width / last_close if last_close > 0 else float("inf")


def _phase_oscillator_value(bars: pd.DataFrame) -> float:
    try:
        return float(phase_oscillator(bars)["oscillator"])
    except (ValueError, KeyError):
        return float("inf")


def is_coiled(bars: pd.DataFrame) -> bool:
    if len(bars) < 50:
        return False
    last_close = float(bars["close"].iloc[-1])
    sma_50 = float(bars["close"].rolling(50).mean().iloc[-1])
    if last_close <= sma_50:
        return False
    if _donchian_width_pct(bars) >= DONCHIAN_WIDTH_THRESHOLD:
        return False
    if not _ttm_squeeze_on(bars):
        return False
    po = _phase_oscillator_value(bars)
    if not (PHASE_OSCILLATOR_LOWER <= po <= PHASE_OSCILLATOR_UPPER):
        return False
    return True


def coiled_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if not is_coiled(bars):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="coiled_spring",
            lane="breakout", role="coiled",
            evidence={
                "donchian_width_pct": _donchian_width_pct(bars),
                "ttm_squeeze_on": True,
                "phase_oscillator": _phase_oscillator_value(bars),
                "close": float(bars["close"].iloc[-1]),
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="coiled_spring", lane="breakout", role="coiled",
    mode="swing", fn=coiled_scan,
))
