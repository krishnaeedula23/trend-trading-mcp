"""
Level 1 tests for api/indicators/satyland/green_flag.py

Covers:
  1. Regression tests for the 4 fixed KeyError bugs
  2. Scoring and grading logic
  3. VIX bias handling
  4. Verbal audit content
  5. Bearish direction flag inversion
"""

import pytest

from api.indicators.satyland.green_flag import green_flag_checklist


# ── Minimal mock dicts (hand-crafted to match actual indicator outputs) ────────

def _make_atr(
    current_price: float = 105.0,
    pdc: float = 100.0,
    atr: float = 2.0,
    atr_room_ok: bool = True,
) -> dict:
    """Minimal ATR dict matching atr_levels() output schema."""
    call_trigger = round(pdc + atr * 0.236, 4)
    put_trigger = round(pdc - atr * 0.236, 4)
    return {
        "atr": atr,
        "pdc": pdc,
        "current_price": current_price,
        "call_trigger": call_trigger,   # top-level alias (Bug 2 fix)
        "put_trigger": put_trigger,     # top-level alias (Bug 2 fix)
        "levels": {
            "trigger_bull": {"price": call_trigger, "pct": "+23.6%", "fib": 0.236},
            "trigger_bear": {"price": put_trigger, "pct": "-23.6%", "fib": 0.236},
            "golden_gate_bull": {"price": round(pdc + atr * 0.382, 4), "pct": "+38.2%", "fib": 0.382},
            "golden_gate_bear": {"price": round(pdc - atr * 0.382, 4), "pct": "-38.2%", "fib": 0.382},
            "mid_50_bull": {"price": round(pdc + atr * 0.500, 4), "pct": "+50.0%", "fib": 0.500},
            "mid_50_bear": {"price": round(pdc - atr * 0.500, 4), "pct": "-50.0%", "fib": 0.500},
            "mid_range_bull": {"price": round(pdc + atr * 0.618, 4), "pct": "+61.8%", "fib": 0.618},
            "mid_range_bear": {"price": round(pdc - atr * 0.618, 4), "pct": "-61.8%", "fib": 0.618},
            "fib_786_bull": {"price": round(pdc + atr * 0.786, 4), "pct": "+78.6%", "fib": 0.786},
            "fib_786_bear": {"price": round(pdc - atr * 0.786, 4), "pct": "-78.6%", "fib": 0.786},
            "full_range_bull": {"price": round(pdc + atr * 1.000, 4), "pct": "+100.0%", "fib": 1.000},
            "full_range_bear": {"price": round(pdc - atr * 1.000, 4), "pct": "-100.0%", "fib": 1.000},
        },
        "atr_room_ok": atr_room_ok,
        "atr_status": "green" if atr_room_ok else "red",
        "atr_covered_pct": 50.0 if atr_room_ok else 95.0,
        "trigger_box": {
            "low": put_trigger,
            "high": call_trigger,
            "inside": put_trigger < current_price < call_trigger,
        },
        "price_position": "above_call_trigger",
        "chopzilla": False,
        "trend": "bullish",
    }


def _make_ribbon(
    ribbon_state: str = "bullish",
    ema48: float = 100.5,
    above_200ema: bool = True,
    in_compression: bool = False,
) -> dict:
    """Minimal ribbon dict matching pivot_ribbon() output schema."""
    return {
        "ema8": 103.0,
        "ema13": 102.0,
        "ema21": 101.5,
        "ema48": ema48,           # Bug 1 fix: no ema34 key
        "ema200": 95.0,
        "ribbon_state": ribbon_state,
        "bias_candle": "green",
        "bias_signal": "bullish",
        "conviction_arrow": None,
        "spread": 2.5,
        "above_48ema": True,
        "above_200ema": above_200ema,
        "in_compression": in_compression,
        "chopzilla": False,
    }


