"""
Saty Pivot Ribbon Pro — exact Python port of the Pine Script.

Pine Script ground truth (pivot_ribbon_pine_script.txt):

EMAs: 8 (fast), 13 (pullback_overlap), 21 (pivot), 48 (slow), 200 (long_term)

Bias Candle — pivot is EMA48 (bias_ema = 48, NOT 21):
  Green  : up candle  AND close >= EMA48
  Blue   : down candle AND close >= EMA48
  Orange : up candle  AND close < EMA48
  Red    : down candle AND close < EMA48

  In compression mode, candles turn gray (Clean) instead.

Compression (custom ATR-based formula, NOT LazyBear BB-inside-KC):
  pivot             = EMA21
  bband_offset      = 2.0 × stdev(close, 21)
  bband_up/down     = EMA21 ± bband_offset
  threshold_up/down = EMA21 ± 2.0 × ATR14      (compression boundary)
  expansion_up/down = EMA21 ± 1.854 × ATR14    (expansion boundary)
  compression       = above_pivot ? (bband_up − threshold_up) : (threshold_down − bband_down)
  in_expansion_zone = above_pivot ? (bband_up − expansion_up) : (expansion_down − bband_down)
  expansion         = compression[prev] <= compression[curr]
  compression_tracker:
      if expansion AND in_expansion_zone > 0  → False
      elif compression <= 0                   → True
      else                                    → False

Conviction Arrow: EMA13 crosses EMA48 (fast_conviction=13, slow_conviction=48).
"""

import pandas as pd


def _wilder_atr(close: pd.Series, high: pd.Series, low: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _compression_tracker(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    """
    Exact port of the Pine Script compression logic shared between
    Pivot Ribbon and Phase Oscillator.
    """
    pivot      = close.ewm(span=21, adjust=False).mean()
    above_pivot = close >= pivot
    stdev_21   = close.rolling(21).std()
    atr14      = _wilder_atr(close, high, low, 14)

    bband_up   = pivot + 2.0 * stdev_21
    bband_down = pivot - 2.0 * stdev_21

    threshold_up   = pivot + 2.0   * atr14
    threshold_down = pivot - 2.0   * atr14
    expansion_up   = pivot + 1.854 * atr14
    expansion_down = pivot - 1.854 * atr14

    # compression: signed distance — negative = BB inside ATR bands (compressed)
    compression = above_pivot * (bband_up - threshold_up) + (~above_pivot) * (threshold_down - bband_down)
    in_expansion = above_pivot * (bband_up - expansion_up) + (~above_pivot) * (expansion_down - bband_down)

    # expansion = previous compression <= current compression (bands expanding)
    expansion = compression.shift(1) <= compression

    # compression_tracker is a stateful boolean per bar
    tracker = pd.Series(False, index=close.index)
    for i in range(1, len(close)):
        exp = bool(expansion.iloc[i])
        in_exp = float(in_expansion.iloc[i])
        comp   = float(compression.iloc[i])
        if exp and in_exp > 0:
            tracker.iloc[i] = False
        elif comp <= 0:
            tracker.iloc[i] = True
        else:
            tracker.iloc[i] = False
    return tracker


def pivot_ribbon(df: pd.DataFrame) -> dict:
    """
    Compute Saty Pivot Ribbon Pro from OHLCV data.
    The df timeframe should match the chart timeframe being analysed.
    """
    if len(df) < 2:
        raise ValueError("Need at least 2 bars for Pivot Ribbon")

    close = df["close"]
    open_ = df["open"]
    high  = df["high"]
    low   = df["low"]

    # ── EMAs ──────────────────────────────────────────────────────────────────
    ema8   = close.ewm(span=8,   adjust=False).mean()
    ema13  = close.ewm(span=13,  adjust=False).mean()
    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema48  = close.ewm(span=48,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    e8   = float(ema8.iloc[-1])
    e13  = float(ema13.iloc[-1])
    e21  = float(ema21.iloc[-1])
    e48  = float(ema48.iloc[-1])
    e200 = float(ema200.iloc[-1])

    curr_close = float(close.iloc[-1])
    curr_open  = float(open_.iloc[-1])

    # ── Ribbon state (8 > 21 > 48 stack) ─────────────────────────────────────
    if e8 > e21 > e48:
        ribbon_state = "bullish"
    elif e8 < e21 < e48:
        ribbon_state = "bearish"
    else:
        ribbon_state = "chopzilla"

    # ── Compression ───────────────────────────────────────────────────────────
    tracker = _compression_tracker(close, high, low)
    in_compression = bool(tracker.iloc[-1])

    # ── Bias candle — pivot is EMA48 (Pine: bias_ema = 48) ───────────────────
    above_48 = curr_close >= e48
    candle_up = curr_close >= curr_open  # up = close >= open

    if in_compression:
        bias_candle = "gray"            # compression = Clean mode gray
        bias_signal = "compression"
    elif candle_up and above_48:
        bias_candle = "green"           # strong bull trend candle
        bias_signal = "bullish"
    elif (not candle_up) and above_48:
        bias_candle = "blue"            # bullish pullback — BUY SIGNAL
        bias_signal = "buy_pullback"
    elif candle_up and (not above_48):
        bias_candle = "orange"          # bearish bounce — SHORT SIGNAL
        bias_signal = "short_pullback"
    else:
        bias_candle = "red"             # strong bear trend candle
        bias_signal = "bearish"

    # ── Conviction arrow: EMA13 crosses EMA48 ────────────────────────────────
    conviction_arrow = None
    if len(ema13) >= 2 and len(ema48) >= 2:
        prev_13_above = float(ema13.iloc[-2]) >= float(ema48.iloc[-2])
        curr_13_above = e13 >= e48
        if not prev_13_above and curr_13_above:
            conviction_arrow = "bullish_crossover"
        elif prev_13_above and not curr_13_above:
            conviction_arrow = "bearish_crossover"

    return {
        "ema8":             round(e8, 4),
        "ema13":            round(e13, 4),
        "ema21":            round(e21, 4),
        "ema48":            round(e48, 4),
        "ema200":           round(e200, 4),
        "ribbon_state":     ribbon_state,
        "bias_candle":      bias_candle,
        "bias_signal":      bias_signal,
        "conviction_arrow": conviction_arrow,
        "spread":           round(e8 - e48, 4),
        "above_48ema":      above_48,              # master regime variable
        "above_200ema":     curr_close > e200,
        "in_compression":   in_compression,
        "chopzilla":        ribbon_state == "chopzilla",
    }
