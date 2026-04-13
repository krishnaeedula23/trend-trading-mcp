# Trading Companion System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude-powered trading companion that delivers pre-market briefs, real-time setup alerts via TradingView webhooks, trade logging with voice/text input, journaling, and self-correcting analytics — all persisted in Supabase and viewable on the existing Next.js frontend.

**Architecture:** TradingView monitors charts and fires webhook alerts to the Saty API on Railway. The API grades setups using a reworked green flag system with setup-specific flags, MTF scoring, and Bilbo probability data. Results post to Slack. Trades, journals, and notes are logged via Slack/CLI/Desktop and stored in Supabase. The existing Next.js frontend gains journal, analytics, and alert history pages.

**Tech Stack:** Python 3.12 (FastAPI, Supabase client), Next.js 16 (React 19, shadcn/ui, Recharts), Supabase (Postgres + Edge Functions), Slack API, TradingView webhooks

**Spec:** `docs/superpowers/specs/2026-04-12-trading-companion-design.md`

---

## Dependency Graph

```
Phase 1: MTF Score + PO Zones (foundational)
    ↓
Phase 2: Green Flag Rework (depends on Phase 1)
    ↓
Phase 3: Supabase Tables (independent, can parallel with 1-2)
    ↓
Phase 4: TradingView Webhook Endpoint (depends on 2 + 3)
    ↓
Phase 5: Slack Integration + Scheduled Tasks (depends on 3 + 4)
    ↓
Phase 6: Trade Logging + Journal + Notes (depends on 3 + 5)
    ↓
Phase 7: Analytics (depends on 3 + 6)
```

Phases 1-2 and Phase 3 can run in parallel. Everything else is sequential.

---

## File Structure

### New Files

| File | Responsibility |
|------|----------------|
| `api/indicators/satyland/mtf_score.py` | MTF EMA Score calculation (-15 to +15) per timeframe |
| `api/indicators/satyland/setup_grader.py` | Setup-aware green flag grading (replaces generic green_flag logic) |
| `api/indicators/satyland/setups/` | Directory for per-setup flag definitions |
| `api/indicators/satyland/setups/__init__.py` | Setup registry |
| `api/indicators/satyland/setups/base.py` | Base class for setup evaluators |
| `api/indicators/satyland/setups/flag_into_ribbon.py` | Flag Into Ribbon required + bonus flags |
| `api/indicators/satyland/setups/golden_gate.py` | Golden Gate with Bilbo filter |
| `api/indicators/satyland/setups/vomy.py` | Vomy/iVomy flags |
| `api/indicators/satyland/setups/orb.py` | ORB flags |
| `api/indicators/satyland/setups/squeeze.py` | Squeeze flags |
| `api/indicators/satyland/setups/divergence.py` | Divergence From Extreme flags |
| `api/indicators/satyland/setups/eod_divergence.py` | EOD Divergence flags |
| `api/indicators/satyland/setups/wicky_wicky.py` | Tweezer Bottom flags |
| `api/endpoints/webhooks.py` | TradingView webhook receiver endpoint |
| `api/endpoints/trades.py` | Trade CRUD endpoints (for frontend + Supabase) |
| `api/endpoints/journal.py` | Journal + notes endpoints |
| `api/endpoints/analytics.py` | Analytics query endpoints |
| `api/integrations/slack.py` | Slack message sending + formatting |
| `api/integrations/supabase_client.py` | Supabase client initialization + helpers |
| `tests/satyland/test_mtf_score.py` | MTF Score tests |
| `tests/satyland/test_setup_grader.py` | Setup-aware grading tests |
| `tests/satyland/test_setups/` | Per-setup flag tests |
| `tests/satyland/test_webhooks.py` | Webhook endpoint tests |
| `api/utils/data_fetch.py` | Shared data fetch functions (extracted from satyland.py) |
| `tests/satyland/test_setups/__init__.py` | Test package init |
| `tests/satyland/test_trades.py` | Trade logging tests |

### Modified Files

| File | What Changes |
|------|-------------|
| `api/indicators/satyland/phase_oscillator.py` | Add zone classification (high/mid/low + rising/falling → zone_state) |
| `api/indicators/satyland/green_flag.py` | Deprecate, redirect to setup_grader.py |
| `api/endpoints/satyland.py` | Update `/trade-plan` to use new setup_grader, add `/mtf-score` endpoint |
| `api/main.py` | Register new routers (webhooks, trades, journal, analytics) |
| `tests/satyland/conftest.py` | Add fixtures for MTF data, multi-timeframe DataFrames |

---

## Phase 1: MTF Score + Phase Oscillator Zones

### Task 1.1: Phase Oscillator Zone Classification

**Files:**
- Modify: `api/indicators/satyland/phase_oscillator.py:82-191`
- Test: `tests/satyland/test_phase_oscillator.py`

- [ ] **Step 1: Write failing tests for zone classification**

```python
# tests/satyland/test_phase_oscillator.py — append to existing file

class TestZoneClassification:
    """Zone + direction state for Bilbo filtering (spec Section 7)."""

    def test_high_rising_zone(self, trending_up_df):
        result = phase_oscillator(trending_up_df)
        assert result["zone"] in ("high", "mid", "low")
        assert result["direction"] in ("rising", "falling")
        assert result["zone_state"] in (
            "high_rising", "high_falling",
            "mid_rising", "mid_falling",
            "low_rising", "low_falling",
        )

    def test_zone_high_threshold(self, trending_up_df):
        result = phase_oscillator(trending_up_df)
        if result["oscillator"] > 38.2:
            assert result["zone"] == "high"
        elif result["oscillator"] < -38.2:
            assert result["zone"] == "low"
        else:
            assert result["zone"] == "mid"

    def test_zone_direction_from_previous(self, trending_up_df):
        result = phase_oscillator(trending_up_df)
        if result["oscillator"] > result["oscillator_prev"]:
            assert result["direction"] == "rising"
        else:
            assert result["direction"] == "falling"

    def test_zone_state_composite(self, trending_up_df):
        result = phase_oscillator(trending_up_df)
        assert result["zone_state"] == f"{result['zone']}_{result['direction']}"

    def test_bearish_low_falling(self, trending_down_df):
        result = phase_oscillator(trending_down_df)
        assert result["zone"] == "low"
        assert result["direction"] == "falling"
        assert result["zone_state"] == "low_falling"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/krishnaeedula/claude/coding/trend-trading-mcp && venv/bin/pytest tests/satyland/test_phase_oscillator.py::TestZoneClassification -v`
