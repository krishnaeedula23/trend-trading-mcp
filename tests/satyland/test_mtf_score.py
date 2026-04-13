import pytest
from api.indicators.satyland.mtf_score import mtf_score


class TestMTFScoreCalculation:
    """MTF Score: -15 to +15 based on EMA crosses + trend directions."""

    def test_perfect_bullish_score(self, trending_up_250_df):
        result = mtf_score(trending_up_250_df)
        assert result["score"] > 10

    def test_perfect_bearish_score(self, trending_down_250_df):
        result = mtf_score(trending_down_250_df)
        assert result["score"] < -10

    def test_score_range(self, trending_up_250_df):
        result = mtf_score(trending_up_250_df)
        assert -15 <= result["score"] <= 15

    def test_return_shape(self, trending_up_250_df):
        result = mtf_score(trending_up_250_df)
        for key in ("score", "cross_score", "trend_score", "po_value", "in_compression", "is_a_plus"):
            assert key in result

    def test_score_is_sum_of_components(self, trending_up_250_df):
        result = mtf_score(trending_up_250_df)
        assert result["score"] == result["cross_score"] + result["trend_score"]
        assert -10 <= result["cross_score"] <= 10
        assert -5 <= result["trend_score"] <= 5

    def test_a_plus_requires_15_and_compression(self, trending_up_250_df):
        result = mtf_score(trending_up_250_df)
        if abs(result["score"]) == 15 and result["in_compression"]:
            assert result["is_a_plus"] is True
        else:
            assert result["is_a_plus"] is False
