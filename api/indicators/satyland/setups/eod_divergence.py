"""EOD Divergence — 1-Min End-of-Day Divergence setup evaluator."""

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


class EodDivergenceEvaluator(SetupEvaluator):
    """
    1-Minute EOD Divergence: late-session divergence on the 1-min chart,
    targeting a quick mean-reversion into close.

    Required flags:
      - after_noon_pst: kw has time_est and hour >= 15 (3pm EST)
      - po_divergence: kw has po_divergence=True
      - swing_formed: kw has swing_type

    Bonus flags:
      - volume_present: kw has volume_present=True
      - at_atr_extreme: atr_covered_pct >= 61.8
      - ribbon_exhaustion: ribbon in_compression or chopzilla
      - target_nearby: kw has target_nearby=True
    """

    name = "eod_divergence"

    _PROB = {"bullish": 0.56, "bearish": 0.55}

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # after_noon_pst (3pm EST = market hour >= 15)
        time_est = kwargs.get("time_est")
        hour = _parse_hour(time_est)
        after_noon = hour is not None and hour >= 15
        flags.append((
            "after_noon_pst",
            after_noon,
            f"time_est={time_est!r}, hour={hour} ({'>=15 EST ok' if after_noon else 'too early or not provided'})",
        ))

        # po_divergence
        po_divergence = bool(kwargs.get("po_divergence", False))
        flags.append((
            "po_divergence",
            po_divergence,
            f"po_divergence={po_divergence}",
        ))

        # swing_formed
        swing_type = kwargs.get("swing_type")
        swing_formed = swing_type is not None
        flags.append((
            "swing_formed",
            swing_formed,
            f"swing_type={swing_type!r} ({'present' if swing_formed else 'not provided'})",
        ))

        return flags

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        flags: list[tuple[str, bool, str]] = []

        # volume_present
        vol_present = bool(kwargs.get("volume_present", False))
        flags.append((
            "volume_present",
            vol_present,
            f"volume_present={vol_present}",
        ))

        # at_atr_extreme
        atr_pct = atr.get("atr_covered_pct", 0.0)
        at_extreme = atr_pct >= 61.8
        flags.append((
            "at_atr_extreme",
            at_extreme,
            f"atr_covered_pct={atr_pct:.1f}% ({'at extreme >=61.8%' if at_extreme else 'not at extreme'})",
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

        # target_nearby
        target_nearby = bool(kwargs.get("target_nearby", False))
        flags.append((
            "target_nearby",
            target_nearby,
            f"target_nearby={target_nearby} (21 EMA or VWAP close)",
        ))

        return flags

    def get_probability(self, direction: str, phase: dict, **kwargs: Any) -> float:
        return self._PROB.get(direction, 0.5)


register("eod_divergence", EodDivergenceEvaluator())