Expected: FAIL — `KeyError: 'zone'`

- [ ] **Step 3: Implement zone classification in phase_oscillator.py**

Add to `phase_oscillator()` return dict, after existing `zone_crosses` calculation (around line 175):

```python
# Zone classification for Bilbo filtering
osc_val = float(oscillator.iloc[-1])
osc_prev = float(oscillator.iloc[-2])

if osc_val > 38.2:
    zone = "high"
elif osc_val < -38.2:
    zone = "low"
else:
    zone = "mid"

direction = "rising" if osc_val > osc_prev else "falling"
zone_state = f"{zone}_{direction}"
```

Add to return dict:
```python
"zone": zone,
"direction": direction,
"zone_state": zone_state,
```

- [ ] **Step 4: Run all phase oscillator tests**

Run: `venv/bin/pytest tests/satyland/test_phase_oscillator.py -v`
Expected: ALL PASS (new + existing)

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/phase_oscillator.py tests/satyland/test_phase_oscillator.py
git commit -m "feat: add zone classification to phase oscillator for Bilbo filtering"
```

---

### Task 1.2: MTF Score Module

**Files:**
- Create: `api/indicators/satyland/mtf_score.py`
- Create: `tests/satyland/test_mtf_score.py`
- Modify: `tests/satyland/conftest.py` (add 250-bar fixtures — existing 50-bar fixtures are too short for 200-period EMA convergence)

**Important:** The existing `trending_up_df` and `trending_down_df` fixtures have only 50 bars. The MTF score needs a 200-period EMA, so add `trending_up_250_df` and `trending_down_250_df` fixtures with 250 bars to `conftest.py` before writing these tests.

- [ ] **Step 1: Write failing tests**

```python
# tests/satyland/test_mtf_score.py

import pandas as pd
import pytest
from api.indicators.satyland.mtf_score import mtf_score


class TestMTFScoreCalculation:
    """MTF Score: -15 to +15 based on EMA crosses + trend directions."""

    def test_perfect_bullish_score(self, trending_up_df):
        """Strongly trending up → score near +15."""
        result = mtf_score(trending_up_df)
        assert result["score"] > 10
        assert result["score"] <= 15

    def test_perfect_bearish_score(self, trending_down_df):
        """Strongly trending down → score near -15."""
        result = mtf_score(trending_down_df)
        assert result["score"] < -10
        assert result["score"] >= -15

    def test_flat_score_near_zero(self, flat_df):
        """Flat market → score near 0."""
        result = mtf_score(flat_df)
        assert -5 <= result["score"] <= 5

    def test_score_range(self, trending_up_df):
        """Score must be in [-15, +15]."""
        result = mtf_score(trending_up_df)
        assert -15 <= result["score"] <= 15

    def test_return_shape(self, trending_up_df):
        """Returns dict with score, po_value, in_compression, is_a_plus."""
        result = mtf_score(trending_up_df)
        assert "score" in result
        assert "po_value" in result
        assert "in_compression" in result
        assert "is_a_plus" in result

    def test_a_plus_requires_15_and_compression(self, trending_up_df):
        """A+ = |score| == 15 AND compression active."""
        result = mtf_score(trending_up_df)
        if abs(result["score"]) == 15 and result["in_compression"]:
            assert result["is_a_plus"] is True
        else:
            assert result["is_a_plus"] is False

    def test_score_components(self, trending_up_df):
        """Score = 10 cross comparisons + 5 trend directions."""
        result = mtf_score(trending_up_df)
        assert "cross_score" in result  # 10 pairwise EMA comparisons
        assert "trend_score" in result  # 5 EMA trend directions
        assert result["score"] == result["cross_score"] + result["trend_score"]
        assert -10 <= result["cross_score"] <= 10
        assert -5 <= result["trend_score"] <= 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/satyland/test_mtf_score.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.indicators.satyland.mtf_score'`

- [ ] **Step 3: Implement mtf_score.py**

```python
# api/indicators/satyland/mtf_score.py
"""
MTF Score Dashboard — Python port of Pine Script v6.

Calculates a score from -15 to +15 per timeframe based on:
- 10 EMA cross comparisons (pairwise: 8, 13, 21, 48, 200)
- 5 EMA trend directions (each EMA vs previous bar)

A+ = |score| == 15 AND compression active.

See: docs/superpowers/specs/2026-04-12-trading-companion-design.md Section 7
"""

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator


_EMA_PERIODS = (8, 13, 21, 48, 200)

# All 10 pairwise combinations: (8,13), (8,21), (8,48), (8,200),
# (13,21), (13,48), (13,200), (21,48), (21,200), (48,200)
_PAIRS = [
    (a, b)
    for i, a in enumerate(_EMA_PERIODS)
    for b in _EMA_PERIODS[i + 1 :]
]


def mtf_score(df: pd.DataFrame) -> dict:
    """
    Calculate the MTF EMA score for a single timeframe.

    Args:
        df: OHLCV DataFrame with at least 200 bars.

    Returns:
        {
            "score": int,           # -15 to +15
            "cross_score": int,     # -10 to +10 (pairwise EMA comparisons)
            "trend_score": int,     # -5 to +5 (EMA trend directions)
            "po_value": float,      # Phase oscillator value
            "in_compression": bool, # Compression tracker state
            "is_a_plus": bool,      # |score| == 15 AND compression
        }
    """
    close = df["close"]

    # Calculate EMAs
    emas = {}
    for period in _EMA_PERIODS:
        emas[period] = close.ewm(span=period, adjust=False).mean()

    # 10 cross comparisons
    cross_score = 0
    for a, b in _PAIRS:
        curr_a = float(emas[a].iloc[-1])
        curr_b = float(emas[b].iloc[-1])
        if curr_a > curr_b:
            cross_score += 1
        elif curr_a < curr_b:
            cross_score -= 1

    # 5 trend directions
    trend_score = 0
    for period in _EMA_PERIODS:
        curr = float(emas[period].iloc[-1])
        prev = float(emas[period].iloc[-2])
        if curr > prev:
            trend_score += 1
        elif curr < prev:
            trend_score -= 1

    score = cross_score + trend_score

    # Phase oscillator + compression from existing module
    po = phase_oscillator(df)
    po_value = po["oscillator"]
    in_compression = po["in_compression"]

    is_a_plus = abs(score) == 15 and in_compression

    return {
        "score": score,
        "cross_score": cross_score,
        "trend_score": trend_score,
        "po_value": round(po_value, 2),
        "in_compression": in_compression,
        "is_a_plus": is_a_plus,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/pytest tests/satyland/test_mtf_score.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/mtf_score.py tests/satyland/test_mtf_score.py
git commit -m "feat: add MTF Score module (-15 to +15 EMA scoring)"
```

