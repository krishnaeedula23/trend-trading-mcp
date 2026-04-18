from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from api.indicators.common.moving_averages import ema


@dataclass
class MarketHealth:
    qqq_close: float
    qqq_20ema: float
    qqq_10ema: float
    green_light: bool
    index_cycle_stage: str
    snapshot: dict


def compute_market_health(qqq_bars: pd.DataFrame) -> MarketHealth:
    """Compute market-health summary from QQQ daily bars."""
    if len(qqq_bars) < 20:
        raise ValueError("insufficient bars for market health")

    qqq_close = float(qqq_bars["close"].iloc[-1])
    qqq_20ema = float(ema(qqq_bars, 20).iloc[-1])
    qqq_10ema = float(ema(qqq_bars, 10).iloc[-1])

    green_light = qqq_close > qqq_20ema

    above_20 = qqq_close > qqq_20ema
    above_10 = qqq_close > qqq_10ema
    if above_20 and above_10:
        index_cycle_stage = "bull"
    elif not above_20 and not above_10:
        index_cycle_stage = "bear"
    else:
        index_cycle_stage = "neutral"

    snapshot = {
        "qqq_close": qqq_close,
        "qqq_10ema": qqq_10ema,
        "qqq_20ema": qqq_20ema,
        "green_light": green_light,
        "index_cycle_stage": index_cycle_stage,
    }

    return MarketHealth(
        qqq_close=qqq_close,
        qqq_20ema=qqq_20ema,
        qqq_10ema=qqq_10ema,
        green_light=green_light,
        index_cycle_stage=index_cycle_stage,
        snapshot=snapshot,
    )
