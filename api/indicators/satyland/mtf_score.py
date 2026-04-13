"""
MTF Score Dashboard — Python port of Pine Script v6.

Score from -15 to +15 per timeframe:
- 10 EMA cross comparisons (pairwise: 8, 13, 21, 48, 200)
- 5 EMA trend directions (each EMA vs previous bar)
A+ = |score| == 15 AND compression active.
"""

import pandas as pd
from api.indicators.satyland.phase_oscillator import phase_oscillator

_EMA_PERIODS = (8, 13, 21, 48, 200)
_PAIRS = [(a, b) for i, a in enumerate(_EMA_PERIODS) for b in _EMA_PERIODS[i + 1:]]


def mtf_score(df: pd.DataFrame) -> dict:
    close = df["close"]
    emas = {p: close.ewm(span=p, adjust=False).mean() for p in _EMA_PERIODS}

    cross_score = 0
    for a, b in _PAIRS:
        curr_a, curr_b = float(emas[a].iloc[-1]), float(emas[b].iloc[-1])
        if curr_a > curr_b:
            cross_score += 1
        elif curr_a < curr_b:
            cross_score -= 1

    trend_score = 0
    for p in _EMA_PERIODS:
        curr, prev = float(emas[p].iloc[-1]), float(emas[p].iloc[-2])
        if curr > prev:
            trend_score += 1
        elif curr < prev:
            trend_score -= 1

    score = cross_score + trend_score
    po = phase_oscillator(df)

    return {
        "score": score,
        "cross_score": cross_score,
        "trend_score": trend_score,
        "po_value": round(po["oscillator"], 2),
        "in_compression": po["in_compression"],
        "is_a_plus": abs(score) == 15 and po["in_compression"],
    }
