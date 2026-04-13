"""Vomy/iVomy — Trend Reversal setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class VomyEvaluator(SetupEvaluator):
    """
    Vomy (bearish reversal) / iVomy (bullish reversal).

    Direction "bullish" = iVomy: ribbon was bearish, now transitioning, price reclaiming.
    Direction "bearish" = Vomy: ribbon was bullish, now transitioning, price rolling over.

    Required flags:
      - ribbon_transitioning: ribbon_state is NOT matching direction (crossing/folding).
        "chopzilla" accepted as transitioning.
      - price_retesting_ribbon: bias_candle is "blue" (iVomy) or "orange" (Vomy).
      - mtf_score_flipped: MTF score sign has changed — for Vomy score going negative,
        for iVomy score going positive.

    Bonus flags:
      - ema48_broken: above 48 EMA (iVomy) or below (Vomy)
      - phase_confirming: phase matches new direction
      - structure_break: above PDH/PMH (iVomy) or below PDL/PML (Vomy)
      - higher_tf_shifting: higher TF MTF scores starting to shift same direction
      - vix_bias: VIX aligns with direction
    """

    name = "vomy"

    _PROB = {"bullish": 0.58, "bearish": 0.57}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        is_bull = direction == "bullish"

        # ribbon_transitioning: ribbon_state should NOT match direction
        ribbon_state = ribbon.get("ribbon_state", "")
        transitioning = ribbon_state != direction or ribbon_state == "chopzilla"
        flags.append((
            "ribbon_transitioning",
            transitioning,
            f"ribbon_state={ribbon_state!r} ({'transitioning' if transitioning else 'still aligned — not reversing'})",
        ))

        # price_retesting_ribbon: bias_candle must be "blue" (iVomy) or "orange" (Vomy)
        bias_candle = ribbon.get("bias_candle", "")
        expected_candle = "blue" if is_bull else "orange"
        retesting = bias_candle == expected_candle
        flags.append((
            "price_retesting_ribbon",
            retesting,
            f"bias_candle={bias_candle!r}, expected {expected_candle!r} for {direction}",
        ))

        # mtf_score_flipped: execution TF score sign changed
        # For iVomy (bullish): score should be positive (flipped up)
        # For Vomy (bearish): score should be negative (flipped down)
        exec_score = mtf_scores.get("exec_score", mtf_scores.get("min_score", 0))
        if is_bull:
            flipped = exec_score > 0
        else:
            flipped = exec_score < 0
        flags.append((
            "mtf_score_flipped",
            flipped,
            f"exec_score={exec_score} ({'positive — bullish flip' if exec_score > 0 else 'negative — bearish flip' if exec_score < 0 else 'zero — no flip'})",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        is_bull = direction == "bullish"
        vix: float | None = kwargs.get("vix")

        # ema48_broken
        above_48ema = ribbon.get("above_48ema", False)
        ema48_ok = bool(above_48ema) if is_bull else not bool(above_48ema)
        flags.append((
            "ema48_broken",
            ema48_ok,
            f"above_48ema={above_48ema} ({'above for iVomy' if is_bull else 'below for Vomy'}: {'ok' if ema48_ok else 'not met'})",
        ))

        # phase_confirming
        current_phase = phase.get("phase", "")
        expected_phase = "green" if is_bull else "red"
        phase_ok = current_phase == expected_phase
        flags.append((
            "phase_confirming",
            phase_ok,
            f"phase={current_phase!r}, expected {expected_phase!r}",
        ))

        # structure_break
        if is_bull:
            above_pdh = structure.get("price_above_pdh", False)
            above_pmh = structure.get("price_above_pmh", False)
            struct_ok = bool(above_pdh or above_pmh)
            flags.append((
                "structure_break",
                struct_ok,
                f"price_above_pdh={above_pdh}, price_above_pmh={above_pmh}",
            ))
        else:
            below_pdl = structure.get("price_below_pdl", False)
            below_pml = structure.get("price_below_pml", False)
            struct_ok = bool(below_pdl or below_pml)
            flags.append((
                "structure_break",
                struct_ok,
                f"price_below_pdl={below_pdl}, price_below_pml={below_pml}",
            ))

        # higher_tf_shifting
        htf_shifting = bool(kwargs.get("htf_shifting", False))
        flags.append((
            "higher_tf_shifting",
            htf_shifting,
            f"htf_shifting={htf_shifting}",
        ))

        # vix_bias
        if vix is not None:
            vix_ok = vix < 17.0 if is_bull else vix > 20.0
            flags.append((
                "vix_bias",
                vix_ok,
                f"VIX={vix:.1f} ({'<17 bullish' if is_bull else '>20 bearish'}: {'ok' if vix_ok else 'not met'})",
            ))
        else:
            flags.append(("vix_bias", False, "VIX not provided"))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


_evaluator = VomyEvaluator()
register("vomy", _evaluator)
register("ivomy", _evaluator)
