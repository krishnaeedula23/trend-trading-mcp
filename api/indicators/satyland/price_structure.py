"""
Saty Price Structure Levels: PDH / PDL / PMH / PML + Key Pivots.

Per SKILL.md — mark before the open, every day:
  PDH  Previous Day High  — key resistance; break above = bullish structural bias
  PDL  Previous Day Low   — key support;    break below = bearish structural bias
  PMH  Pre-Market High    — pre-market supply cleared = intraday bullish
  PML  Pre-Market Low     — pre-market buyers lost   = intraday bearish

Key Pivots (closes act as magnets / support-resistance):
  PWH/PWL/PWC  Previous Week High/Low/Close
  PMoH/PMoL/PMoC  Previous Month High/Low/Close
  PQC  Previous Quarter Close
  PYC  Previous Year Close

Bias Rules:
  Price above PDH              → Strongly Bullish
  Price above PMH (< PDH)      → Bullish
  Price between PMH and PML    → Neutral / Developing
  Price below PML (> PDL)      → Bearish
  Price below PDL              → Strongly Bearish
"""

import pandas as pd


def price_structure(df: pd.DataFrame, premarket_df: pd.DataFrame | None = None,
                    use_current_close: bool = False) -> dict:
    """
    Compute PDH, PDL, and optionally PMH/PML.

    Args:
        df:           Daily OHLCV DataFrame (at least 2 rows for previous day).
        premarket_df: Optional intraday DataFrame for the pre-market session
                      (4:00–9:30 AM ET). If None, PMH/PML are omitted.
        use_current_close: When True, anchor at iloc[-1] instead of iloc[-2].

    Returns:
        dict with pdh, pdl, pdch (prev day close), pmh, pml, structural_bias,
        gap_scenario, and confluence hints.
    """
    if len(df) < 2:
        return {"error": "Need at least 2 daily bars to compute structure levels"}

    anchor = -1 if use_current_close else -2
    prev = df.iloc[anchor]
    curr_close = float(df["close"].iloc[-1])

    pdh  = float(prev["high"])
    pdl  = float(prev["low"])
    pdc  = float(prev["close"])  # PDC = Zero Line for ATR Levels

    result: dict = {
        "pdc": round(pdc, 4),
        "pdh": round(pdh, 4),
        "pdl": round(pdl, 4),
        "current_price": round(curr_close, 4),
    }

    # PMH / PML from intraday pre-market data if provided
    pmh: float | None = None
    pml: float | None = None
    if premarket_df is not None and not premarket_df.empty:
        pmh = float(premarket_df["high"].max())
        pml = float(premarket_df["low"].min())
        result["pmh"] = round(pmh, 4)
        result["pml"] = round(pml, 4)
    else:
        result["pmh"] = None
        result["pml"] = None

    # Structural bias
    if curr_close > pdh:
        bias = "strongly_bullish"
    elif pmh is not None and curr_close > pmh:
        bias = "bullish"
    elif pml is not None and pmh is not None and pml <= curr_close <= pmh:
        bias = "neutral"
    elif pml is not None and curr_close < pml:
        bias = "bearish"
    elif curr_close < pdl:
        bias = "strongly_bearish"
    else:
        bias = "neutral"

    result["structural_bias"] = bias

    # Gap scenario — today's open vs previous day's range
    today_open = float(df["open"].iloc[-1])
    if today_open > pdh:
        gap_scenario = "gap_above_pdh"
    elif today_open < pdl:
        gap_scenario = "gap_below_pdl"
    elif today_open > pdc:
        gap_scenario = "gap_up_inside_range"
    elif today_open < pdc:
        gap_scenario = "gap_down_inside_range"
    else:
        gap_scenario = "no_gap"

    result["gap_scenario"] = gap_scenario

    # Key S/R flags for confluence detection
    result["price_above_pdh"] = curr_close > pdh
    result["price_above_pmh"] = pmh is not None and curr_close > pmh
    result["price_below_pdl"] = curr_close < pdl
    result["price_below_pml"] = pml is not None and curr_close < pml

    return result


