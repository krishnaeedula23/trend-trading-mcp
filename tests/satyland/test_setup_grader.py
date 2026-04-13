import pytest
from api.indicators.satyland.setup_grader import grade_setup


class TestSetupGrader:
    def test_returns_required_keys(self):
        # Register a minimal test evaluator first
        from api.indicators.satyland.setups import register
        from api.indicators.satyland.setups.base import SetupEvaluator

        class TestEval(SetupEvaluator):
            name = "test_setup"
            def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("test_req", True, "passes")]
            def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("test_bonus", True, "passes")]

        register("test_setup", TestEval())

        result = grade_setup(
            setup_type="test_setup", direction="bullish",
            atr={}, ribbon={}, phase={}, structure={}, mtf_scores={},
        )
        for key in ("grade", "score", "required_flags", "bonus_flags", "reasoning", "probability"):
            assert key in result

    def test_required_flag_fails_forces_skip(self):
        from api.indicators.satyland.setups import register
        from api.indicators.satyland.setups.base import SetupEvaluator

        class FailEval(SetupEvaluator):
            name = "fail_setup"
            def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("must_pass", False, "fails")]
            def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("b1", True, "ok"), ("b2", True, "ok"), ("b3", True, "ok"), ("b4", True, "ok")]

        register("fail_setup", FailEval())
        result = grade_setup(
            setup_type="fail_setup", direction="bullish",
            atr={}, ribbon={}, phase={}, structure={}, mtf_scores={},
        )
        assert result["grade"] == "skip"

    def test_unknown_setup_raises(self):
        with pytest.raises(ValueError, match="Unknown setup"):
            grade_setup(
                setup_type="nonexistent", direction="bullish",
                atr={}, ribbon={}, phase={}, structure={}, mtf_scores={},
            )

    def test_four_bonus_flags_gives_a_plus(self):
        from api.indicators.satyland.setups import register
        from api.indicators.satyland.setups.base import SetupEvaluator

        class GoodEval(SetupEvaluator):
            name = "good_setup"
            def evaluate_required(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("req", True, "ok")]
            def evaluate_bonus(self, direction, atr, ribbon, phase, structure, mtf_scores, **kw):
                return [("b1", True, "ok"), ("b2", True, "ok"), ("b3", True, "ok"), ("b4", True, "ok")]

        register("good_setup", GoodEval())
        result = grade_setup(
            setup_type="good_setup", direction="bullish",
            atr={}, ribbon={}, phase={}, structure={}, mtf_scores={},
        )
        assert result["grade"] == "A+"

    def test_personal_win_rate_overrides(self):
        result = grade_setup(
            setup_type="good_setup", direction="bullish",
            atr={}, ribbon={}, phase={}, structure={}, mtf_scores={},
            personal_win_rate=0.72, personal_trade_count=38,
        )
        assert result["probability"] == 0.72
        assert result["probability_source"] == "personal"
