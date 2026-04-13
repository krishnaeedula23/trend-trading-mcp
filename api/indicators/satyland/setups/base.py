"""Base class for setup-specific flag evaluators."""

from typing import Any


class SetupEvaluator:
    """
    Base class for setup flag evaluation.

    Subclasses implement evaluate_required() and evaluate_bonus().
    Each returns a list of (flag_name, passed: bool, reason: str) tuples.
    """

    name: str = "unknown"

    def evaluate_required(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        raise NotImplementedError

    def evaluate_bonus(
        self, direction: str, atr: dict, ribbon: dict, phase: dict,
        structure: dict, mtf_scores: dict, **kwargs: Any,
    ) -> list[tuple[str, bool, str]]:
        raise NotImplementedError
