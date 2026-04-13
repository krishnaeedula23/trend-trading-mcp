from api.indicators.satyland.setup_grader import grade_setup


class TestSqueeze:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 35.0, "atr_room_ok": True, "current_price": 560.0},
            "ribbon": {
                "ribbon_state": "bullish",
                "bias_candle": "blue",
                "in_compression": False,
            },
            "phase": {"phase": "compression", "in_compression": True, "oscillator": 5.0},
            "structure": {"price_above_pdh": True, "price_above_pmh": False},
            "mtf_scores": {
                "alignment": "bullish", "min_score": 9,
                "3m": {"score": 8, "is_a_plus": False},
                "10m": {"score": 9, "is_a_plus": False},
                "1h": {"score": 10, "is_a_plus": True},
            },
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """Squeeze with compression + coiling ribbon + HTF directional → not skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="squeeze",
            direction="bullish",
            vix=17.5,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """No compression active → skip."""
        inputs = self._make_inputs(
            phase={"phase": "green", "in_compression": False, "oscillator": 30.0},
        )
        result = grade_setup(setup_type="squeeze", direction="bullish", **inputs)
        assert result["grade"] == "skip"

    def test_chopzilla_ribbon_skips(self):
        """Chopzilla ribbon_state → ribbon_coiling fails → skip."""
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "chopzilla",
            "bias_candle": "gray",
            "in_compression": False,
        })
        result = grade_setup(setup_type="squeeze", direction="bullish", **inputs)
        assert result["grade"] == "skip"

    def test_no_htf_directional_skips(self):
        """All TF scores below 7 → htf_directional fails → skip."""
        inputs = self._make_inputs(mtf_scores={
            "alignment": "bullish", "min_score": 3,
            "3m": {"score": 3, "is_a_plus": False},
            "10m": {"score": 4, "is_a_plus": False},
            "1h": {"score": 5, "is_a_plus": False},
        })
        result = grade_setup(setup_type="squeeze", direction="bullish", **inputs)
        assert result["grade"] == "skip"

    def test_bearish_squeeze(self):
        """Bearish squeeze in compression with HTF scores negative."""
        inputs = self._make_inputs(
            ribbon={"ribbon_state": "bearish", "bias_candle": "orange", "in_compression": False},
            structure={"price_below_pdl": True, "price_below_pml": False},
            mtf_scores={
                "alignment": "bearish", "min_score": -9,
                "3m": {"score": -8, "is_a_plus": False},
                "10m": {"score": -9, "is_a_plus": False},
                "1h": {"score": -10, "is_a_plus": False},
            },
        )
        result = grade_setup(
            setup_type="squeeze",
            direction="bearish",
            vix=18.0,
            **inputs,
        )
        assert all(f["passed"] for f in result["required_flags"])
        assert result["grade"] != "skip"
