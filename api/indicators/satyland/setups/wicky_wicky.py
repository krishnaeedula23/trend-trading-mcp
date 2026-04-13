"""Wicky Wicky — Tweezer Bottom setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class WickyWickyEvaluator(SetupEvaluator):
    """
    Wicky Wicky / Tweezer Bottom: two candles form a matching low with long wicks,
    followed by a reclaim of the midpoint — signals bullish reversal.

    Required flags:
      - tweezer_pattern: kw has tweezer_detected=True
      - reclaim_50pct: kw has reclaim_confirmed=True

    Bonus flags:
      - po_divergence: phase == "green" or kw po_bullish_div=True
      - at_key_level: kw has at_key_level=True
      - volume_increasing: kw has volume_increasing=True
      - mtf_not_strongly_negative: MTF min_score > -10
      - ribbon_flattening: ribbon in_compression or ribbon_state != "bearish"
    """

    name = "wicky_wicky"

    _PROB = {"bullish": 0.60, "bearish": 0.57}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # tweezer_pattern
        tweezer_detected = bool(kwargs.get("tweezer_detected", False))
        flags.append((
            "tweezer_pattern",
            tweezer_detected,
            f"tweezer_detected={tweezer_detected}",
        ))

        # reclaim_50pct
        reclaim_confirmed = bool(kwargs.get("reclaim_confirmed", False))
        flags.append((
            "reclaim_50pct",
            reclaim_confirmed,
            f"reclaim_confirmed={reclaim_confirmed}",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # po_divergence
        current_phase = phase.get("phase", "")
        po_bullish_div = bool(kwargs.get("po_bullish_div", False))
        po_div = current_phase == "green" or po_bullish_div
        flags.append((
            "po_divergence",
            po_div,
            f"phase={current_phase!r}, po_bullish_div={po_bullish_div}",
        ))

        # at_key_level
        at_key_level = bool(kwargs.get("at_key_level", False))
        flags.append((
            "at_key_level",
            at_key_level,
            f"at_key_level={at_key_level}",
        ))

        # volume_increasing
        volume_increasing = bool(kwargs.get("volume_increasing", False))
        flags.append((
            "volume_increasing",
            volume_increasing,
            f"volume_increasing={volume_increasing}",
        ))

        # mtf_not_strongly_negative: min_score > -10
        min_score = mtf_scores.get("min_score", 0)
        not_strongly_neg = min_score > -10
        flags.append((
            "mtf_not_strongly_negative",
            not_strongly_neg,
            f"min_score={min_score} ({'> -10 ok' if not_strongly_neg else '<= -10 fighting strong bear'})",
        ))

        # ribbon_flattening
        in_compression = ribbon.get("in_compression", False)
        ribbon_state = ribbon.get("ribbon_state", "")
        flattening = bool(in_compression) or ribbon_state != "bearish"
        flags.append((
            "ribbon_flattening",
            flattening,
            f"in_compression={in_compression}, ribbon_state={ribbon_state!r}",
        ))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


register("wicky_wicky", WickyWickyEvaluator())