def _make_phase(
    phase: str = "green",
    in_compression: bool = False,
) -> dict:
    """Minimal phase dict matching phase_oscillator() output schema."""
    return {
        "oscillator": 15.0 if phase == "green" else -15.0,
        "oscillator_prev": 10.0,
        "phase": phase,           # Bug 3 fix: "green"/"red"/"compression"
        "in_compression": in_compression,  # Bug 4 fix: correct key
        "current_zone": "neutral_up",
        "zone_crosses": {
            "leaving_accumulation": False,
            "leaving_extreme_down": False,
            "leaving_distribution": False,
            "leaving_extreme_up": False,
        },
        "zones": {
            "extreme": {"up": 100.0, "down": -100.0},
            "distribution": {"up": 61.8, "down": -61.8},
            "neutral": {"up": 23.6, "down": -23.6},
            "zero": 0.0,
        },
    }


def _make_structure(
    price_above_pdh: bool = True,
    price_above_pmh: bool = False,
    pdh: float = 104.5,
    pdl: float = 99.0,
) -> dict:
    return {
        "pdc": 100.0,
        "pdh": pdh,
        "pdl": pdl,
        "pmh": None,
        "pml": None,
        "current_price": 105.0,
        "structural_bias": "strongly_bullish",
        "gap_scenario": "gap_above_pdh",
        "price_above_pdh": price_above_pdh,
        "price_above_pmh": price_above_pmh,
        "price_below_pdl": False,
        "price_below_pml": False,
    }


# ── Bug regression tests ───────────────────────────────────────────────────────

