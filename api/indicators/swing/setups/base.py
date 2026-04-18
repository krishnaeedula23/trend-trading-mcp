"""Shared dataclass and helper functions for swing setup detectors."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class SetupHit:
    ticker: str
    setup_kell: str              # 'wedge_pop', 'ema_crossback', etc.
    cycle_stage: str
    entry_zone: tuple[float, float]
    stop_price: float
    first_target: float | None
    second_target: float | None
    detection_evidence: dict
    raw_score: int               # 1-5


def volume_vs_avg(bars: pd.DataFrame, lookback: int = 20) -> float:
    """Return current bar volume divided by avg of prior `lookback` bars.

    Raises ValueError if fewer than lookback + 1 bars are available.
    """
    if len(bars) < lookback + 1:
        raise ValueError(
            f"Need at least {lookback + 1} bars; got {len(bars)}."
        )
    current = bars["volume"].iloc[-1]
    avg = bars["volume"].iloc[-lookback - 1 : -1].mean()
    return float(current / avg)


def prior_swing_high(bars: pd.DataFrame, lookback: int = 60) -> float | None:
    """Return the max high of the prior `lookback` bars (current bar excluded).

    Returns None if insufficient bars.
    """
    if len(bars) < lookback + 1:
        return None
    return float(bars["high"].iloc[-lookback - 1 : -1].max())


def prior_swing_low(bars: pd.DataFrame, lookback: int = 60) -> float | None:
    """Return the min low of the prior `lookback` bars (current bar excluded).

    Returns None if insufficient bars.
    """
    if len(bars) < lookback + 1:
        return None
    return float(bars["low"].iloc[-lookback - 1 : -1].min())


def synth_bars(
    days: int | None = None,
    closes: list[float] | None = None,
    volume: int = 10_000_000,
    start: str = "2026-01-01",
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame for testing.

    Provide either `closes` (explicit list) or `days` (generates flat closes
    at 100.0).  If both are provided, `closes` wins and len(closes) must equal
    `days`.
    """
    if closes is None and days is None:
        raise ValueError("Either 'days' or 'closes' must be provided.")
    if closes is None:
        closes = [100.0] * days  # type: ignore[arg-type]
    if days is not None:
        assert len(closes) == days, "len(closes) must equal days when both given."
    dates = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        }
    )