---

### Task 1.3: MTF Score Aggregation + Endpoint

**Files:**
- Modify: `api/indicators/satyland/mtf_score.py`
- Modify: `api/endpoints/satyland.py`
- Test: `tests/satyland/test_mtf_score.py`
- Test: `tests/satyland/test_endpoints.py`

- [ ] **Step 1: Write failing test for aggregation function**

```python
# tests/satyland/test_mtf_score.py — append

class TestMTFScoreAggregation:
    """Aggregates scores across timeframes with alignment analysis."""

    def test_aggregate_all_bullish(self, trending_up_df):
        scores = {
            "3m": mtf_score(trending_up_df),
            "10m": mtf_score(trending_up_df),
            "1h": mtf_score(trending_up_df),
        }
        from api.indicators.satyland.mtf_score import aggregate_mtf_scores
        result = aggregate_mtf_scores(scores)
        assert result["alignment"] == "bullish"
        assert result["min_score"] > 0
        assert result["conviction"] in ("maximum", "strong", "moderate", "weak", "chopzilla")

    def test_aggregate_conflict(self, trending_up_df, trending_down_df):
        scores = {
            "3m": mtf_score(trending_up_df),
            "10m": mtf_score(trending_down_df),
        }
        from api.indicators.satyland.mtf_score import aggregate_mtf_scores
        result = aggregate_mtf_scores(scores)
        assert result["alignment"] == "conflict"

    def test_conviction_thresholds(self):
        from api.indicators.satyland.mtf_score import _score_to_conviction
        assert _score_to_conviction(15) == "maximum"
        assert _score_to_conviction(12) == "strong"
        assert _score_to_conviction(8) == "moderate"
        assert _score_to_conviction(5) == "weak"
        assert _score_to_conviction(2) == "chopzilla"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/satyland/test_mtf_score.py::TestMTFScoreAggregation -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_mtf_scores'`

- [ ] **Step 3: Implement aggregation**

Add to `api/indicators/satyland/mtf_score.py`:

```python
def _score_to_conviction(abs_score: int) -> str:
    """Map absolute score to conviction level per spec thresholds."""
    if abs_score >= 13:
        return "maximum"
    elif abs_score >= 10:
        return "strong"
    elif abs_score >= 7:
        return "moderate"
    elif abs_score >= 4:
        return "weak"
    return "chopzilla"


def aggregate_mtf_scores(scores: dict[str, dict]) -> dict:
    """
    Aggregate MTF scores across timeframes.

    Args:
        scores: {"3m": mtf_score_result, "10m": ..., "1h": ...}

    Returns:
        {
            "3m": {"score": 13, "po": 42.3, "compression": false},
            ...,
            "alignment": "bullish" | "bearish" | "conflict",
            "min_score": 11,
            "conviction": "strong",
        }
    """
    result = {}
    score_values = []

    for tf, data in scores.items():
        result[tf] = {
            "score": data["score"],
            "po": data["po_value"],
            "compression": data["in_compression"],
        }
        score_values.append(data["score"])

    # Alignment: all same sign?
    all_positive = all(s > 0 for s in score_values)
    all_negative = all(s < 0 for s in score_values)

    # min_score is always stored as absolute value (weakest link)
    if all_positive:
        result["alignment"] = "bullish"
        result["min_score"] = min(score_values)  # smallest positive = weakest
    elif all_negative:
        result["alignment"] = "bearish"
        result["min_score"] = min(abs(s) for s in score_values)  # closest to 0 = weakest
    else:
        result["alignment"] = "conflict"
        result["min_score"] = min(abs(s) for s in score_values)

    result["conviction"] = _score_to_conviction(result["min_score"])
    return result
```

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/satyland/test_mtf_score.py -v`
Expected: ALL PASS

- [ ] **Step 5: Add `/api/satyland/mtf-score` endpoint**

Add request model and endpoint to `api/endpoints/satyland.py`:

```python
# Request model (add near other models ~line 114)
class MTFScoreRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    timeframes: list[str] = Field(
        default=["3", "10", "60"],
        description="List of timeframe intervals (minutes or 'd'/'w')",
    )

# Endpoint (add after /premarket endpoint ~line 551)
@router.post("/mtf-score")
async def mtf_score_endpoint(req: MTFScoreRequest):
    """Calculate MTF Score across multiple timeframes."""
    from api.indicators.satyland.mtf_score import mtf_score, aggregate_mtf_scores

    scores = {}
    for tf in req.timeframes:
        tf_key = f"{tf}m" if tf.isdigit() else tf
        try:
            df = await asyncio.to_thread(_fetch_intraday, req.ticker, tf)
            scores[tf_key] = mtf_score(df)
        except Exception as e:
            scores[tf_key] = {"error": str(e)}

    result = aggregate_mtf_scores(
        {k: v for k, v in scores.items() if "error" not in v}
    )
    # Merge per-TF results back
    for tf_key in scores:
        if "error" not in scores[tf_key]:
            result[tf_key] = {**result.get(tf_key, {}), **scores[tf_key]}
        else:
            result[tf_key] = scores[tf_key]

    return JSONResponse(
        content={"ticker": req.ticker, "mtf_scores": result},
        headers={"Cache-Control": "s-maxage=30, stale-while-revalidate=60"},
    )
