"""Setup registry — maps setup_type strings to evaluators."""

from api.indicators.satyland.setups.base import SetupEvaluator

_REGISTRY: dict[str, SetupEvaluator] = {}


def register(setup_type: str, evaluator: SetupEvaluator) -> None:
    _REGISTRY[setup_type] = evaluator


def get_evaluator(setup_type: str) -> SetupEvaluator:
    if setup_type not in _REGISTRY:
        raise ValueError(f"Unknown setup: {setup_type}")
    return _REGISTRY[setup_type]


def registered_setups() -> list[str]:
    return list(_REGISTRY.keys())


import api.indicators.satyland.setups.flag_into_ribbon  # noqa: F401
import api.indicators.satyland.setups.golden_gate  # noqa: F401
