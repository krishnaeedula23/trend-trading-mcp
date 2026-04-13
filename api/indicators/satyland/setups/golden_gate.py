"""
Golden Gate Strategy with Bilbo filter.

Uses backtested probability data from milkmantrades.com (6,466 SPY days).
60m Phase Oscillator zone_state is the primary probability driver.
"""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


def _parse_hour(time_est: str | None) -> int | None:
    """Parse hour from HH:MM string, returning None on failure."""
    if not time_est:
        return None
    try:
        return int(time_est.split(":")[0])
    except (ValueError, IndexError):
        return None

BILBO_PROBABILITIES = {
    "bullish": {
        "high_rising": 0.777,
        "high_falling": 0.776,
        "mid_rising": 0.633,
        "mid_falling": 0.515,
    },
    "bearish": {
        "low_falling": 0.902,
        "low_rising": 0.885,
        "mid_falling": 0.640,
        "mid_rising": 0.542,
    },
}

BASELINE_PROBABILITY = {"bullish": 0.630, "bearish": 0.650}

COUNTER_TREND = {
    "bullish": {"mid_falling", "low_falling", "low_rising"},
    "bearish": {"mid_rising", "high_rising", "high_falling"},
}


class GoldenGateEvaluator(SetupEvaluator):
    name = "golden_gate"
    BACKTESTED = True

    def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        flags = []

        # 1. Price through ±38.2%
        current = atr.get("current_price", 0)
        level_key = "golden_gate_bull" if is_bull else "golden_gate_bear"
        gg_level = atr.get("levels", {}).get(level_key, {}).get("price", 0)
        if is_bull:
            broke = current >= gg_level if gg_level else True
        else:
            broke = current <= gg_level if gg_level else True
        flags.append(("price_through_38.2", broke, f"Price {current}, GG at {gg_level}"))

        # 2. 60m PO not counter-trend
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "mid_rising")
        is_counter = zone_state in COUNTER_TREND.get(direction, set())
        flags.append(("po_60m_not_counter", not is_counter,
                      f"60m PO: {zone_state} ({'counter-trend' if is_counter else 'aligned'})"))

        # 3. ATR room
        room_ok = atr.get("atr_room_ok", False)
        pct = atr.get("atr_covered_pct", 0)
        flags.append(("atr_room", room_ok, f"ATR {pct:.0f}% consumed"))

        return flags

    def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        flags = []

        # 1. Bilbo confirmed
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "")
        bilbo_states = {"high_rising", "high_falling"} if is_bull else {"low_falling", "low_rising"}
        flags.append(("bilbo_confirmed", zone_state in bilbo_states, f"60m PO: {zone_state}"))

        # 2. Trigger holding
        current = atr.get("current_price", 0)
        trigger = atr.get("call_trigger" if is_bull else "put_trigger", 0)
        holding = (current >= trigger) if is_bull else (current <= trigger) if trigger else False
        flags.append(("trigger_holding", holding, f"Trigger at {trigger}, price at {current}"))

        # 3. Early session
        time_est = kw.get("time_est")
        hour = _parse_hour(time_est)
        early = hour is not None and hour < 11
        flags.append(("early_session", early, f"Time: {time_est or 'unknown'} EST"))

        # 4. MTF aligned
        target = "bullish" if is_bull else "bearish"
        flags.append(("mtf_aligned", mtf_scores.get("alignment") == target, f"MTF: {mtf_scores.get('alignment', 'unknown')}"))

        # 5. Structure
        if is_bull:
            ok = structure.get("price_above_pdh", False) or structure.get("price_above_pmh", False)
        else:
            ok = structure.get("price_below_pdl", False) or structure.get("price_below_pml", False)
        flags.append(("structure_confirmed", ok, "Structure aligned" if ok else "Not confirmed"))

        return flags

    def get_modifiers(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        modifiers = []
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "")
        is_bull = direction == "bullish"

        bilbo_states = {"high_rising", "high_falling"} if is_bull else {"low_falling", "low_rising"}
        if zone_state in bilbo_states:
            prob = BILBO_PROBABILITIES.get(direction, {}).get(zone_state, 0)
            modifiers.append(("bilbo_upgrade", +3, f"Bilbo confirmed ({prob:.0%} backtested) → A+"))

        time_est = kw.get("time_est")
        hour = _parse_hour(time_est)
        if hour is not None and hour >= 13:
            modifiers.append(("late_session", -1, f"After 1pm EST — lower completion rate"))

        return modifiers

    def get_probability(self, direction, phase, **kw):
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "mid_rising")
        return BILBO_PROBABILITIES.get(direction, {}).get(
            zone_state, BASELINE_PROBABILITY.get(direction, 0.63)
        )


register("golden_gate", GoldenGateEvaluator())