```

- [ ] **Step 6: Run all tests**

Run: `venv/bin/pytest tests/satyland/ -v`
Expected: ALL PASS (existing + new)

- [ ] **Step 7: Commit**

```bash
git add api/indicators/satyland/mtf_score.py api/endpoints/satyland.py tests/satyland/test_mtf_score.py
git commit -m "feat: add MTF Score aggregation and /api/satyland/mtf-score endpoint"
```

---

## Phase 2: Green Flag Rework

### Task 2.1: Setup Grader Architecture

**Files:**
- Create: `api/indicators/satyland/setup_grader.py`
- Create: `api/indicators/satyland/setups/__init__.py`
- Create: `api/indicators/satyland/setups/base.py`
- Create: `tests/satyland/test_setup_grader.py`

- [ ] **Step 1: Write failing tests for the grader interface**

```python
# tests/satyland/test_setup_grader.py

from api.indicators.satyland.setup_grader import grade_setup


class TestSetupGrader:
    """Setup-aware grading: required + bonus flags → grade + reasoning."""

    def test_returns_required_keys(self):
        result = grade_setup(
            setup_type="flag_into_ribbon",
            direction="bullish",
            atr={}, ribbon={}, phase={}, structure={},
            mtf_scores={},
        )
        assert "grade" in result
        assert "score" in result
        assert "required_flags" in result
        assert "bonus_flags" in result
        assert "reasoning" in result
        assert "probability" in result

    def test_missing_required_flag_forces_skip(self):
        """If any required flag is False → grade = skip."""
        result = grade_setup(
            setup_type="flag_into_ribbon",
            direction="bullish",
            atr={"atr_covered_pct": 90.0, "atr_room_ok": False},  # >70%
            ribbon={"ribbon_state": "bullish"},
            phase={"phase": "green"},
            structure={},
            mtf_scores={},
        )
        assert result["grade"] == "skip"

    def test_unknown_setup_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown setup"):
            grade_setup(
                setup_type="nonexistent",
                direction="bullish",
                atr={}, ribbon={}, phase={}, structure={},
                mtf_scores={},
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/satyland/test_setup_grader.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement setup_grader.py and base.py**

```python
# api/indicators/satyland/setups/base.py
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
```

```python
# api/indicators/satyland/setups/__init__.py
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
```

```python
# api/indicators/satyland/setup_grader.py
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
```

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/satyland/test_setup_grader.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/setup_grader.py api/indicators/satyland/setups/
git add tests/satyland/test_setup_grader.py
git commit -m "feat: add setup-aware grading architecture with required/bonus flags"
```

---

### Task 2.2: Flag Into Ribbon Setup

**Files:**
- Create: `api/indicators/satyland/setups/flag_into_ribbon.py`
- Create: `tests/satyland/test_setups/__init__.py`
- Create: `tests/satyland/test_setups/test_flag_into_ribbon.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/satyland/test_setups/test_flag_into_ribbon.py

from api.indicators.satyland.setup_grader import grade_setup


class TestFlagIntoRibbon:
    """Flag Into Ribbon: trending pullback to 13/21 EMA."""

    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 50.0, "atr_room_ok": True},
            "ribbon": {
                "ribbon_state": "bullish", "bias_candle": "blue",
                "ema13": 560.0, "ema21": 559.0, "ema48": 555.0,
                "above_48ema": True, "in_compression": False,
            },
            "phase": {"phase": "green", "oscillator": 45.0},
            "structure": {"price_above_pdh": True, "price_above_pmh": True},
            "mtf_scores": {
                "alignment": "bullish", "min_score": 12, "conviction": "strong",
                "3m": {"score": 13}, "10m": {"score": 12}, "1h": {"score": 14},
            },
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="flag_into_ribbon", direction="bullish", **inputs)
        assert result["grade"] in ("A+", "A")
        assert all(f["passed"] for f in result["required_flags"])

    def test_ribbon_not_stacked_skips(self):
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "chopzilla", "bias_candle": "gray",
            "ema13": 560.0, "ema21": 559.0, "ema48": 555.0,
            "above_48ema": True, "in_compression": False,
        })
        result = grade_setup(setup_type="flag_into_ribbon", direction="bullish", **inputs)
        assert result["grade"] == "skip"

    def test_atr_room_exceeded_skips(self):
        inputs = self._make_inputs(atr={"atr_covered_pct": 80.0, "atr_room_ok": False})
        result = grade_setup(setup_type="flag_into_ribbon", direction="bullish", **inputs)
        assert result["grade"] == "skip"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/satyland/test_setups/test_flag_into_ribbon.py -v`
Expected: FAIL — `ValueError: Unknown setup: flag_into_ribbon`

- [ ] **Step 3: Implement flag_into_ribbon.py**

```python
# api/indicators/satyland/setups/flag_into_ribbon.py
"""
Flag Into Ribbon (Classic Trend Continuation).

Required: ribbon stacked, price at 13/21 EMA, ATR room < 70%.
Bonus: phase firing, MTF aligned, structure confirmed, VIX, confluence.
"""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator


