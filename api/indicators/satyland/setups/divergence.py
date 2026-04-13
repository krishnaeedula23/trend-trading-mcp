"""Divergence — Divergence From Extreme setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class DivergenceEvaluator(SetupEvaluator):
    """
    Divergence From Extreme: price makes a new swing high/low while the Phase
    Oscillator diverges — signals exhaustion.

    Required flags:
      - swing_formed: kw has swing_type ("high" or "low")
      - po_divergence: kw has po_divergence=True
      - ribbon_exhaustion: ribbon in_compression OR ribbon_state is "chopzilla"

    Bonus flags:
      - mtf_divergence: divergence visible on multiple TFs
      - at_atr_extreme: atr_covered_pct >= 61.8
      - volume_declining: kw has volume_declining=True
      - mtf_score_weakening: MTF score magnitude decreasing
    """

    name = "divergence"

    _PROB = {"bullish": 0.59, "bearish": 0.58}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # swing_formed
        swing_type = kwargs.get("swing_type")
        swing_formed = swing_type is not None
        flags.append((
            "swing_formed",
            swing_formed,
            f"swing_type={swing_type!r} ({'present' if swing_formed else 'not provided'})",
        ))

        # po_divergence
        po_divergence = bool(kwargs.get("po_divergence", False))
        flags.append((
            "po_divergence",
            po_divergence,
            f"po_divergence={po_divergence}",
        ))

        # ribbon_exhaustion
        in_compression = ribbon.get("in_compression", False)
        ribbon_state = ribbon.get("ribbon_state", "")
        exhausted = bool(in_compression) or ribbon_state == "chopzilla"
        flags.append((
            "ribbon_exhaustion",
            exhausted,
            f"in_compression={in_compression}, ribbon_state={ribbon_state!r}",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # mtf_divergence
        mtf_div = bool(kwargs.get("mtf_divergence", False))
        flags.append((
            "mtf_divergence",
            mtf_div,
            f"mtf_divergence={mtf_div}",
        ))

        # at_atr_extreme: atr_covered_pct >= 61.8
        atr_pct = atr.get("atr_covered_pct", 0.0)
        at_extreme = atr_pct >= 61.8
        flags.append((
            "at_atr_extreme",
            at_extreme,
            f"atr_covered_pct={atr_pct:.1f}% ({'at extreme >=61.8%' if at_extreme else 'not at extreme'})",
        ))

        # volume_declining
        vol_declining = bool(kwargs.get("volume_declining", False))
        flags.append((
            "volume_declining",
            vol_declining,
            f"volume_declining={vol_declining}",
        ))

        # mtf_score_weakening
        score_weakening = bool(kwargs.get("score_weakening", False))
        flags.append((
            "mtf_score_weakening",
            score_weakening,
            f"score_weakening={score_weakening}",
        ))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


register("divergence_from_extreme", DivergenceEvaluator())
