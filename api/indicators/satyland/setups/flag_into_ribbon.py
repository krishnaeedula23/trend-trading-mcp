"""Flag Into Ribbon — Classic Trend Continuation setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class FlagIntoRibbonEvaluator(SetupEvaluator):
    """
    Flag Into Ribbon: price pulls back into a stacked ribbon then resumes trend.

    Required flags (all must pass — else grade = "skip"):
      - ribbon_stacked: ribbon_state matches direction
      - price_at_ema_pullback: bias_candle is blue (bullish) or orange (bearish)
      - atr_room: atr_room_ok is True (<70% consumed)

    Bonus flags (count drives A+/A/B):
      - phase_firing: phase matches direction (green/red)
      - mtf_aligned: all TFs same sign AND min_score >= 10
      - structure_confirmed: above PDH/PMH (calls) or below PDL/PML (puts)
      - vix_bias: VIX <17 for bulls, >20 for bears
    """

    name = "flag_into_ribbon"

    # Estimated win rates by direction (no backtested data yet)
    _PROB = {"bullish": 0.62, "bearish": 0.60}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # ribbon_stacked: ribbon_state must match direction
        ribbon_state = ribbon.get("ribbon_state", "")
        stacked = ribbon_state == direction
        flags.append((
            "ribbon_stacked",
            stacked,
            f"ribbon_state={ribbon_state!r} {'matches' if stacked else 'does not match'} direction={direction!r}",
        ))

        # price_at_ema_pullback: bias_candle must be blue (bullish) or orange (bearish)
        bias_candle = ribbon.get("bias_candle", "")
        expected_candle = "blue" if direction == "bullish" else "orange"
        at_pullback = bias_candle == expected_candle
        flags.append((
            "price_at_ema_pullback",
            at_pullback,
            f"bias_candle={bias_candle!r}, expected {expected_candle!r} for {direction}",
        ))

        # atr_room: atr_room_ok must be True
        atr_room_ok = atr.get("atr_room_ok", False)
        atr_pct = atr.get("atr_covered_pct", 0.0)
        flags.append((
            "atr_room",
            bool(atr_room_ok),
            f"atr_covered_pct={atr_pct:.1f}% ({'ok' if atr_room_ok else 'exceeded'})",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        vix: float | None = kwargs.get("vix")

        # phase_firing: phase matches direction
        current_phase = phase.get("phase", "")
        expected_phase = "green" if direction == "bullish" else "red"
        phase_ok = current_phase == expected_phase
        flags.append((
            "phase_firing",
            phase_ok,
            f"phase={current_phase!r}, expected {expected_phase!r}",
        ))

        # mtf_aligned: alignment matches direction AND min_score >= 10
        mtf_alignment = mtf_scores.get("alignment", "")
        min_score = mtf_scores.get("min_score", 0)
        mtf_ok = (mtf_alignment == direction) and (min_score >= 10)
        flags.append((
            "mtf_aligned",
            mtf_ok,
            f"alignment={mtf_alignment!r}, min_score={min_score} ({'ok' if mtf_ok else 'not aligned or weak'})",
        ))

        # structure_confirmed: above PDH/PMH (bullish) or below PDL/PML (bearish)
        if direction == "bullish":
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

        # vix_bias: VIX <17 for bulls, >20 for bears
        if vix is not None:
            if direction == "bullish":
                vix_ok = vix < 17.0
                flags.append((
                    "vix_bias",
                    vix_ok,
                    f"VIX={vix:.1f} ({'<17 bullish' if vix_ok else '>=17 unfavorable'})",
                ))
            else:
                vix_ok = vix > 20.0
                flags.append((
                    "vix_bias",
                    vix_ok,
                    f"VIX={vix:.1f} ({'>20 bearish' if vix_ok else '<=20 unfavorable'})",
                ))
        else:
            flags.append(("vix_bias", False, "VIX not provided"))

        return flags

    def get_probability(
        self, direction: str, phase: dict, **kwargs: Any,
    ) -> float:
        return self._PROB.get(direction, 0.5)


register("flag_into_ribbon", FlagIntoRibbonEvaluator())
