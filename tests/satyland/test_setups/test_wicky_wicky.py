from api.indicators.satyland.setup_grader import grade_setup


class TestWickyWicky:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 55.0, "atr_room_ok": False, "current_price": 558.0},
            "ribbon": {
                "ribbon_state": "bearish",
                "bias_candle": "orange",
                "in_compression": False,
            },
            "phase": {"phase": "green", "oscillator": 10.0},
            "structure": {"price_above_pdh": False, "price_above_pmh": False},
            "mtf_scores": {"alignment": "bearish", "min_score": -5},
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """Wicky Wicky with tweezer + reclaim + bonus → not skip, good grade."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="wicky_wicky",
            direction="bullish",
            tweezer_detected=True,
            reclaim_confirmed=True,
            at_key_level=True,
            volume_increasing=True,
            po_bullish_div=True,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """No tweezer_detected → tweezer_pattern fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="wicky_wicky",
            direction="bullish",
            tweezer_detected=False,
            reclaim_confirmed=True,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_no_reclaim_skips(self):
        """tweezer_detected but reclaim_confirmed=False → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="wicky_wicky",
            direction="bullish",
            tweezer_detected=True,
            reclaim_confirmed=False,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_strong_bear_trend_reduces_bonus(self):
        """Very negative MTF score (< -10) → mtf_not_strongly_negative fails."""
        inputs = self._make_inputs(
            mtf_scores={"alignment": "bearish", "min_score": -15},
        )
        result = grade_setup(
            setup_type="wicky_wicky",
            direction="bullish",
            tweezer_detected=True,
            reclaim_confirmed=True,
            **inputs,
        )
        # Required passes, but one bonus fails
        assert all(f["passed"] for f in result["required_flags"])
        bonus_names = {f["name"]: f["passed"] for f in result["bonus_flags"]}
        assert not bonus_names.get("mtf_not_strongly_negative", True)

    def test_phase_green_triggers_po_divergence_bonus(self):
        """phase == 'green' alone qualifies for po_divergence bonus."""
        inputs = self._make_inputs(phase={"phase": "green", "oscillator": 15.0})
        result = grade_setup(
            setup_type="wicky_wicky",
            direction="bullish",
            tweezer_detected=True,
            reclaim_confirmed=True,
            **inputs,
        )
        bonus_names = {f["name"]: f["passed"] for f in result["bonus_flags"]}
        assert bonus_names.get("po_divergence", False)