def key_pivots(daily_df: pd.DataFrame, **_kwargs: object) -> dict:
    """
    Compute key pivot levels from daily OHLCV data.

    Previous Week: High, Low, Close (pivot)
    Previous Month: High, Low, Close (pivot)
    Previous Quarter: Close (pivot)
    Previous Year: Close (pivot)

    Requires at least ~400 daily bars (2y) for yearly pivot.
    Returns None for any level that can't be computed.

    NOTE: Always uses the previous *completed* period (iloc[-2] on the
    resampled frame).  The use_current_close flag (accepted and ignored
    via **_kwargs for backward-compat) is irrelevant here — pivots are
    by definition the prior period's close, not the current incomplete one.
    """
    result: dict = {}

    # Resample daily to weekly
    weekly = daily_df.resample("W").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna()
    if len(weekly) >= 2:
        pw = weekly.iloc[-2]
        result["pwh"] = round(float(pw["high"]), 4)
        result["pwl"] = round(float(pw["low"]), 4)
        result["pwc"] = round(float(pw["close"]), 4)
    else:
        result["pwh"] = result["pwl"] = result["pwc"] = None

    # Resample daily to monthly
    monthly = daily_df.resample("MS").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna()
    if len(monthly) >= 2:
        pm = monthly.iloc[-2]
        result["pmoh"] = round(float(pm["high"]), 4)
        result["pmol"] = round(float(pm["low"]), 4)
        result["pmoc"] = round(float(pm["close"]), 4)
    else:
        result["pmoh"] = result["pmol"] = result["pmoc"] = None

    # Resample daily to quarterly
    quarterly = daily_df.resample("QS").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna()
    if len(quarterly) >= 2:
        result["pqc"] = round(float(quarterly.iloc[-2]["close"]), 4)
    else:
        result["pqc"] = None

    # Resample daily to yearly
    yearly = daily_df.resample("YS").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna()
    if len(yearly) >= 2:
        result["pyc"] = round(float(yearly.iloc[-2]["close"]), 4)
    else:
        result["pyc"] = None

    return result


def open_gaps(daily_df: pd.DataFrame) -> list[dict]:
    """
    Scan daily bars for unfilled (open) gaps.

    A *true gap up* exists on day i when day[i].low > day[i-1].high.
    A *true gap down* exists on day i when day[i].high < day[i-1].low.

    A gap is "filled" once any subsequent bar's low <= gap_low (for gap up)
    or any subsequent bar's high >= gap_high (for gap down).

    Returns a list of unfilled gaps sorted newest-first, each with:
      date, type ("gap_up"/"gap_down"), gap_high, gap_low, size
    """
    if len(daily_df) < 2:
        return []

    highs = daily_df["high"].values
    lows = daily_df["low"].values
    dates = daily_df.index

    gaps: list[dict] = []

    for i in range(1, len(daily_df)):
        prev_high = float(highs[i - 1])
        prev_low = float(lows[i - 1])
        curr_low = float(lows[i])
        curr_high = float(highs[i])

        if curr_low > prev_high:
            # Gap up: gap zone is prev_high (bottom) → curr_low (top)
            gap_high = curr_low
            gap_low = prev_high
            # Filled when any subsequent bar's low touches the gap bottom
            filled = False
            for j in range(i + 1, len(daily_df)):
                if float(lows[j]) <= gap_low:
                    filled = True
                    break
            if not filled:
                dt = dates[i]
                date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                gaps.append({
                    "date": date_str,
                    "type": "gap_up",
                    "gap_high": round(gap_high, 4),
                    "gap_low": round(gap_low, 4),
                    "size": round(gap_high - gap_low, 4),
                })

        elif curr_high < prev_low:
            # Gap down: gap zone is curr_high (bottom) → prev_low (top)
            gap_high = prev_low
            gap_low = curr_high
            # Filled when any subsequent bar's high reaches the gap top
            filled = False
            for j in range(i + 1, len(daily_df)):
                if float(highs[j]) >= gap_high:
                    filled = True
                    break
            if not filled:
                dt = dates[i]
                date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                gaps.append({
                    "date": date_str,
                    "type": "gap_down",
                    "gap_high": round(gap_high, 4),
                    "gap_low": round(gap_low, 4),
                    "size": round(gap_high - gap_low, 4),
                })

    # Newest first
    gaps.reverse()
    return gaps