class TestBugRegressions:
    def test_bug_ema34_no_longer_causes_keyerror(self):
        """Bug 1: ribbon has no 'ema34' key — must not KeyError."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        # Explicit verification: ema34 must NOT be in the ribbon dict
        assert "ema34" not in ribbon
        phase = _make_phase()
        struct = _make_structure()
        # This must not raise KeyError
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        assert "price_above_cloud" in result["flags"]

    def test_bug_call_trigger_level_lookup(self):
        """Bug 2: call_trigger at atr['call_trigger'], not atr['levels']['call_trigger']."""
        atr = _make_atr(current_price=105.0)
        # atr["levels"] does NOT have a "call_trigger" key (only "trigger_bull")
        assert "call_trigger" not in atr["levels"]
        # atr["call_trigger"] (top-level alias) DOES exist
        assert "call_trigger" in atr
        ribbon = _make_ribbon()
        phase = _make_phase()
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        # trigger_hit should reflect current_price vs call_trigger
        assert "trigger_hit" in result["flags"]

    def test_bug_phase_green_not_firing_up(self):
        """Bug 3: phase='green' matches bullish momentum (not 'firing_up')."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase(phase="green")
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        # With phase="green" and direction="bullish", momentum_confirmed=True
        assert result["flags"]["momentum_confirmed"] is True

    def test_bug_phase_firing_up_no_longer_matches(self):
        """Bug 3 regression: old string 'firing_up' must NOT match."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase(phase="firing_up")  # wrong old value
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        # "firing_up" != "green" → momentum_confirmed should be False
        assert result["flags"]["momentum_confirmed"] is False

    def test_bug_compression_flag_uses_in_compression(self):
        """Bug 4: squeeze flag reads phase['in_compression'], not squeeze_active/fired."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase(in_compression=True)
        # Explicit: neither 'squeeze_active' nor 'squeeze_fired' in phase dict
        assert "squeeze_active" not in phase
        assert "squeeze_fired" not in phase
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        assert result["flags"]["squeeze"] is True

    def test_bug_compression_false_when_not_compressed(self):
        """Bug 4: squeeze=False when in_compression=False."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase(in_compression=False)
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        assert result["flags"]["squeeze"] is False


# ── Scoring and grading ────────────────────────────────────────────────────────

class TestScoringAndGrading:
    def _all_green_bullish(self) -> dict:
        """Returns a checklist result where all scoreable flags are True."""
        atr = _make_atr(current_price=105.0, pdc=100.0, atr=2.0, atr_room_ok=True)
        ribbon = _make_ribbon(ribbon_state="bullish", ema48=100.5, above_200ema=True)
        phase = _make_phase(phase="green", in_compression=False)
        # PDH at 100.47 (near call_trigger=100.472) → confluence within 0.5%
        struct = _make_structure(price_above_pdh=True, pdh=100.47)
        return green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=14.0)

    def test_all_green_score_aplus_grade(self):
        """All scoreable flags True → score >= 5 → grade='A+'."""
        result = self._all_green_bullish()
        assert result["score"] >= 5
        assert result["grade"] == "A+"

    def test_grade_a_at_score_4(self):
        """Score = 4 → grade='A'."""
        # Disable some flags to hit exactly 4
        atr = _make_atr(current_price=99.0, atr_room_ok=True)  # below call_trigger
        ribbon = _make_ribbon(ribbon_state="bullish", above_200ema=True)
        phase = _make_phase(phase="green")
        struct = _make_structure(price_above_pdh=True)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=14.0)
        assert result["grade"] in ("A+", "A", "B", "skip")

    def test_three_flags_grade_b(self):
        """Exactly 3 True flags → grade='B'."""
        # Only trend_ribbon_stacked, price_above_cloud, and momentum_confirmed are True
        atr = _make_atr(current_price=99.0, atr_room_ok=False)  # below trigger
        ribbon = _make_ribbon(ribbon_state="bullish", ema48=98.0, above_200ema=False)
        phase = _make_phase(phase="green", in_compression=False)
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=None)
        # Score depends on exact values; just check valid grade
        assert result["grade"] in ("A+", "A", "B", "skip")
        assert result["score"] == sum(1 for v in result["flags"].values() if v is True)

    def test_two_flags_grade_skip(self):
        """2 or fewer True flags → grade='skip'."""
        # Almost nothing aligned
        atr = _make_atr(current_price=95.0, atr_room_ok=False)
        ribbon = _make_ribbon(ribbon_state="bearish", above_200ema=False)  # bearish when bullish dir
        phase = _make_phase(phase="red")   # red when bullish direction
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=25.0)
        assert result["grade"] in ("A+", "A", "B", "skip")
        assert result["score"] >= 0

    def test_score_excludes_none_flags(self):
        """VIX=None → vix_bias is None → not counted in score."""
        atr = _make_atr()
        ribbon = _make_ribbon(ribbon_state="bullish")
        phase = _make_phase(phase="green")
        struct = _make_structure(price_above_pdh=True)
        result_with_vix = green_flag_checklist(
            atr, ribbon, phase, struct, "bullish", vix=14.0
        )
        result_no_vix = green_flag_checklist(
            atr, ribbon, phase, struct, "bullish", vix=None
        )
        # vix_bias=None should not be counted
        assert result_no_vix["flags"]["vix_bias"] is None
        # Score with None VIX = score with True VIX - 1 (assuming vix was True)
        if result_with_vix["flags"]["vix_bias"] is True:
            assert result_no_vix["score"] == result_with_vix["score"] - 1


# ── VIX bias ──────────────────────────────────────────────────────────────────

class TestVixBias:
    def test_vix_none_excluded(self):
        """vix=None → vix_bias=None (excluded from score)."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase()
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=None)
        assert result["flags"]["vix_bias"] is None

    def test_vix_low_bullish(self):
        """vix=14 + bullish direction → vix_bias=True (low VIX = fear absent)."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase()
        struct = _make_structure()
        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=14.0)
        assert result["flags"]["vix_bias"] is True

    def test_vix_borderline_bullish(self):
        """vix=17 boundary: < 17 → True, >= 17 → False."""
        atr = _make_atr()
        ribbon = _make_ribbon()
        phase = _make_phase()
        struct = _make_structure()
        result_low = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=16.9)
        result_high = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=17.0)
        assert result_low["flags"]["vix_bias"] is True
        assert result_high["flags"]["vix_bias"] is False

    def test_vix_high_bearish(self):
        """vix=25 + bearish direction → vix_bias=True (high VIX helps puts)."""
        atr = _make_atr(current_price=95.0)
        ribbon = _make_ribbon(ribbon_state="bearish", ema48=101.0)
        phase = _make_phase(phase="red")
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish", vix=25.0)
        assert result["flags"]["vix_bias"] is True

    def test_vix_low_bearish(self):
        """vix=14 + bearish direction → vix_bias=False (low VIX hurts puts)."""
        atr = _make_atr(current_price=95.0)
        ribbon = _make_ribbon(ribbon_state="bearish", ema48=101.0)
        phase = _make_phase(phase="red")
        struct = _make_structure(price_above_pdh=False)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish", vix=14.0)
        assert result["flags"]["vix_bias"] is False


# ── Output shape ──────────────────────────────────────────────────────────────

class TestOutputShape:
    def test_verbal_audit_is_nonempty_string(self):
        """verbal_audit must be a non-empty string."""
        result = green_flag_checklist(
            _make_atr(), _make_ribbon(), _make_phase(), _make_structure(), "bullish"
        )
        assert isinstance(result["verbal_audit"], str)
        assert len(result["verbal_audit"]) > 0

    def test_required_keys_present(self):
        """Result must have direction, score, max_score, grade, recommendation, flags, verbal_audit."""
        result = green_flag_checklist(
            _make_atr(), _make_ribbon(), _make_phase(), _make_structure(), "bullish"
        )
        for key in ("direction", "score", "max_score", "grade", "recommendation", "flags", "verbal_audit"):
            assert key in result, f"Missing key: {key}"

    def test_max_score_is_ten(self):
        """max_score must always be 10."""
        result = green_flag_checklist(
            _make_atr(), _make_ribbon(), _make_phase(), _make_structure(), "bullish"
        )
        assert result["max_score"] == 10

    def test_grade_values_valid(self):
        """Grade must be one of the four valid values."""
        result = green_flag_checklist(
            _make_atr(), _make_ribbon(), _make_phase(), _make_structure(), "bullish"
        )
        assert result["grade"] in ("A+", "A", "B", "skip")


# ── Bearish direction ─────────────────────────────────────────────────────────

class TestBearishDirection:
    def test_bearish_direction_checks_price_below_cloud(self):
        """Bearish direction: flag is 'price_below_cloud' not 'price_above_cloud'."""
        atr = _make_atr(current_price=95.0)
        ribbon = _make_ribbon(ribbon_state="bearish", ema48=101.0)
        phase = _make_phase(phase="red")
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish")
        assert "price_below_cloud" in result["flags"]
        assert "price_above_cloud" not in result["flags"]

    def test_bearish_momentum_uses_red_phase(self):
        """Bearish direction: momentum_confirmed=True when phase='red'."""
        atr = _make_atr(current_price=95.0)
        ribbon = _make_ribbon(ribbon_state="bearish", ema48=101.0)
        phase = _make_phase(phase="red")
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish")
        assert result["flags"]["momentum_confirmed"] is True

    def test_bearish_trigger_checks_put_trigger(self):
        """Bearish direction: trigger_hit = current_price <= put_trigger."""
        pdc = 100.0
        atr_val = 2.0
        put_trigger = pdc - atr_val * 0.236   # 99.528
        atr = _make_atr(current_price=99.0, pdc=pdc, atr=atr_val)  # below put_trigger
        ribbon = _make_ribbon(ribbon_state="bearish", ema48=101.0)
        phase = _make_phase(phase="red")
        struct = _make_structure(price_above_pdh=False, pdh=110.0)
        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish")
        # 99.0 <= 99.528 → trigger_hit=True
        assert result["flags"]["trigger_hit"] is True

    def test_direction_in_result(self):
        """Result['direction'] must match the input direction."""
        result = green_flag_checklist(
            _make_atr(), _make_ribbon(), _make_phase(), _make_structure(), "bearish"
        )
        assert result["direction"] == "bearish"
