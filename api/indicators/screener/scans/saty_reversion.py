"""Saty Reversion Up / Down — mean-reversion setup candidates.

Reversion Up:
  - bias_candle == "blue"
  - last_close < EMA21

Reversion Down:
  - bias_candle == "orange"
  - last_close > EMA21

Lane: reversion. Role: setup_ready. Weight: 1 each.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.common.moving_averages import ema as ema_series
from api.indicators.screener.registry import ScanDescriptor, make_hit, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


def _ema21_value(bars: pd.DataFrame) -> float | None:
    if len(bars) < 21:
        return None
    return float(ema_series(bars, 21).iloc[-1])


def _make_reversion_scan(direction: str):
    expected_candle = "blue" if direction == "up" else "orange"
    scan_id = f"saty_reversion_{direction}"

    def scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
        hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
    ) -> list[ScanHit]:
        hits: list[ScanHit] = []
        for ticker, overlay in overlays_by_ticker.items():
            if overlay.bias_candle != expected_candle:
                continue
            bars = bars_by_ticker[ticker]
            ema21 = _ema21_value(bars)
            if ema21 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if direction == "up" and last_close >= ema21:
                continue
            if direction == "down" and last_close <= ema21:
                continue
            hits.append(make_hit(
                ticker=ticker, scan_id=scan_id,
                lane="reversion", role="setup_ready",
                overlay=overlay, bars=bars,
                evidence={
                    "bias_candle": overlay.bias_candle,
                    "last_close": last_close,
                    "ema21": ema21,
                },
            ))
        return hits

    return scan_fn


for _dir in ("up", "down"):
    register_scan(ScanDescriptor(
        scan_id=f"saty_reversion_{_dir}",
        lane="reversion", role="setup_ready", mode="swing",
        fn=_make_reversion_scan(_dir), weight=1,
    ))
