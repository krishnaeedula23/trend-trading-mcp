"""
Saty Phase Oscillator — exact Python port of the Pine Script.

Pine Script ground truth (phase_oscillator_pine_script.txt):

  pivot      = EMA21(close)
  atr        = ATR14 (Wilder, same timeframe)
  above_pivot = close >= pivot

  Compression (same formula as Pivot Ribbon):
    bband_offset      = 2.0 × stdev(close, 21)
    bband_up/down     = EMA21 ± bband_offset
    threshold_up/down = EMA21 ± 2.0 × ATR14
    expansion_up/down = EMA21 ± 1.854 × ATR14
    compression       = above_pivot ? (bband_up − threshold_up) : (threshold_down − bband_down)
    in_expansion_zone = above_pivot ? (bband_up − expansion_up) : (expansion_down − bband_down)
    expansion         = compression[prev] <= compression[curr]
    compression_tracker:
        if expansion AND in_expansion_zone > 0  → False
        elif compression <= 0                   → True
        else                                    → False

  Oscillator:
    raw_signal = ((close − EMA21) / (3.0 × ATR14)) × 100
    oscillator = EMA3(raw_signal)    [alpha = 2/(3+1) = 0.5]

  Phase (color):
    compression_tracker=True  → compression (magenta / gray)
    oscillator >= 0            → green (bullish momentum)
    oscillator < 0             → red   (bearish momentum)

  Zone lines: ±100, ±61.8, ±23.6, 0

  Zone cross signals (mean reversion):
    leaving_accumulation  : oscillator[prev] ≤ −61.8 AND oscillator > −61.8
    leaving_extreme_down  : oscillator[prev] ≤ −100  AND oscillator > −100
    leaving_distribution  : oscillator[prev] ≥  61.8 AND oscillator <  61.8
    leaving_extreme_up    : oscillator[prev] ≥  100  AND oscillator <  100
"""

import pandas as pd


def _wilder_atr(close: pd.Series, high: pd.Series, low: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _compression_tracker(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    """Shared compression logic (identical to pivot_ribbon implementation)."""
    pivot       = close.ewm(span=21, adjust=False).mean()
    above_pivot = close >= pivot
    stdev_21    = close.rolling(21).std()
    atr14       = _wilder_atr(close, high, low, 14)

    bband_up   = pivot + 2.0 * stdev_21
    bband_down = pivot - 2.0 * stdev_21

    threshold_up   = pivot + 2.0   * atr14
    threshold_down = pivot - 2.0   * atr14
    expansion_up   = pivot + 1.854 * atr14
    expansion_down = pivot - 1.854 * atr14

    compression  = above_pivot * (bband_up - threshold_up)  + (~above_pivot) * (threshold_down - bband_down)
    in_expansion = above_pivot * (bband_up - expansion_up)  + (~above_pivot) * (expansion_down - bband_down)
    expansion    = compression.shift(1) <= compression

    tracker = pd.Series(False, index=close.index)
    for i in range(1, len(close)):
        if bool(expansion.iloc[i]) and float(in_expansion.iloc[i]) > 0:
            tracker.iloc[i] = False
        elif float(compression.iloc[i]) <= 0:
            tracker.iloc[i] = True
        else:
            tracker.iloc[i] = False
    return tracker


def phase_oscillator(df: pd.DataFrame) -> dict:
    """
    Compute Saty Phase Oscillator from OHLCV data.

    Returns:
        oscillator     : current oscillator value (float, scaled ±100 range)
        oscillator_prev: previous bar's value (for crossover detection)
        phase          : "compression" | "green" | "red"
        in_compression : bool
        zone_crosses   : dict of mean-reversion cross signals (bool)
        zones          : fixed reference levels ±23.6, ±61.8, ±100
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    if len(df) < 22:
        raise ValueError("Need at least 22 bars for Phase Oscillator")

    # ── Pivot and ATR ─────────────────────────────────────────────────────────
    pivot = close.ewm(span=21, adjust=False).mean()
    atr14 = _wilder_atr(close, high, low, 14)

    # ── Oscillator: raw = ((close - EMA21) / (3 × ATR14)) × 100, smoothed EMA3
    # Pine EMA uses alpha = 2/(length+1); for length=3, alpha=0.5
    raw_signal = ((close - pivot) / (3.0 * atr14)) * 100
    oscillator = raw_signal.ewm(span=3, adjust=False).mean()   # EMA3

    osc_curr = float(oscillator.iloc[-1])
    osc_prev = float(oscillator.iloc[-2]) if len(oscillator) > 1 else 0.0

    # ── Compression ───────────────────────────────────────────────────────────
    tracker = _compression_tracker(close, high, low)
    in_compression = bool(tracker.iloc[-1])

    # ── Phase ─────────────────────────────────────────────────────────────────
    if in_compression:
        phase = "compression"    # magenta / gray
    elif osc_curr >= 0:
        phase = "green"          # bullish momentum
    else:
        phase = "red"            # bearish momentum

    # ── Zone cross signals ────────────────────────────────────────────────────
    zone_crosses = {
        "leaving_accumulation":  osc_prev <= -61.8 and osc_curr > -61.8,
        "leaving_extreme_down":  osc_prev <= -100  and osc_curr > -100,
        "leaving_distribution":  osc_prev >= 61.8  and osc_curr < 61.8,
        "leaving_extreme_up":    osc_prev >= 100   and osc_curr < 100,
    }

    # ── Current zone ─────────────────────────────────────────────────────────
    if osc_curr >= 100:
        current_zone = "extreme_up"
    elif osc_curr >= 61.8:
        current_zone = "distribution"
    elif osc_curr >= 23.6:
        current_zone = "neutral_up"
    elif osc_curr >= 0:
        current_zone = "above_zero"
    elif osc_curr >= -23.6:
        current_zone = "below_zero"
    elif osc_curr >= -61.8:
        current_zone = "neutral_down"
    elif osc_curr >= -100:
        current_zone = "accumulation"
    else:
        current_zone = "extreme_down"

    return {
        "oscillator":      round(osc_curr, 4),
        "oscillator_prev": round(osc_prev, 4),
        "phase":           phase,
        "in_compression":  in_compression,
        "current_zone":    current_zone,
        "zone_crosses":    zone_crosses,
        "zones": {
            "extreme":      {"up": 100.0,  "down": -100.0},
            "distribution": {"up": 61.8,   "down": -61.8},
            "neutral":      {"up": 23.6,   "down": -23.6},
            "zero":         0.0,
        },
    }
