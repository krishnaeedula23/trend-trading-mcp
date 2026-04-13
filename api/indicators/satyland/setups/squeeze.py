"""Squeeze — Volatility Expansion setup evaluator."""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class SqueezeEvaluator(SetupEvaluator):
    """
    Volatility Expansion / Squeeze: price coiling in compression before a directional move.

    Required flags:
      - compression_active: phase in_compression is True OR phase == "compression"
      - ribbon_coiling: ribbon_state is NOT "chopzilla" (coiling is ok)
      - htf_directional: at least one higher TF has |score| >= 7

    Bonus flags:
      - a_plus_mtf: any TF has is_a_plus (score ±15 + compression)
      - all_tf_aligned: all TF scores same sign
      - atr_room: atr_room_ok
      - structure_confirmed: structure aligns with direction
      - vix_calm: VIX < 20
    """

    name = "squeeze"

    _PROB = {"bullish": 0.61, "bearish": 0.60}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # compression_active
        in_compression = phase.get("in_compression", False)
        phase_str = phase.get("phase", "")
        compression_active = bool(in_compression) or phase_str == "compression"
        flags.append((
            "compression_active",
            compression_active,
            f"in_compression={in_compression}, phase={phase_str!r}",
        ))

        # ribbon_coiling: NOT "chopzilla"
        ribbon_state = ribbon.get("ribbon_state", "")
        coiling = ribbon_state != "chopzilla"
        flags.append((
            "ribbon_coiling",
            coiling,
            f"ribbon_state={ribbon_state!r} ({'coiling ok' if coiling else 'chopzilla — not a squeeze setup'})",
        ))

        # htf_directional: at least one TF with |score| >= 7
        tf_keys = [k for k in mtf_scores if k not in ("alignment", "min_score", "conviction", "exec_score")]
        htf_ok = any(
            abs(mtf_scores[tf].get("score", 0)) >= 7
            for tf in tf_keys
            if isinstance(mtf_scores[tf], dict)
        )
        tf_score_str = ", ".join(
            f"{k}={mtf_scores[k].get('score', 0)}"
            for k in tf_keys
            if isinstance(mtf_scores[k], dict)
        )
        flags.append((
            "htf_directional",
            htf_ok,
            f"TF scores: {tf_score_str}",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []
        is_bull = direction == "bullish"
        vix: float | None = kwargs.get("vix")

        # a_plus_mtf
        tf_keys = [k for k in mtf_scores if k not in ("alignment", "min_score", "conviction", "exec_score")]
        a_plus = any(
            mtf_scores[tf].get("is_a_plus", False)
            for tf in tf_keys
            if isinstance(mtf_scores[tf], dict)
        )
        flags.append((
            "a_plus_mtf",
            a_plus,
            f"a_plus found: {a_plus}",
        ))

        # all_tf_aligned
        tf_scores = [
            mtf_scores[tf].get("score", 0)
            for tf in tf_keys
            if isinstance(mtf_scores[tf], dict)
        ]
        if tf_scores:
            all_pos = all(s > 0 for s in tf_scores)
            all_neg = all(s < 0 for s in tf_scores)
            all_aligned = all_pos if is_bull else all_neg
        else:
            all_aligned = False
        flags.append((
            "all_tf_aligned",
            all_aligned,
            f"TF scores all {'positive' if is_bull else 'negative'}: {all_aligned}",
        ))

        # atr_room
        atr_room_ok = atr.get("atr_room_ok", False)
        atr_pct = atr.get("atr_covered_pct", 0.0)
        flags.append((
            "atr_room",
            bool(atr_room_ok),
            f"atr_covered_pct={atr_pct:.1f}% ({'ok' if atr_room_ok else 'exceeded'})",
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

        # vix_calm
        if vix is not None:
            vix_calm = vix < 20.0
            flags.append((
                "vix_calm",
                vix_calm,
                f"VIX={vix:.1f} ({'calm <20' if vix_calm else 'elevated >=20'})",
            ))
        else:
            flags.append(("vix_calm", False, "VIX not provided"))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


register("squeeze", SqueezeEvaluator())