class FlagIntoRibbonEvaluator(SetupEvaluator):
    name = "flag_into_ribbon"

    def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        target_state = "bullish" if is_bull else "bearish"
        target_candle = "blue" if is_bull else "orange"

        flags = []

        # 1. Ribbon stacked and fanning
        stacked = ribbon.get("ribbon_state") == target_state
        flags.append((
            "ribbon_stacked",
            stacked,
            f"Ribbon {ribbon.get('ribbon_state', 'unknown')} (need {target_state})",
        ))

        # 2. Price at 13/21 EMA pullback (blue/orange candle)
        candle = ribbon.get("bias_candle", "")
        at_pullback = candle == target_candle
        flags.append((
            "price_at_ema_pullback",
            at_pullback,
            f"Bias candle: {candle} (need {target_candle} for pullback)",
        ))

        # 3. ATR room < 70%
        room_ok = atr.get("atr_room_ok", False)
        pct = atr.get("atr_covered_pct", 0)
        flags.append((
            "atr_room",
            room_ok,
            f"ATR {pct:.0f}% consumed {'< 70%' if room_ok else '>= 70%'}",
        ))

        return flags

    def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        flags = []

        # 1. Phase oscillator firing in direction
        target_phase = "green" if is_bull else "red"
        phase_ok = phase.get("phase") == target_phase
        flags.append((
            "phase_firing",
            phase_ok,
            f"Phase: {phase.get('phase', 'unknown')} (need {target_phase})",
        ))

        # 2. MTF alignment (all TFs same sign, min score >= 10)
        alignment = mtf_scores.get("alignment", "conflict")
        target_align = "bullish" if is_bull else "bearish"
        min_score = abs(mtf_scores.get("min_score", 0))
        mtf_ok = alignment == target_align and min_score >= 10
        flags.append((
            "mtf_aligned",
            mtf_ok,
            f"MTF {alignment}, min score ±{min_score} (need {target_align} ≥ ±10)",
        ))

        # 3. Structure confirmed
        if is_bull:
            struct_ok = structure.get("price_above_pdh", False) or structure.get("price_above_pmh", False)
        else:
            struct_ok = structure.get("price_below_pdl", False) or structure.get("price_below_pml", False)
        flags.append((
            "structure_confirmed",
            struct_ok,
            "Above PDH/PMH" if is_bull and struct_ok else "Below PDL/PML" if struct_ok else "Structure not confirmed",
        ))

        # 4. VIX bias
        vix = kw.get("vix")
        if vix is not None:
            vix_ok = (is_bull and vix < 17) or (not is_bull and vix > 20)
        else:
            vix_ok = False
        flags.append((
            "vix_bias",
            vix_ok,
            f"VIX: {vix}" if vix else "VIX: unavailable",
        ))

        # 5. Confluence
        confluence = False  # Simplified — check if ATR level near structure level
        flags.append((
            "confluence",
            confluence,
            "ATR/structure confluence check",
        ))

        return flags


register("flag_into_ribbon", FlagIntoRibbonEvaluator())
```

Add import to `api/indicators/satyland/setups/__init__.py` (bottom of file):
```python
# Import all setups to trigger registration
import api.indicators.satyland.setups.flag_into_ribbon  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/satyland/test_setups/test_flag_into_ribbon.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/setups/ tests/satyland/test_setups/
git commit -m "feat: add Flag Into Ribbon setup evaluator"
```

---

### Task 2.3: Golden Gate Setup (Bilbo-Enhanced)

**Files:**
- Create: `api/indicators/satyland/setups/golden_gate.py`
- Create: `tests/satyland/test_setups/test_golden_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/satyland/test_setups/test_golden_gate.py

from api.indicators.satyland.setup_grader import grade_setup


