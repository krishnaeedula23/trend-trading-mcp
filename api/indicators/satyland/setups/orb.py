"""ORB — 10-Minute Open Range Breakout setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class OrbEvaluator(SetupEvaluator):
    """
    10-Minute Open Range Breakout: price closes outside the first 10-min range
    after a confirmed retest of the breakout level.

    Required flags:
      - or_marked: kw has or_high and or_low (non-zero)
      - candle_close_outside: current_price > or_high (bull) or < or_low (bear)
      - retest_confirmed: kw has retest_confirmed=True

    Bonus flags:
      - mtf_aligned: all TFs same sign, matches direction
      - phase_firing: phase matches direction
      - structure_confirmed: breakout aligns with PDH/PDL/PMH/PML
      - atr_room: atr_room_ok
      - or_size_ok: kw has or_size_ok=True
    """

    name = "orb"

    _PROB = {"bullish": 0.60, "bearish": 0.59}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        is_bull = direction == "bullish"

        # or_marked: must have non-zero or_high and or_low
        or_high = kwargs.get("or_high", 0)
        or_low = kwargs.get("or_low", 0)
        or_marked = bool(or_high) and bool(or_low)
        flags.append((
            "or_marked",
            or_marked,
            f"or_high={or_high}, or_low={or_low} ({'set' if or_marked else 'not set'})",
        ))

        # candle_close_outside: current_price beyond the range
        current_price = atr.get("current_price", 0)
        if is_bull:
            outside = current_price > or_high if or_high else False
        else:
            outside = current_price < or_low if or_low else False
        flags.append((
            "candle_close_outside",
            outside,
            f"current_price={current_price}, {'or_high' if is_bull else 'or_low'}={or_high if is_bull else or_low} "
            f"({'closed outside' if outside else 'still inside range'})",
        ))

        # retest_confirmed
        retest_confirmed = bool(kwargs.get("retest_confirmed", False))
        flags.append((
            "retest_confirmed",
            retest_confirmed,
            f"retest_confirmed={retest_confirmed}",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        is_bull = direction == "bullish"

        # mtf_aligned: alignment matches direction
        mtf_alignment = mtf_scores.get("alignment", "")
        mtf_ok = mtf_alignment == direction
        flags.append((
            "mtf_aligned",
            mtf_ok,
            f"alignment={mtf_alignment!r} ({'ok' if mtf_ok else 'not aligned'})",
        ))

        # phase_firing
        current_phase = phase.get("phase", "")
        expected_phase = "green" if is_bull else "red"
        phase_ok = current_phase == expected_phase
        flags.append((
            "phase_firing",
            phase_ok,
            f"phase={current_phase!r}, expected {expected_phase!r}",
        ))

        # structure_confirmed
        if is_bull:
            above_pdh = structure.get("price_above_pdh", False)
            above_pmh = structure.get("price_above_pmh", False)
            struct_ok = bool(above_pdh or above_pmh)
            flags.append((
                "structure_confirmed",
                struct_ok,
                f"price_above_pdh={above_pdh}, price_above_pmh={above_pmh}",
            ))
        else:
            below_pdl = structure.get("price_below_pdl", False)
            below_pml = structure.get("price_below_pml", False)
            struct_ok = bool(below_pdl or below_pml)
            flags.append((
                "structure_confirmed",
                struct_ok,
                f"price_below_pdl={below_pdl}, price_below_pml={below_pml}",
            ))

        # atr_room
        atr_room_ok = atr.get("atr_room_ok", False)
        atr_pct = atr.get("atr_covered_pct", 0.0)
        flags.append((
            "atr_room",
            bool(atr_room_ok),
            f"atr_covered_pct={atr_pct:.1f}% ({'ok' if atr_room_ok else 'exceeded'})",
        ))

        # or_size_ok
        or_size_ok = bool(kwargs.get("or_size_ok", False))
        flags.append((
            "or_size_ok",
            or_size_ok,
            f"or_size_ok={or_size_ok}",
        ))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


register("orb", OrbEvaluator())
