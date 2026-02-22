"""
Saty Price Structure Levels: PDH / PDL / PMH / PML.

Per SKILL.md — mark before the open, every day:
  PDH  Previous Day High  — key resistance; break above = bullish structural bias
  PDL  Previous Day Low   — key support;    break below = bearish structural bias
  PMH  Pre-Market High    — pre-market supply cleared = intraday bullish
  PML  Pre-Market Low     — pre-market buyers lost   = intraday bearish

Bias Rules:
  Price above PDH              → Strongly Bullish
  Price above PMH (< PDH)      → Bullish
  Price between PMH and PML    → Neutral / Developing
  Price below PML (> PDL)      → Bearish
  Price below PDL              → Strongly Bearish
"""

import pandas as pd


def price_structure(df: pd.DataFrame, premarket_df: pd.DataFrame | None = None) -> dict:
    """
    Compute PDH, PDL, and optionally PMH/PML.

    Args:
        df:           Daily OHLCV DataFrame (at least 2 rows for previous day).
        premarket_df: Optional intraday DataFrame for the pre-market session
                      (4:00–9:30 AM ET). If None, PMH/PML are omitted.

    Returns:
        dict with pdh, pdl, pdch (prev day close), pmh, pml, structural_bias,
        gap_scenario, and confluence hints.
    """
    if len(df) < 2:
        return {"error": "Need at least 2 daily bars to compute structure levels"}

    prev = df.iloc[-2]
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

    # Gap scenario (open vs PDH/PDL — approximate using current price)
    if curr_close > pdh:
        gap_scenario = "gap_above_pdh"
    elif curr_close < pdl:
        gap_scenario = "gap_below_pdl"
    elif pdc is not None and curr_close > pdc:
        gap_scenario = "gap_up_inside_range"
    elif pdc is not None and curr_close < pdc:
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