class TestGoldenGate:
    """Golden Gate with Bilbo filter and Milkman probability data."""

    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {
                "atr_covered_pct": 40.0, "atr_room_ok": True,
                "call_trigger": 561.0, "put_trigger": 557.0,
                "current_price": 563.5,
                "levels": {"golden_gate_bull": {"price": 563.0, "pct": "+38.2%", "fib": 0.382}},
            },
            "ribbon": {"ribbon_state": "bullish"},
            "phase": {
                "phase": "green", "oscillator": 55.0,
                "zone": "high", "direction": "rising",
                "zone_state": "high_rising",
            },
            "structure": {"price_above_pdh": True, "price_above_pmh": True},
            "mtf_scores": {
                "alignment": "bullish", "min_score": 13,
                "3m": {"score": 13}, "10m": {"score": 14}, "1h": {"score": 13},
            },
        }
        defaults.update(overrides)
        return defaults

    def test_bilbo_confirmed_auto_a_plus(self):
        """60m PO High+Rising → auto A+ for bullish GG."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="golden_gate", direction="bullish",
            phase_60m={"zone_state": "high_rising", "oscillator": 55.0},
            **inputs,
        )
        assert result["grade"] == "A+"
        assert result["probability"] >= 0.77  # Bilbo bullish = 77.7%
        assert result["probability_source"] == "backtested"

    def test_counter_trend_po_skips(self):
        """60m PO Mid+Falling (counter-trend for bull) → required flag fails."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="golden_gate", direction="bullish",
            phase_60m={"zone_state": "mid_falling", "oscillator": -5.0},
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_bearish_bilbo_90_percent(self):
        """Bearish GG + PO Low+Falling → 90.2% backtested."""
        inputs = self._make_inputs(
            atr={
                "atr_covered_pct": 30.0, "atr_room_ok": True,
                "put_trigger": 557.0, "call_trigger": 561.0,
                "current_price": 555.0,
            },
            phase={"phase": "red", "oscillator": -55.0,
                   "zone": "low", "direction": "falling", "zone_state": "low_falling"},
            ribbon={"ribbon_state": "bearish"},
            structure={"price_below_pdl": True},
        )
        result = grade_setup(
            setup_type="golden_gate", direction="bearish",
            phase_60m={"zone_state": "low_falling", "oscillator": -55.0},
            **inputs,
        )
        assert result["grade"] == "A+"
        assert result["probability"] >= 0.90

    def test_reasoning_includes_milkman_data(self):
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="golden_gate", direction="bullish",
            phase_60m={"zone_state": "high_rising", "oscillator": 55.0},
            **inputs,
        )
        assert "77" in result["reasoning"] or "78" in result["reasoning"]
        assert "backtested" in result["reasoning"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/satyland/test_setups/test_golden_gate.py -v`
Expected: FAIL — `ValueError: Unknown setup: golden_gate`

- [ ] **Step 3: Implement golden_gate.py**

```python
# api/indicators/satyland/setups/golden_gate.py
"""
Golden Gate Strategy with Bilbo filter.

Uses backtested probability data from milkmantrades.com (6,466 SPY days).
60m Phase Oscillator zone_state is the primary probability driver.

See: docs/superpowers/specs/2026-04-12-trading-companion-design.md Section 5
"""

from typing import Any

from api.indicators.satyland.setups import register
from api.indicators.satyland.setups.base import SetupEvaluator

# Backtested completion rates from milkmantrades.com
BILBO_PROBABILITIES = {
    "bullish": {
        "high_rising": 0.777,
        "high_falling": 0.776,
        "mid_rising": 0.633,
        "mid_falling": 0.515,
    },
    "bearish": {
        "low_falling": 0.902,
        "low_rising": 0.885,
        "mid_falling": 0.640,
        "mid_rising": 0.542,
    },
}

BASELINE_PROBABILITY = {"bullish": 0.630, "bearish": 0.650}

# Counter-trend zone_states (should be required=False → skip)
COUNTER_TREND = {
    "bullish": {"mid_falling", "low_falling", "low_rising"},
    "bearish": {"mid_rising", "high_rising", "high_falling"},
}


class GoldenGateEvaluator(SetupEvaluator):
    name = "golden_gate"
    BACKTESTED = True

    def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        flags = []

        # 1. Price broke through ±38.2% (implied by webhook trigger, check current price)
        current = atr.get("current_price", 0)
        if is_bull:
            gg_level = atr.get("levels", {}).get("golden_gate_bull", {}).get("price", 0)
            broke_through = current >= gg_level if gg_level else True  # trust webhook
        else:
            gg_level = atr.get("levels", {}).get("golden_gate_bear", {}).get("price", 0)
            broke_through = current <= gg_level if gg_level else True
        flags.append(("price_through_38.2", broke_through, f"Price at {current}, GG at {gg_level}"))

        # 2. 60m PO not counter-trend
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "mid_rising")
        is_counter = zone_state in COUNTER_TREND.get(direction, set())
        flags.append((
            "po_60m_not_counter",
            not is_counter,
            f"60m PO: {zone_state} ({'counter-trend — SKIP' if is_counter else 'aligned'})",
        ))

        # 3. ATR room
        room_ok = atr.get("atr_room_ok", False)
        pct = atr.get("atr_covered_pct", 0)
        flags.append(("atr_room", room_ok, f"ATR {pct:.0f}% consumed"))

        return flags

    def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        is_bull = direction == "bullish"
        flags = []

        # 1. Bilbo confirmed
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "")
        bilbo_states = {"high_rising", "high_falling"} if is_bull else {"low_falling", "low_rising"}
        bilbo_ok = zone_state in bilbo_states
        flags.append(("bilbo_confirmed", bilbo_ok, f"60m PO: {zone_state}"))

        # 2. Trigger level holding
        current = atr.get("current_price", 0)
        if is_bull:
            trigger = atr.get("call_trigger", 0)
            holding = current >= trigger if trigger else False
        else:
            trigger = atr.get("put_trigger", 0)
            holding = current <= trigger if trigger else False
        flags.append(("trigger_holding", holding, f"Trigger at {trigger}, price at {current}"))

        # 3. Time of day (before 11am EST)
        time_est = kw.get("time_est")
        if time_est:
            hour = int(time_est.split(":")[0])
            early = hour < 11
        else:
            early = False
        flags.append(("early_session", early, f"Time: {time_est or 'unknown'} EST"))

        # 4. MTF alignment
        alignment = mtf_scores.get("alignment", "conflict")
        target = "bullish" if is_bull else "bearish"
        mtf_ok = alignment == target
        flags.append(("mtf_aligned", mtf_ok, f"MTF: {alignment}"))

        # 5. Structure confirmed
        if is_bull:
            struct_ok = structure.get("price_above_pdh", False) or structure.get("price_above_pmh", False)
        else:
            struct_ok = structure.get("price_below_pdl", False) or structure.get("price_below_pml", False)
        flags.append(("structure_confirmed", struct_ok, "Structure aligned" if struct_ok else "Not confirmed"))

        return flags

    def get_modifiers(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
        modifiers = []
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "")
        is_bull = direction == "bullish"

        # Bilbo → auto A+
        bilbo_states = {"high_rising", "high_falling"} if is_bull else {"low_falling", "low_rising"}
        if zone_state in bilbo_states:
            prob = BILBO_PROBABILITIES.get(direction, {}).get(zone_state, 0)
            modifiers.append(("bilbo_upgrade", +3, f"Bilbo confirmed ({prob:.0%} backtested) → A+"))

        # Time of day penalty (after 1pm EST for GG)
        time_est = kw.get("time_est")
        if time_est:
            hour = int(time_est.split(":")[0])
            if hour >= 13:
                modifiers.append(("late_session", -1, f"After 1pm EST ({time_est}) — lower completion rate"))

        return modifiers

    def get_probability(self, direction, phase, **kw):
        phase_60m = kw.get("phase_60m", {})
        zone_state = phase_60m.get("zone_state", "mid_rising")
        probs = BILBO_PROBABILITIES.get(direction, {})
        return probs.get(zone_state, BASELINE_PROBABILITY.get(direction, 0.63))


register("golden_gate", GoldenGateEvaluator())
```

Add import to `__init__.py`:
```python
import api.indicators.satyland.setups.golden_gate  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/satyland/test_setups/test_golden_gate.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/setups/golden_gate.py tests/satyland/test_setups/test_golden_gate.py
git add api/indicators/satyland/setups/__init__.py
git commit -m "feat: add Golden Gate setup evaluator with Bilbo filter and backtested probabilities"
```

---

### Task 2.4: Remaining 6 Setup Evaluators

**Files:**
- Create: `api/indicators/satyland/setups/vomy.py`
- Create: `api/indicators/satyland/setups/orb.py`
- Create: `api/indicators/satyland/setups/squeeze.py`
- Create: `api/indicators/satyland/setups/divergence.py`
- Create: `api/indicators/satyland/setups/eod_divergence.py`
- Create: `api/indicators/satyland/setups/wicky_wicky.py`
- Create: `tests/satyland/test_setups/test_vomy.py` (and one per setup)

Each setup follows the same pattern as Task 2.2 (FlagIntoRibbon) — implement `SetupEvaluator` subclass with `evaluate_required()` and `evaluate_bonus()` per the spec's Section 5.

- [ ] **Step 1: Implement all 6 evaluators** following the required/bonus flags defined in the spec for each setup (Vomy/iVomy, ORB, Squeeze, Divergence, EOD Divergence, Wicky Wicky). Use the flag definitions from spec Section 5 verbatim.

- [ ] **Step 2: Write tests for each** — minimum: test all-flags-pass, test required-flag-fails → skip, test direction inversion for Vomy.

- [ ] **Step 3: Register all in `__init__.py`**

- [ ] **Step 4: Run all tests**

Run: `venv/bin/pytest tests/satyland/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/indicators/satyland/setups/ tests/satyland/test_setups/
git commit -m "feat: add remaining 6 setup evaluators (vomy, orb, squeeze, divergence, eod, wicky)"
```

---

### Task 2.5: Wire Setup Grader into /trade-plan Endpoint

**Files:**
- Modify: `api/endpoints/satyland.py:345-425`
- Modify: `api/indicators/satyland/green_flag.py`
- Test: `tests/satyland/test_endpoints.py`

- [ ] **Step 1: Update `/trade-plan` to accept `setup_type` parameter and use new grader**

Add `setup_type: str | None = None` to `TradePlanRequest`. When provided, use `grade_setup()` from `setup_grader.py` instead of `green_flag_checklist()`. When not provided, fall back to existing generic grading for backward compatibility.

- [ ] **Step 2: Add deprecation notice to `green_flag.py`**

Add docstring note: `"""DEPRECATED: Use setup_grader.grade_setup() for setup-aware grading."""`

- [ ] **Step 3: Test both paths**

Run: `venv/bin/pytest tests/satyland/test_endpoints.py -v`
Expected: ALL PASS (existing generic path still works, new setup_type path works)

- [ ] **Step 4: Commit**

```bash
git add api/endpoints/satyland.py api/indicators/satyland/green_flag.py tests/satyland/test_endpoints.py
git commit -m "feat: wire setup grader into /trade-plan endpoint with backward compatibility"
```

---

## Phase 3: Supabase Tables

### Task 3.1: Supabase Client Setup

**Files:**
- Create: `api/integrations/supabase_client.py`

- [ ] **Step 1: Create Supabase client module**

```python
# api/integrations/supabase_client.py
"""Supabase client initialization."""

