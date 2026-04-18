"""Post-EPS Flag Base detector — Kell/Saty pattern after earnings gap-up."""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.common.moving_averages import ema
from api.indicators.swing.earnings_calendar import last_earnings_gap_pct
from api.indicators.swing.setups.base import SetupHit, volume_vs_avg

logger = logging.getLogger(__name__)


def detect(bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
    """Return SetupHit if Post-EPS Flag Base fires on the current (last) bar, else None."""
    ticker = ctx.get("ticker", "UNKNOWN")
    try:
        return _detect(bars, ticker)
    except Exception as exc:  # noqa: BLE001
        logger.warning("post_eps_flag: unexpected error for %s: %s", ticker, exc)
        return None


def _detect(bars: pd.DataFrame, ticker: str) -> SetupHit | None:
    if len(bars) < 15:
        return None

    # Rule 1: earnings gap up > 5% in last 10 bars
    gap_pct = last_earnings_gap_pct(ticker, bars, 10)
    if gap_pct is None:
        return None

    # Rule 2: locate the gap bar index within bars
    n = len(bars)
    start_search = max(n - 10, 1)
    gap_bar_idx: int | None = None
    for i in range(start_search, n):
        prev_close = float(bars["close"].iloc[i - 1])
        cur_open = float(bars["open"].iloc[i])
        if prev_close > 0 and (cur_open - prev_close) / prev_close >= 0.05:
            gap_bar_idx = i
            # Take the last qualifying gap
    if gap_bar_idx is None:
        return None

    # Consolidation window: bars strictly after the gap bar through current (inclusive)
    consol_start = gap_bar_idx + 1
    consol_end = n  # exclusive → bars[consol_start:n]
    consol_bars = bars.iloc[consol_start:consol_end]
    consolidation_bars = len(consol_bars)

    if consolidation_bars < 3:
        return None

    # Rule 3: >= 3 consecutive bars after gap bar each have daily_range < 4%
    # Check all consolidation bars (all must pass — consecutive check from gap_bar onward)
    for i in range(len(consol_bars)):
        high = float(consol_bars["high"].iloc[i])
        low = float(consol_bars["low"].iloc[i])
        close = float(consol_bars["close"].iloc[i])
        if close == 0:
            return None
        if (high - low) / close >= 0.04:
            return None

    # Rule 4: price above 10-EMA throughout consolidation window
    ema10 = ema(bars, 10)
    for i in range(consol_start, n):
        if float(bars["close"].iloc[i]) <= float(ema10.iloc[i]):
            return None

    # Rule 5: volume drying up — current bar volume < 0.8× 20-day avg
    vol_ratio = volume_vs_avg(bars, 20)
    if vol_ratio >= 0.8:
        return None

    # Compute output values
    cur_close = float(bars["close"].iloc[-1])
    cur_ema10 = float(ema10.iloc[-1])

    consolidation_low = float(consol_bars["low"].min())
    consolidation_high = float(consol_bars["high"].max())
    consolidation_height = consolidation_high - consolidation_low

    # Compute the average daily range % across the consolidation window
    ranges = [
        (float(consol_bars["high"].iloc[i]) - float(consol_bars["low"].iloc[i]))
        / float(consol_bars["close"].iloc[i])
        for i in range(len(consol_bars))
    ]
    avg_range_pct = sum(ranges) / len(ranges)

    gap_bars_ago = n - 1 - gap_bar_idx

    entry_zone = (cur_close, round(cur_close * 1.02, 4))
    stop_price = min(consolidation_low, cur_ema10)
    first_target = cur_close + consolidation_height

    raw_score = 3
    if gap_pct > 0.08:
        raw_score += 1
    if consolidation_bars >= 5:
        raw_score += 1
    raw_score = min(raw_score, 5)

    return SetupHit(
        ticker=ticker,
        setup_kell="post_eps_flag",
        cycle_stage="post_eps_flag",
        entry_zone=entry_zone,
        stop_price=round(stop_price, 4),
        first_target=round(first_target, 4),
        second_target=None,
        detection_evidence={
            "gap_pct": round(gap_pct, 4),
            "gap_bars_ago": gap_bars_ago,
            "consolidation_bars": consolidation_bars,
            "consolidation_range_pct": round(avg_range_pct, 4),
            "volume_vs_20d_avg": round(vol_ratio, 4),
        },
        raw_score=raw_score,
    )
