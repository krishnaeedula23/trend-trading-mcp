from api.indicators.satyland.setup_grader import grade_setup


class TestVomy:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 45.0, "atr_room_ok": True, "current_price": 555.0},
            "ribbon": {
                "ribbon_state": "chopzilla",
                "bias_candle": "orange",
                "ema13": 558.0, "ema21": 559.0, "ema48": 560.0,
                "above_48ema": False,
                "in_compression": False,
            },
            "phase": {"phase": "red", "oscillator": -30.0},
            "structure": {"price_below_pdl": True, "price_below_pml": False},
            "mtf_scores": {
                "alignment": "bearish", "min_score": -8, "exec_score": -5,
                "3m": {"score": -9}, "10m": {"score": -8}, "1h": {"score": -7},
            },
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """Vomy (bearish reversal) with all required flags passes."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="vomy",
            direction="bearish",
            htf_shifting=True,
            vix=22.0,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """If ribbon is still stacked bullish (not transitioning), should skip."""
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "bearish",  # already bearish, so direction matches — not a reversal
            "bias_candle": "orange",
            "ema13": 558.0, "ema21": 559.0, "ema48": 560.0,
            "above_48ema": False,
            "in_compression": False,
        })
        # For Vomy (bearish), ribbon_state must NOT be "bearish" to be transitioning
        result = grade_setup(setup_type="vomy", direction="bearish", **inputs)
        assert result["grade"] == "skip"

    def test_ivomy_bullish_variant(self):
        """iVomy (bullish reversal): ribbon was bearish, now transitioning up."""
        inputs = self._make_inputs(
            ribbon={
                "ribbon_state": "chopzilla",
                "bias_candle": "blue",
                "ema13": 562.0, "ema21": 561.0, "ema48": 558.0,
                "above_48ema": True,
                "in_compression": False,
            },
            phase={"phase": "green", "oscillator": 25.0},
            structure={"price_above_pdh": True, "price_above_pmh": False},
            mtf_scores={
                "alignment": "bullish", "min_score": 8, "exec_score": 6,
                "3m": {"score": 7}, "10m": {"score": 8}, "1h": {"score": 6},
            },
        )
        result = grade_setup(
            setup_type="ivomy",
            direction="bullish",
            htf_shifting=True,
            vix=15.0,
            **inputs,
        )
        assert all(f["passed"] for f in result["required_flags"])
        assert result["grade"] != "skip"

    def test_wrong_bias_candle_skips(self):
        """Vomy with non-orange bias_candle skips."""
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "chopzilla",
            "bias_candle": "green",
            "ema13": 558.0, "ema21": 559.0, "ema48": 560.0,
            "above_48ema": False,
            "in_compression": False,
        })
        result = grade_setup(setup_type="vomy", direction="bearish", **inputs)
        assert result["grade"] == "skip"

    def test_mtf_score_not_flipped_skips(self):
        """Vomy with positive exec_score (not flipped bearish) skips."""
        inputs = self._make_inputs(mtf_scores={
            "alignment": "bullish", "min_score": 10, "exec_score": 8,
            "3m": {"score": 9}, "10m": {"score": 10}, "1h": {"score": 8},
        })
        result = grade_setup(setup_type="vomy", direction="bearish", **inputs)
        assert result["grade"] == "skip"
