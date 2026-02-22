"""
Level 2 tests — Pine Script invariant rules.

These use the actual indicator functions with synthetic DataFrames to assert
cross-indicator behavioral invariants that should hold for any realistic dataset.
No mocking — real computation only.
"""

import pandas as pd
import pytest

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.green_flag import green_flag_checklist
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.satyland.price_structure import price_structure


def _make_df(n: int, closes: list[float],
             h_offset: float = 0.5,
             l_offset: float = 0.5) -> pd.DataFrame:
    highs = [c + h_offset for c in closes]
    lows = [c - l_offset for c in closes]
    opens = [closes[0]] + closes[:-1]
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )


class TestAtrLevelsInvariants:
    def test_atr_levels_anchored_to_pdc_not_current(self):
        """
        Levels don't move when only today's bar changes.

        If we change only the last bar (today), the levels (which are anchored
        to PDC = iloc[-2].close and ATR = iloc[-2] settled value) must not change.
        """
        n = 50
        base_closes = [100.0] * n
        base_highs = [101.0] * n
        base_lows = [99.0] * n
        base_opens = [100.0] * n

        idx = pd.date_range("2024-01-01", periods=n, freq="B")

        df1 = pd.DataFrame(
            {"open": base_opens, "high": base_highs, "low": base_lows, "close": base_closes},
            index=idx,
        )
        # Variant: only today's bar differs (last bar)
        base_closes_v2 = base_closes.copy()
        base_closes_v2[-1] = 103.0
        base_highs_v2 = base_highs.copy()
        base_highs_v2[-1] = 104.0
        df2 = pd.DataFrame(
            {"open": base_opens, "high": base_highs_v2, "low": base_lows, "close": base_closes_v2},
            index=idx,
        )

        result1 = atr_levels(df1)
        result2 = atr_levels(df2)

        # PDC and ATR must be identical (both from iloc[-2])
        assert result1["pdc"] == result2["pdc"]
        assert result1["atr"] == result2["atr"]

        # All levels must be identical
        for key in result1["levels"]:
            assert result1["levels"][key]["price"] == result2["levels"][key]["price"], \
                f"Level {key} differs despite same previous bar"

    def test_atr_covered_increases_with_intraday_range(self):
        """Wider intraday range → higher atr_covered_pct."""
        n = 50
        base_closes = [100.0] * n
        base_opens = [100.0] * n
        idx = pd.date_range("2024-01-01", periods=n, freq="B")

        def make_df_with_last_range(high: float, low: float) -> pd.DataFrame:
            highs = [101.0] * (n - 1) + [high]
            lows = [99.0] * (n - 1) + [low]
            return pd.DataFrame(
                {"open": base_opens, "high": highs, "low": lows, "close": base_closes},
                index=idx,
            )

        narrow = atr_levels(make_df_with_last_range(100.2, 99.8))   # range=0.4
        wide = atr_levels(make_df_with_last_range(101.5, 99.0))     # range=2.5

        assert narrow["atr_covered_pct"] < wide["atr_covered_pct"]

    def test_atr_room_ok_consistent_with_status(self):
        """atr_room_ok=True ↔ atr_status='green'."""
        n = 50
        for last_range, expected_room_ok in [(0.4, True), (1.5, False)]:
            highs = [101.0] * (n - 1) + [100.0 + last_range / 2]
            lows = [99.0] * (n - 1) + [100.0 - last_range / 2]
            closes = [100.0] * n
            opens = [100.0] * n
            idx = pd.date_range("2024-01-01", periods=n, freq="B")
            df = pd.DataFrame(
                {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
            )
            result = atr_levels(df)
            assert result["atr_room_ok"] == (result["atr_status"] == "green")

    def test_call_trigger_above_pdc_put_trigger_below(self, atr_daily_df):
        """call_trigger > PDC > put_trigger always."""
        result = atr_levels(atr_daily_df)
        assert result["call_trigger"] > result["pdc"]
        assert result["put_trigger"] < result["pdc"]


class TestRibbonCompressionInvariants:
    def test_ribbon_compression_is_stateful(self, flat_df):
        """
        Compression tracker is computed bar-by-bar (stateful loop).
        Verify in_compression is deterministic for a given input.
        """
        result1 = pivot_ribbon(flat_df)
        result2 = pivot_ribbon(flat_df)
        assert result1["in_compression"] == result2["in_compression"]

    def test_bias_candle_always_set(self, trending_up_df, trending_down_df, flat_df):
        """bias_candle must always be one of the 5 valid values."""
        valid_candles = {"green", "blue", "orange", "red", "gray"}
        for df in (trending_up_df, trending_down_df, flat_df):
            result = pivot_ribbon(df)
            assert result["bias_candle"] in valid_candles

    def test_above_48ema_consistent_with_ema48(self, trending_up_df):
        """above_48ema = (close >= ema48). Must be consistent."""
        result = pivot_ribbon(trending_up_df)
        curr_close = float(trending_up_df["close"].iloc[-1])
        assert result["above_48ema"] == (curr_close >= result["ema48"])

    def test_ribbon_state_consistent_with_emas(self, trending_up_df, trending_down_df):
        """ribbon_state='bullish' ↔ EMA8 > EMA21 > EMA48."""
        for df, expected_state in [(trending_up_df, "bullish"), (trending_down_df, "bearish")]:
            result = pivot_ribbon(df)
            e8, e21, e48 = result["ema8"], result["ema21"], result["ema48"]
            if result["ribbon_state"] == "bullish":
                assert e8 > e21 > e48
            elif result["ribbon_state"] == "bearish":
                assert e8 < e21 < e48

    def test_chopzilla_flag_consistent_with_ribbon_state(self, trending_up_df):
        """chopzilla flag must equal (ribbon_state == 'chopzilla')."""
        result = pivot_ribbon(trending_up_df)
        assert result["chopzilla"] == (result["ribbon_state"] == "chopzilla")


class TestPhaseOscillatorInvariants:
    def test_phase_osc_bounded_in_normal_markets(self, trending_up_df, trending_down_df):
        """For realistic price series, oscillator stays within a wide but finite range."""
        for df in (trending_up_df, trending_down_df):
            result = phase_oscillator(df)
            # With ATR-normalized formula, values are typically bounded
            # Use a wide range to avoid false failures
            assert -500 < result["oscillator"] < 500

    def test_phase_consistent_with_oscillator_sign(self, trending_up_df, trending_down_df):
        """phase='green' ↔ oscillator >= 0 (when not in compression)."""
        for df in (trending_up_df, trending_down_df):
            result = phase_oscillator(df)
            if not result["in_compression"]:
                if result["oscillator"] >= 0:
                    assert result["phase"] == "green"
                else:
                    assert result["phase"] == "red"

    def test_in_compression_overrides_phase(self, flat_df):
        """When in_compression=True, phase must be 'compression'."""
        result = phase_oscillator(flat_df)
        if result["in_compression"]:
            assert result["phase"] == "compression"

    def test_zone_classification_exhaustive(self, trending_up_df):
        """current_zone must always be one of the 8 valid zone strings."""
        valid_zones = {
            "extreme_up", "distribution", "neutral_up", "above_zero",
            "below_zero", "neutral_down", "accumulation", "extreme_down",
        }
        result = phase_oscillator(trending_up_df)
        assert result["current_zone"] in valid_zones


class TestFullTradePlanRoundtrip:
    def test_full_trade_plan_bullish_no_exception(self, trending_up_df):
        """green_flag_checklist(atr, ribbon, phase, struct, 'bullish') must not throw."""
        atr = atr_levels(trending_up_df)
        ribbon = pivot_ribbon(trending_up_df)
        phase = phase_oscillator(trending_up_df)
        struct = price_structure(trending_up_df)

        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish", vix=14.0)

        assert result["grade"] in ("A+", "A", "B", "skip")
        assert 0 <= result["score"] <= result["max_score"]
        assert isinstance(result["verbal_audit"], str)

    def test_full_trade_plan_bearish_no_exception(self, trending_down_df):
        """green_flag_checklist with 'bearish' direction must not throw."""
        atr = atr_levels(trending_down_df)
        ribbon = pivot_ribbon(trending_down_df)
        phase = phase_oscillator(trending_down_df)
        struct = price_structure(trending_down_df)

        result = green_flag_checklist(atr, ribbon, phase, struct, "bearish", vix=25.0)

        assert result["grade"] in ("A+", "A", "B", "skip")
        assert result["direction"] == "bearish"

    def test_score_is_sum_of_true_flags(self, trending_up_df):
        """result['score'] == count of True values in result['flags']."""
        atr = atr_levels(trending_up_df)
        ribbon = pivot_ribbon(trending_up_df)
        phase = phase_oscillator(trending_up_df)
        struct = price_structure(trending_up_df)

        result = green_flag_checklist(atr, ribbon, phase, struct, "bullish")
        expected_score = sum(1 for v in result["flags"].values() if v is True)
        assert result["score"] == expected_score