import os
from functools import lru_cache

from supabase import create_client, Client


@lru_cache
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)
```

- [ ] **Step 2: Add env vars to `.env.example`**

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

- [ ] **Step 3: Commit**

```bash
git add api/integrations/supabase_client.py
git commit -m "feat: add Supabase client initialization"
```

---

### Task 3.2: Create Supabase Tables

**Files:**
- Create: `scripts/create_supabase_tables.sql`

- [ ] **Step 1: Write SQL migration**

Create the 6 tables defined in spec Section 2 (daily_plans, trades, journal_entries, alerts, notes, weekly_reviews) with all columns, types, FKs, and indexes. Include `updated_at` trigger for auto-updating timestamps.

- [ ] **Step 2: Run migration against Supabase**

Use Supabase MCP `execute_sql` tool or Supabase dashboard SQL editor.

- [ ] **Step 3: Verify tables exist**

- [ ] **Step 4: Commit**

```bash
git add scripts/create_supabase_tables.sql
git commit -m "feat: add Supabase table definitions for trading companion"
```

---

## Phase 4: TradingView Webhook Endpoint

### Task 4.1: Webhook Receiver

**Files:**
- Create: `api/endpoints/webhooks.py`
- Modify: `api/main.py`
- Create: `tests/satyland/test_webhooks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/satyland/test_webhooks.py

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from api.main import app


@pytest.mark.asyncio
class TestTradingViewWebhook:

    async def test_missing_token_returns_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/webhooks/tradingview", json={
                "ticker": "SPY", "timeframe": "3", "setup": "flag_into_ribbon",
                "direction": "long", "price": 562.0, "alert": "test",
            })
            assert resp.status_code == 401

    async def test_valid_webhook_returns_200(self):
        with patch.dict("os.environ", {"TRADINGVIEW_WEBHOOK_SECRET": "test123"}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=test123",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "flag_into_ribbon", "direction": "long",
                        "price": 562.0, "alert": "test",
                    },
                )
                assert resp.status_code == 200

    async def test_invalid_setup_returns_400(self):
        with patch.dict("os.environ", {"TRADINGVIEW_WEBHOOK_SECRET": "test123"}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=test123",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "invalid_setup", "direction": "long",
                        "price": 562.0, "alert": "test",
                    },
                )
                assert resp.status_code == 400
```

- [ ] **Step 2: Implement webhook endpoint**

```python
# api/endpoints/webhooks.py
"""TradingView webhook receiver — grades setups and posts to Slack."""

import os
import asyncio
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class TradingViewPayload(BaseModel):
    ticker: str
    timeframe: str
    setup: str
    direction: str
    price: float
    alert: str = ""


@router.post("/tradingview")
async def tradingview_webhook(
    payload: TradingViewPayload,
    token: str = Query(..., description="Webhook secret token"),
):
    """Receive TradingView alert, grade setup, post to Slack, save to Supabase."""
    secret = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET", "")
    if token != secret:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Validate setup type
    from api.indicators.satyland.setups import registered_setups
    if payload.setup not in registered_setups():
        raise HTTPException(status_code=400, detail=f"Unknown setup: {payload.setup}")

    # TODO Phase 5: Fetch indicators, grade, post to Slack, save to Supabase
    return {"status": "received", "setup": payload.setup, "grade": "pending"}
```

- [ ] **Step 3: Register router in main.py**

Add `from api.endpoints import webhooks` and `app.include_router(webhooks.router)`.

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/satyland/test_webhooks.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add api/endpoints/webhooks.py api/main.py tests/satyland/test_webhooks.py
git commit -m "feat: add TradingView webhook endpoint with token auth"
```

---

### Task 4.2: Webhook Grading Pipeline

**Files:**
- Modify: `api/endpoints/webhooks.py`

- [ ] **Step 1: Refactor shared data fetch functions**

Extract `_fetch_intraday`, `_fetch_daily`, `_fetch_premarket`, `_normalise_columns` from `api/endpoints/satyland.py` into `api/utils/data_fetch.py` so both `satyland.py` and `webhooks.py` can import them. Update imports in `satyland.py`.

- [ ] **Step 2: Implement persist-first pattern**

On webhook receipt, immediately save the raw payload to `alerts` table in Supabase with `grade="pending"`. This ensures no alerts are lost even if grading crashes. Then grade asynchronously.

- [ ] **Step 3: Implement full grading pipeline**

Wire up: fetch indicators via shared data functions → compute MTF scores → run `grade_setup()` → update alert record with grade → format Slack message → send to Slack.

- [ ] **Step 4: Implement deduplication**

Before posting to Slack, check `alerts` table for same ticker + same setup_type + same direction within last 5 minutes. If found, group into one message showing both timeframes. Cross-direction or cross-setup alerts are NEVER deduplicated — always surfaced separately.

