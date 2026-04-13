from api.indicators.satyland.setup_grader import grade_setup


class TestDivergence:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {"atr_covered_pct": 65.0, "atr_room_ok": False, "current_price": 555.0},
            "ribbon": {
                "ribbon_state": "chopzilla",
                "bias_candle": "gray",
                "in_compression": True,
            },
            "phase": {"phase": "red", "oscillator": -60.0},
            "structure": {"price_below_pdl": True},
            "mtf_scores": {"alignment": "bearish", "min_score": -10},
        }
        defaults.update(overrides)
        return defaults

    def test_all_flags_pass(self):
        """Divergence with swing, PO divergence, and exhausted ribbon → not skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="divergence",
            direction="bullish",
            swing_type="low",
            po_divergence=True,
            mtf_divergence=True,
            volume_declining=True,
            score_weakening=True,
            **inputs,
        )
        assert result["grade"] in ("A+", "A", "B")
        assert all(f["passed"] for f in result["required_flags"])

    def test_required_flag_fails_skips(self):
        """No swing_type → swing_formed fails → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="divergence",
            direction="bullish",
            po_divergence=True,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_bearish_divergence_variant(self):
        """Bearish divergence: price at swing high with PO divergence."""
        inputs = self._make_inputs(
            atr={"atr_covered_pct": 70.0, "atr_room_ok": False, "current_price": 570.0},
            ribbon={"ribbon_state": "chopzilla", "bias_candle": "gray", "in_compression": True},
            phase={"phase": "green", "oscillator": 70.0},
        )
        result = grade_setup(
            setup_type="divergence",
            direction="bearish",
            swing_type="high",
            po_divergence=True,
            mtf_divergence=True,
            volume_declining=True,
            **inputs,
        )
        assert all(f["passed"] for f in result["required_flags"])
        assert result["grade"] != "skip"

    def test_no_po_divergence_skips(self):
        """po_divergence=False → skip."""
        inputs = self._make_inputs()
        result = grade_setup(
            setup_type="divergence",
            direction="bullish",
            swing_type="low",
            po_divergence=False,
            **inputs,
        )
        assert result["grade"] == "skip"

    def test_ribbon_not_exhausted_skips(self):
        """Stacked bullish ribbon (not exhausted) → ribbon_exhaustion fails → skip."""
        inputs = self._make_inputs(ribbon={
            "ribbon_state": "bullish",
            "bias_candle": "blue",
            "in_compression": False,
        })
        result = grade_setup(
            setup_type="divergence",
            direction="bullish",
            swing_type="low",
            po_divergence=True,
            **inputs,
        )
        assert result["grade"] == "skip"
