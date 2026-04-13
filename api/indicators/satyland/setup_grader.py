"""
Setup-aware green flag grading — replaces generic green_flag.py.

See: docs/superpowers/specs/2026-04-12-trading-companion-design.md Section 5
"""

from typing import Any

from api.indicators.satyland.setups import get_evaluator


def _base_grade(bonus_count: int) -> str:
    if bonus_count >= 4:
        return "A+"
    elif bonus_count == 3:
        return "A"
    elif bonus_count == 2:
        return "B"
    return "skip"


def _apply_modifiers(grade: str, modifiers: list[tuple[str, int, str]]) -> tuple[str, list[str]]:
    """Apply grade modifiers (upgrade/downgrade). Returns (final_grade, modifier_reasons)."""
    grades = ["skip", "B", "A", "A+"]
    idx = grades.index(grade)
    reasons = []

    for name, delta, reason in modifiers:
        idx = max(0, min(len(grades) - 1, idx + delta))
        reasons.append(reason)

    return grades[idx], reasons


def grade_setup(
    setup_type: str,
    direction: str,
    atr: dict,
    ribbon: dict,
    phase: dict,
    structure: dict,
    mtf_scores: dict,
    vix: float | None = None,
    time_est: str | None = None,
    personal_win_rate: float | None = None,
    personal_trade_count: int = 0,
    **kwargs: Any,
) -> dict:
    """
    Grade a trade setup using setup-specific required + bonus flags.

    Returns:
        {
            "setup_type": str,
            "direction": str,
            "grade": "A+" | "A" | "B" | "skip",
            "score": int (bonus count),
            "required_flags": [{"name": str, "passed": bool, "reason": str}],
            "bonus_flags": [{"name": str, "passed": bool, "reason": str}],
            "modifiers": [str],
            "probability": float,
            "probability_source": "backtested" | "estimated" | "personal",
            "reasoning": str,
        }
    """
    evaluator = get_evaluator(setup_type)

    required = evaluator.evaluate_required(
        direction, atr, ribbon, phase, structure, mtf_scores,
        vix=vix, time_est=time_est, **kwargs,
    )
    bonus = evaluator.evaluate_bonus(
        direction, atr, ribbon, phase, structure, mtf_scores,
        vix=vix, time_est=time_est, **kwargs,
    )

    # Check required flags
    required_flags = [{"name": n, "passed": p, "reason": r} for n, p, r in required]
    all_required_pass = all(f["passed"] for f in required_flags)

    # Count bonus flags
    bonus_flags = [{"name": n, "passed": p, "reason": r} for n, p, r in bonus]
    bonus_count = sum(1 for f in bonus_flags if f["passed"])

    # Grade
    if not all_required_pass:
        grade = "skip"
    else:
        grade = _base_grade(bonus_count)

    # Modifiers (setup-specific, e.g. Bilbo for Golden Gate)
    modifiers = []
    if hasattr(evaluator, "get_modifiers"):
        modifiers = evaluator.get_modifiers(
            direction, atr, ribbon, phase, structure, mtf_scores,
            vix=vix, time_est=time_est, **kwargs,
        )
    mod_reasons = []
    if modifiers and all_required_pass:
        grade, mod_reasons = _apply_modifiers(grade, modifiers)

    # Probability
    if personal_trade_count >= 30 and personal_win_rate is not None:
        probability = personal_win_rate
        prob_source = "personal"
    elif hasattr(evaluator, "get_probability"):
        probability = evaluator.get_probability(direction, phase, time_est=time_est, **kwargs)
        prob_source = "backtested" if hasattr(evaluator, "BACKTESTED") else "estimated"
    else:
        probability = 0.5
        prob_source = "estimated"

    # Build reasoning
    req_text = "\n".join(
        f"  {'✅' if f['passed'] else '❌'} {f['name']}: {f['reason']}"
        for f in required_flags
    )
    bonus_text = "\n".join(
        f"  {'✅' if f['passed'] else '⬜'} {f['name']}: {f['reason']}"
        for f in bonus_flags
    )
    mod_text = "\n".join(f"  → {r}" for r in mod_reasons) if mod_reasons else ""

    reasoning = (
        f"Setup: {setup_type} ({direction})\n"
        f"Required flags:\n{req_text}\n"
        f"Bonus flags ({bonus_count}/{len(bonus_flags)}):\n{bonus_text}\n"
    )
    if mod_text:
        reasoning += f"Modifiers:\n{mod_text}\n"
    reasoning += f"Grade: {grade} | Probability: {probability:.0%} ({prob_source})"

    return {
        "setup_type": setup_type,
        "direction": direction,
        "grade": grade,
        "score": bonus_count,
        "max_bonus": len(bonus_flags),
        "required_flags": required_flags,
        "bonus_flags": bonus_flags,
        "modifiers": mod_reasons,
        "probability": round(probability, 3),
        "probability_source": prob_source,
        "reasoning": reasoning,
    }