- [ ] **Step 5: Implement conflict filtering**

If MTF scores show 1h is bearish but 3m bullish setup fires (or vice versa), add conflict warning to the Slack message and downgrade the grade by one level.

- [ ] **Step 6: Test full pipeline with mock data**

- [ ] **Step 7: Commit**

```bash
git add api/endpoints/webhooks.py api/utils/data_fetch.py api/endpoints/satyland.py
git commit -m "feat: wire full grading pipeline with persist-first, dedup, and conflict filtering"
```

---

## Phase 5: Slack Integration + Scheduled Tasks

### Task 5.1: Slack Message Formatter + Sender

**Files:**
- Create: `api/integrations/slack.py`

- [ ] **Step 1: Implement Slack client**

Use the `slack_sdk` Python library (NOT Slack MCP tools — those are for Claude CLI/Desktop, not a deployed FastAPI server). Install via `pip install slack_sdk`. Create formatting functions for each message type: morning brief, setup alert, ORB marker, trend time, euro close, midday nudge, journal prompt, next-day prep. Requires `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` env vars.

- [ ] **Step 2: Test formatting functions** (unit tests on message formatting, mock Slack sends)

- [ ] **Step 3: Commit**

```bash
git add api/integrations/slack.py tests/satyland/test_slack.py
git commit -m "feat: add Slack message formatter and sender"
```

---

### Task 5.2: Scheduled Tasks

**Files:**
- Create: `api/endpoints/scheduled.py`

- [ ] **Step 1: Create scheduled task endpoints**

One endpoint per scheduled touchpoint. Each can be triggered by Railway cron or Supabase pg_cron:
- `POST /api/scheduled/morning-brief` (5:30am PST)
- `POST /api/scheduled/orb-marker` (6:40am PST)
- `POST /api/scheduled/trend-time` (7:00am PST)
- `POST /api/scheduled/euro-close` (8:20am PST)
- `POST /api/scheduled/midday-nudge` (9:30am PST)
- `POST /api/scheduled/journal-prompt` (1:00pm PST)
- `POST /api/scheduled/next-day-prep` (5:00pm PST)
- `POST /api/scheduled/weekly-review` (Friday 1:00pm PST)

- [ ] **Step 2: Register router, test endpoints**

- [ ] **Step 3: Configure cron triggers** (Railway or Supabase pg_cron)

- [ ] **Step 4: Commit**

```bash
git add api/endpoints/scheduled.py api/main.py
git commit -m "feat: add scheduled task endpoints for daily trading touchpoints"
```

---

## Phase 6: Trade Logging + Journal + Notes

### Task 6.1: Trade CRUD Endpoints

**Files:**
- Create: `api/endpoints/trades.py`
- Create: `tests/satyland/test_trades.py`

- [ ] **Step 1: Implement trade endpoints**

- `POST /api/trades` — create trade (validates 6-point checklist, operator rules)
- `PATCH /api/trades/{id}` — update trade (exit, status change)
- `GET /api/trades?date=YYYY-MM-DD` — list trades for a day
- `GET /api/trades/{id}` — get single trade

- [ ] **Step 2: Implement alert-to-trade flow** — `POST /api/trades/from-alert/{alert_id}` pre-fills from alert data

- [ ] **Step 3: Test all endpoints**

- [ ] **Step 4: Commit**

```bash
git add api/endpoints/trades.py tests/satyland/test_trades.py api/main.py
git commit -m "feat: add trade CRUD endpoints with 6-point checklist validation"
```

---

### Task 6.2: Journal + Notes Endpoints

**Files:**
- Create: `api/endpoints/journal.py`

- [ ] **Step 1: Implement journal endpoints**

- `POST /api/journal` — create journal entry
- `GET /api/journal?date=YYYY-MM-DD` — get journal for a day
- `POST /api/notes` — create mid-session note (auto-tagged by category)
- `GET /api/notes?date=YYYY-MM-DD` — list notes for a day

- [ ] **Step 2: Test endpoints**

- [ ] **Step 3: Commit**

```bash
git add api/endpoints/journal.py api/main.py
git commit -m "feat: add journal and notes endpoints"
```

---

## Phase 7: Analytics

### Task 7.1: Analytics Query Endpoints

**Files:**
- Create: `api/endpoints/analytics.py`

- [ ] **Step 1: Implement analytics endpoints**

- `GET /api/analytics/daily?date=YYYY-MM-DD` — daily summary
- `GET /api/analytics/weekly?week=YYYY-Wnn` — weekly review
- `GET /api/analytics/setup-performance?setup=flag_into_ribbon&period=30d` — per-setup stats
- `GET /api/analytics/win-rates` — current win rates per setup (for self-correcting probabilities)

- [ ] **Step 2: Implement weekly review auto-generation** — query trades + journal for the week, compute stats, save to `weekly_reviews` table

- [ ] **Step 3: Test analytics queries**

- [ ] **Step 4: Commit**

```bash
git add api/endpoints/analytics.py api/main.py tests/satyland/test_analytics.py
git commit -m "feat: add analytics endpoints with setup performance and win rate tracking"
```

---

## Summary

| Phase | Tasks | Dependencies | Estimated Commits |
|-------|-------|-------------|-------------------|
| 1. MTF Score + PO Zones | 3 tasks | None | 3 |
| 2. Green Flag Rework | 5 tasks | Phase 1 | 5 |
| 3. Supabase Tables | 2 tasks | None (parallel with 1-2) | 2 |
| 4. Webhook Endpoint | 2 tasks | Phases 2 + 3 | 2 |
| 5. Slack + Scheduled | 2 tasks | Phases 3 + 4 | 2 |
| 6. Trade Logging | 2 tasks | Phases 3 + 5 | 2 |
| 7. Analytics | 1 task | Phases 3 + 6 | 1 |
| **Total** | **17 tasks** | | **17 commits** |

**Deferred to a separate plan:**
- Frontend pages (`/journal`, `/analytics`, `/alerts`) — will be brainstormed and planned after backend is working
- Natural language query parsing — will use Claude API to translate questions to Supabase queries
- Monthly review page — computed on-the-fly from `weekly_reviews` table, no dedicated endpoint needed until frontend is built
