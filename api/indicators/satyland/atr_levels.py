"""
Saty ATR Levels — exact Python port of the Pine Script.

Pine Script ground truth (saty_atr_levels_pine_script.txt):
  - Trading modes   : Day (daily ATR), Multiday (weekly), Swing (monthly),
                      Position (quarterly), Long-term (yearly)
  - ATR source      : ta.atr(14)[1] on the mode's timeframe — previous period's settled ATR
  - PDC / zero line : close[1] on the mode's timeframe — previous period's close
  - ATR covered %   : (period_high - period_low) / atr * 100
  - ATR status      : ≤70% green (room), 70-90% orange (warning), ≥90% red (overextended)
  - Levels          : ±23.6%, ±38.2%, ±50%, ±61.8%, ±78.6%, ±100%
  - Extensions      : ±123.6%, ±161.8%, ±200%, ±223.6%, ±261.8%, ±300%
  - Trend label     : close >= EMA8 >= EMA21 >= EMA34 → bullish
                      close <= EMA8 <= EMA21 <= EMA34 → bearish

The first argument (atr_source_df) provides the OHLCV bars for computing ATR and PDC.
For Day mode this is daily bars; for Multiday, weekly bars; for Swing, monthly bars; etc.
The intraday_df is used only for the EMA-based trend label.
"""

import pandas as pd


