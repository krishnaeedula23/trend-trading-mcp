from api.indicators.satyland.setup_grader import grade_setup


class TestFlagIntoRibbon:
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

    def test_no_pullback_candle_skips(self):
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "bullish", "bias_candle": "green",
            "ema13": 560.0, "ema21": 559.0, "ema48": 555.0,
            "above_48ema": True, "in_compression": False,
        })
        result = grade_setup(setup_type="flag_into_ribbon", direction="bullish", **inputs)
        assert result["grade"] == "skip"

    def test_bearish_direction(self):
        inputs = self._make_inputs(
            ribbon={"ribbon_state": "bearish", "bias_candle": "orange",
                    "ema13": 555.0, "ema21": 556.0, "ema48": 560.0,
                    "above_48ema": False, "in_compression": False},
            phase={"phase": "red", "oscillator": -45.0},
            structure={"price_below_pdl": True, "price_below_pml": True},
            mtf_scores={"alignment": "bearish", "min_score": 11},
        )
        result = grade_setup(setup_type="flag_into_ribbon", direction="bearish", **inputs)
        assert result["grade"] in ("A+", "A")

    def test_reasoning_includes_setup_name(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="flag_into_ribbon", direction="bullish", **inputs)
        assert "flag_into_ribbon" in result["reasoning"]
