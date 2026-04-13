from api.indicators.satyland.setup_grader import grade_setup


class TestOrb:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {
                "atr_covered_pct": 40.0, "atr_room_ok": True,
                "current_price": 565.0,
            },
            "ribbon": {"ribbon_state": "bullish", "bias_candle": "blue"},
            "phase": {"phase": "green", "oscillator": 50.0},
            "structure": {"price_above_pdh": True, "price_above_pmh": False},
            "mtf_scores": {
                "alignment": "bullish", "min_score": 11,
                "3m": {"score": 12}, "10m": {"score": 11}, "1h": {"score": 13},
            },
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """ORB with all required flags → not skip and grade A or better."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="orb",
            direction="bullish",
            or_high=563.0,
            or_low=560.0,
            retest_confirmed=True,
            or_size_ok=True,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """Missing or_high/or_low → or_marked fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="orb",
            direction="bullish",
            or_high=0,
            or_low=0,
            retest_confirmed=True,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_bearish_orb_variant(self):
        """Bearish ORB: price closes below or_low after confirmed retest."""
        inputs = self._make_inputs(
            atr={"atr_covered_pct": 35.0, "atr_room_ok": True, "current_price": 557.0},
            ribbon={"ribbon_state": "bearish", "bias_candle": "orange"},
            phase={"phase": "red", "oscillator": -50.0},
            structure={"price_below_pdl": True, "price_below_pml": False},
            mtf_scores={"alignment": "bearish", "min_score": 10,
                        "3m": {"score": -11}, "10m": {"score": -10}, "1h": {"score": -12}},
        )
        result = grade_setup(
            setup_type="orb",
            direction="bearish",
            or_high=563.0,
            or_low=559.0,
            retest_confirmed=True,
            **inputs,
        )
        assert all(f["passed"] for f in result["required_flags"])
        assert result["grade"] != "skip"

    def test_retest_not_confirmed_skips(self):
        """No retest_confirmed → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="orb",
            direction="bullish",
            or_high=563.0,
            or_low=560.0,
            retest_confirmed=False,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_candle_inside_range_skips(self):
        """Current price inside OR range → candle_close_outside fails → skip."""
        inputs = self._make_inputs(
            atr={"atr_covered_pct": 40.0, "atr_room_ok": True, "current_price": 561.5},
        )
        result = grade_setup(
            setup_type="orb",
            direction="bullish",
            or_high=563.0,
            or_low=560.0,
            retest_confirmed=True,
            **inputs,
        )
        assert result["grade"] == "skip"
