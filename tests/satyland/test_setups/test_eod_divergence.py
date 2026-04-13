from api.indicators.satyland.setup_grader import grade_setup


class TestEodDivergence:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 68.0, "atr_room_ok": False, "current_price": 557.0},
            "ribbon": {
                "ribbon_state": "chopzilla",
                "bias_candle": "gray",
                "in_compression": True,
            },
            "phase": {"phase": "red", "oscillator": -55.0},
            "structure": {"price_below_pdl": True},
            "mtf_scores": {"alignment": "bearish", "min_score": -9},
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """EOD divergence after 3pm EST with PO divergence and swing formed → not skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="eod_divergence",
            direction="bullish",
            time_est="15:30",
            po_divergence=True,
            swing_type="low",
            volume_present=True,
            target_nearby=True,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """Too early in the session (before 3pm EST) → after_noon_pst fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="eod_divergence",
            direction="bullish",
            time_est="12:00",
            po_divergence=True,
            swing_type="low",
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_no_time_provided_skips(self):
        """No time_est → after_noon_pst fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="eod_divergence",
            direction="bullish",
            po_divergence=True,
            swing_type="low",
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_bearish_eod_divergence(self):
        """Bearish EOD divergence: price at swing high with PO divergence late session."""
        inputs = self._make_inputs(
            atr={"atr_covered_pct": 72.0, "atr_room_ok": False, "current_price": 569.0},
            ribbon={"ribbon_state": "chopzilla", "bias_candle": "gray", "in_compression": True},
            phase={"phase": "green", "oscillator": 65.0},
        )
        result = grade_setup(
            setup_type="eod_divergence",
            direction="bearish",
            time_est="15:45",
            po_divergence=True,
            swing_type="high",
            **inputs,
        )
        assert all(f["passed"] for f in result["required_flags"])
        assert result["grade"] != "skip"

    def test_no_swing_type_skips(self):
        """No swing_type → swing_formed fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="eod_divergence",
            direction="bullish",
            time_est="15:30",
            po_divergence=True,
            **inputs,
        )
        assert result["grade"] == "skip"
