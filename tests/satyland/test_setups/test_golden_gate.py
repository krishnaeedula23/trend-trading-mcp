from api.indicators.satyland.setup_grader import grade_setup


class TestGoldenGate:
    def _make_inputs(self, **overrides):
        defaults = {
            "atr": {
                "atr_covered_pct": 40.0, "atr_room_ok": True,
                "call_trigger": 561.0, "put_trigger": 557.0,
                "current_price": 563.5,
                "levels": {"golden_gate_bull": {"price": 563.0, "pct": "+38.2%", "fib": 0.382}},
            },
            "ribbon": {"ribbon_state": "bullish"},
            "phase": {"phase": "green", "oscillator": 55.0,
                      "zone": "high", "direction": "rising", "zone_state": "high_rising"},
            "structure": {"price_above_pdh": True, "price_above_pmh": True},
            "mtf_scores": {"alignment": "bullish", "min_score": 13,
                           "3m": {"score": 13}, "10m": {"score": 14}, "1h": {"score": 13}},
        }
        defaults.update(overrides)
        return defaults

    def test_bilbo_confirmed_auto_a_plus(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="golden_gate", direction="bullish",
                             phase_60m={"zone_state": "high_rising", "oscillator": 55.0}, **inputs)
        assert result["grade"] == "A+"
        assert result["probability"] >= 0.77
        assert result["probability_source"] == "backtested"

    def test_counter_trend_po_skips(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="golden_gate", direction="bullish",
                             phase_60m={"zone_state": "mid_falling", "oscillator": -5.0}, **inputs)
        assert result["grade"] == "skip"

    def test_bearish_bilbo_90_percent(self):
        inputs = self._make_inputs(
            atr={"atr_covered_pct": 30.0, "atr_room_ok": True,
                 "put_trigger": 557.0, "call_trigger": 561.0, "current_price": 555.0,
                 "levels": {"golden_gate_bear": {"price": 556.0, "pct": "-38.2%", "fib": 0.382}}},
            phase={"phase": "red", "oscillator": -55.0, "zone": "low",
                   "direction": "falling", "zone_state": "low_falling"},
            ribbon={"ribbon_state": "bearish"},
            structure={"price_below_pdl": True},
            mtf_scores={"alignment": "bearish", "min_score": 12},
        )
        result = grade_setup(setup_type="golden_gate", direction="bearish",
                             phase_60m={"zone_state": "low_falling", "oscillator": -55.0}, **inputs)
        assert result["grade"] == "A+"
        assert result["probability"] >= 0.90

    def test_reasoning_includes_probability(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="golden_gate", direction="bullish",
                             phase_60m={"zone_state": "high_rising"}, **inputs)
        assert "backtested" in result["reasoning"]

    def test_baseline_probability_without_bilbo(self):
        inputs = self._make_inputs()
        result = grade_setup(setup_type="golden_gate", direction="bullish",
                             phase_60m={"zone_state": "mid_rising"}, **inputs)
        assert 0.60 <= result["probability"] <= 0.65
