"""
Saty Green Flag Checklist — A+ Trade Confirmation.

Per SKILL.md, an A+ trade requires 3–5 of these flags aligned.
More green flags = larger position size.
Fewer than 3 = wait or skip.
"""

from typing import Any


def green_flag_checklist(
    atr: dict,
    ribbon: dict,
    phase: dict,
    structure: dict,
    direction: str,  # "bullish" or "bearish"
    vix: float | None = None,
    mtf_ribbons: dict[str, dict] | None = None,
) -> dict:
    """
    Score a trade setup against the 10-flag Green Flag Checklist.

    Args:
        atr:       Output of atr_levels()
        ribbon:    Output of pivot_ribbon()
        phase:     Output of phase_oscillator()
        structure: Output of price_structure()
        direction: "bullish" or "bearish"
        vix:       Current VIX level (optional)

    Returns:
        {
            "score": int,             # number of green flags (0-10)
            "grade": str,             # "A+" | "A" | "B" | "skip"
            "flags": dict[str, bool], # each flag and its state
            "recommendation": str,
            "verbal_audit": str,      # pre-trade narration template
        }
    """
    is_bull = direction == "bullish"
    flags: dict[str, bool] = {}

    # 1. Trend: Ribbon stacked and fanning
    flags["trend_ribbon_stacked"] = ribbon["ribbon_state"] == ("bullish" if is_bull else "bearish")

    # 2. Position: price holding above/below 48 EMA (bias_ema = 48 in Saty system)
    curr = atr["current_price"]
    ema48 = ribbon["ema48"]
    if is_bull:
        flags["price_above_cloud"] = curr > ema48
    else:
        flags["price_below_cloud"] = curr < ema48

    # 3. Trigger: candle close through Call/Put Trigger (±23.6%)
    if is_bull:
        call_trigger = atr["call_trigger"]
        flags["trigger_hit"] = curr >= call_trigger
    else:
        put_trigger = atr["put_trigger"]
        flags["trigger_hit"] = curr <= put_trigger

    # 4. Structure — calls: above PDH and/or PMH
    # 4. Structure — puts: below PDL and/or PML
    if is_bull:
        flags["structure_confirmed"] = structure.get("price_above_pdh", False) or structure.get("price_above_pmh", False)
    else:
        flags["structure_confirmed"] = structure.get("price_below_pdl", False) or structure.get("price_below_pml", False)

    # 5. MTF alignment: all higher-TF ribbons stacked in trade direction
    if mtf_ribbons:
        target_state = "bullish" if is_bull else "bearish"
        flags["mtf_aligned"] = all(
            r.get("ribbon_state") == target_state
            for r in mtf_ribbons.values()
        )
    else:
        # Fallback: above/below 200 EMA as proxy when MTF data unavailable
        if is_bull:
            flags["mtf_aligned"] = ribbon.get("above_200ema", False)
        else:
            flags["mtf_aligned"] = not ribbon.get("above_200ema", True)

    # 6. Phase Oscillator firing in direction
    if is_bull:
        flags["momentum_confirmed"] = phase["phase"] == "green"
    else:
        flags["momentum_confirmed"] = phase["phase"] == "red"

    # 7. Squeeze / compression active
    flags["squeeze"] = phase.get("in_compression", False)

    # 8. ATR room: price has covered < 70% of daily range
    flags["atr_room_ok"] = atr.get("atr_room_ok", True)

    # 9. VIX bias aligns with direction
    if vix is not None:
        if is_bull:
            flags["vix_bias"] = vix < 17
        else:
            flags["vix_bias"] = vix > 20
    else:
        flags["vix_bias"] = None  # type: ignore[assignment]

    # 10. Confluence bonus: ATR level clusters with structure level
    # Proxy: trigger price within 0.5% of PDH/PDL
    pdh = structure.get("pdh", 0.0) or 0.0
    pdl = structure.get("pdl", 0.0) or 0.0
    if is_bull:
        trigger_price = atr["call_trigger"]
        flags["confluence_bonus"] = abs(trigger_price - pdh) / pdh < 0.005 if pdh > 0 else False
    else:
        trigger_price = atr["put_trigger"]
        flags["confluence_bonus"] = abs(trigger_price - pdl) / pdl < 0.005 if pdl > 0 else False

    # Score (exclude None flags)
    score = sum(1 for v in flags.values() if v is True)

    # Grade
    if score >= 5:
        grade = "A+"
        rec = "High-conviction entry. Full size per Rule of 10."
    elif score == 4:
        grade = "A"
        rec = "Good setup. Standard size."
    elif score == 3:
        grade = "B"
        rec = "Marginal. Reduce size or wait for one more confirmation."
    else:
        grade = "skip"
        rec = "Insufficient confirmations. WAIT — do not force the trade."

    # Verbal audit template
    setup_name = "Trend Continuation" if flags.get("trend_ribbon_stacked") else "Unknown Setup"
    trigger_level = "Call Trigger (+23.6%)" if is_bull else "Put Trigger (-23.6%)"
    entry_cue = "Blue bias candle bouncing off 21 EMA" if is_bull else "Orange bias candle failing at 21 EMA"
    exit_target = "Mid-Range (+61.8%) then Full Range (+100%)" if is_bull else "Mid-Range (-61.8%) then Full Range (-100%)"
    stop_cue = "Candle close below 21 EMA or Ribbon fold" if is_bull else "Candle close above 21 EMA or Ribbon fold"

    verbal_audit = (
        f"Setup: {setup_name} ({direction}). "
        f"Trigger: {trigger_level} cleared. "
        f"Entry: {entry_cue}. "
        f"Exit: Scale 70% at {exit_target.split(' then ')[0]}, runners to {exit_target.split(' then ')[1]}. "
        f"Stop: {stop_cue}."
    )

    return {
        "direction":    direction,
        "score":        score,
        "max_score":    10,
        "grade":        grade,
        "recommendation": rec,
        "flags":        flags,
        "verbal_audit": verbal_audit,
    }