def _wilder_atr(daily_df: pd.DataFrame, period: int = 14) -> pd.Series:
    """14-period Wilder ATR on daily bars (matches Pine ta.atr)."""
    h = daily_df["high"]
    l = daily_df["low"]
    c = daily_df["close"]
    tr = pd.concat(
        [(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _level(pdc: float, atr: float, fib: float) -> dict:
    return {
        "bull": round(pdc + atr * fib, 4),
        "bear": round(pdc - atr * fib, 4),
        "pct":  fib,
    }


# Core Fibonacci levels (always shown)
_CORE_FIBS = [
    (0.236, "trigger"),
    (0.382, "golden_gate"),
    (0.500, "mid_50"),
    (0.618, "mid_range"),
    (0.786, "fib_786"),
    (1.000, "full_range"),
]

# Extension levels (beyond 100%)
_EXT_FIBS = [
    (1.236, "ext_1236"),
    (1.618, "ext_1618"),
    (2.000, "ext_2000"),
    (2.236, "ext_2236"),
    (2.618, "ext_2618"),
    (3.000, "ext_3000"),
]


def atr_levels(daily_df: pd.DataFrame, intraday_df: pd.DataFrame | None = None,
               atr_period: int = 14, include_extensions: bool = False,
               trading_mode: str = "day",
               use_current_close: bool = False) -> dict:
    """
    Compute Saty ATR Levels from higher-timeframe OHLCV data.

    Args:
        daily_df:          ATR source OHLCV — daily bars for Day mode, weekly for
                           Multiday, monthly for Swing, quarterly for Position.
                           Named ``daily_df`` for backward compatibility.
        intraday_df:       Optional chart-timeframe OHLCV for EMA-based trend label.
                           If None, trend label is derived from atr_source data.
        atr_period:        ATR lookback (default 14).
        include_extensions: Include Valhalla extension levels beyond 100%.
        trading_mode:      One of "day", "multiday", "swing", "position".
                           Controls the label shown in the response.
        use_current_close: When True, anchor ATR/PDC at iloc[-1] (settled bar)
                           instead of iloc[-2]. Pine: use_current_close shifts
                           period_index from 1 to 0.

    Returns:
        Full ATR Levels dict matching Pine Script outputs.
    """
    if len(daily_df) < 2:
        raise ValueError("Need at least 2 daily bars")

    # ── ATR and PDC from source data ─────────────────────────────────────────
    anchor = -1 if use_current_close else -2
    atr_series = _wilder_atr(daily_df, atr_period)
    # Pine: ta.atr(14)[period_index] — settled bar's ATR
    atr = float(atr_series.iloc[anchor])
    # Pine: close[period_index] on the mode's timeframe
    pdc = float(daily_df["close"].iloc[anchor])
    # Current forming bar
    today_high  = float(daily_df["high"].iloc[-1])
    today_low   = float(daily_df["low"].iloc[-1])
    current_price = float(daily_df["close"].iloc[-1])

    # ── ATR covered % ─────────────────────────────────────────────────────────
    # Pine: range_1 = period_high - period_low; tr_percent_of_atr = range_1/atr*100
    daily_range = today_high - today_low
    atr_covered_pct = round(daily_range / atr * 100, 1) if atr > 0 else 0.0

    if atr_covered_pct <= 70:
        atr_status = "green"      # room to run
    elif atr_covered_pct >= 90:
        atr_status = "red"        # overextended
    else:
        atr_status = "orange"     # warning zone

    # ── Build levels ──────────────────────────────────────────────────────────
    levels: dict[str, dict] = {}
    for fib, label in _CORE_FIBS:
        bull_price = round(pdc + atr * fib, 4)
        bear_price = round(pdc - atr * fib, 4)
        levels[f"{label}_bull"] = {"price": bull_price, "pct": f"+{fib*100:.1f}%", "fib": fib}
        levels[f"{label}_bear"] = {"price": bear_price, "pct": f"-{fib*100:.1f}%", "fib": fib}

    if include_extensions:
        for fib, label in _EXT_FIBS:
            base_bull = round(pdc + atr, 4)   # +100%
            base_bear = round(pdc - atr, 4)   # -100%
            ext_fib   = fib - 1.0
            levels[f"{label}_bull"] = {"price": round(base_bull + atr * ext_fib, 4), "pct": f"+{fib*100:.1f}%", "fib": fib}
            levels[f"{label}_bear"] = {"price": round(base_bear - atr * ext_fib, 4), "pct": f"-{fib*100:.1f}%", "fib": fib}

    # Named convenience aliases
    call_trigger = levels["trigger_bull"]["price"]
    put_trigger  = levels["trigger_bear"]["price"]

    # ── Trigger box ───────────────────────────────────────────────────────────
    inside_trigger_box = put_trigger < current_price < call_trigger

    # ── Price position ────────────────────────────────────────────────────────
    full_high   = levels["full_range_bull"]["price"]
    mid_high    = levels["mid_range_bull"]["price"]
    gate_high   = levels["golden_gate_bull"]["price"]
    full_low    = levels["full_range_bear"]["price"]
    mid_low     = levels["mid_range_bear"]["price"]
    gate_low    = levels["golden_gate_bear"]["price"]

    if current_price >= full_high:
        price_position = "above_full_range"
    elif current_price >= mid_high:
        price_position = "above_mid_range"
    elif current_price >= gate_high:
        price_position = "above_golden_gate"
    elif current_price >= call_trigger:
        price_position = "above_call_trigger"
    elif current_price > put_trigger:
        price_position = "inside_trigger_box"
    elif current_price > gate_low:
        price_position = "below_put_trigger"
    elif current_price > mid_low:
        price_position = "below_golden_gate"
    elif current_price > full_low:
        price_position = "below_mid_range"
    else:
        price_position = "below_full_range"

    # ── Trend label (EMA 8/21/34 stack, Pine ATR script) ─────────────────────
    # Uses intraday_df if provided, else falls back to daily
    src = intraday_df if (intraday_df is not None and len(intraday_df) >= 34) else daily_df
    close = src["close"]
    e8  = float(close.ewm(span=8,  adjust=False).mean().iloc[-1])
    e21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    e34 = float(close.ewm(span=34, adjust=False).mean().iloc[-1])
    cp  = float(close.iloc[-1])

    if cp >= e8 >= e21 >= e34:
        trend = "bullish"
    elif cp <= e8 <= e21 <= e34:
        trend = "bearish"
    else:
        trend = "neutral"

    _MODE_LABELS = {
        "day": "Day",
        "multiday": "Multiday",
        "swing": "Swing",
        "position": "Position",
    }

    return {
        "atr":             round(atr, 4),
        "pdc":             round(pdc, 4),
        "current_price":   round(current_price, 4),
        "levels":          levels,
        "call_trigger":    call_trigger,
        "put_trigger":     put_trigger,
        "trigger_box": {
            "low":    put_trigger,
            "high":   call_trigger,
            "inside": inside_trigger_box,
        },
        "price_position":  price_position,
        "daily_range":     round(daily_range, 4),   # backward compat
        "period_range":    round(daily_range, 4),
        "atr_covered_pct": atr_covered_pct,
        "atr_status":      atr_status,       # green / orange / red
        "atr_room_ok":     atr_status == "green",
        "chopzilla":       inside_trigger_box,
        "trend":           trend,             # bullish / bearish / neutral
        "trading_mode":    trading_mode,
        "trading_mode_label": _MODE_LABELS.get(trading_mode, "Day"),
        "use_current_close": use_current_close,
    }
