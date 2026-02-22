"""
Level 1 tests for api/indicators/satyland/atr_levels.py

Validates Pine Script accuracy:
  - ATR and PDC sourced from previous bar (settled)
  - Fibonacci levels anchored to PDC ± ATR × fib
  - ATR status thresholds (≤70% green, 70-90% orange, ≥90% red)
  - Price position classification
  - Trend label (EMA 8/21/34 stack)
  - Extension levels gating
"""

import pandas as pd
import pytest

from api.indicators.satyland.atr_levels import _wilder_atr, atr_levels


def _build_flat_df(n: int = 50, price: float = 100.0,
                   last_high: float | None = None,
                   last_low: float | None = None,
                   last_close: float | None = None) -> pd.DataFrame:
    """Helper: flat df with optional last-bar overrides."""
    closes = [price] * n
    highs = [price + 1.0] * n
    lows = [price - 1.0] * n
    opens = [price] * n
    if last_high is not None:
        highs[-1] = last_high
    if last_low is not None:
        lows[-1] = last_low
    if last_close is not None:
        closes[-1] = last_close
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )


class TestPdcAndAtr:
    def test_pdc_is_previous_close(self, atr_daily_df):
        """result['pdc'] must equal daily_df['close'].iloc[-2]."""
        result = atr_levels(atr_daily_df)
        expected = round(float(atr_daily_df["close"].iloc[-2]), 4)
        assert result["pdc"] == expected

    def test_atr_is_previous_bar_settled(self, atr_daily_df):
        """ATR must be iloc[-2] of the Wilder series, not the forming bar."""
        atr_series = _wilder_atr(atr_daily_df)
        expected = round(float(atr_series.iloc[-2]), 4)
        result = atr_levels(atr_daily_df)
        assert abs(result["atr"] - expected) < 1e-4

    def test_atr_converges_to_constant_tr(self, atr_daily_df):
        """With 49 bars of TR=2.0, settled ATR at iloc[-2] ≈ 2.0."""
        result = atr_levels(atr_daily_df)
        # Allow small convergence error (should be <0.01 after 49 bars)
        assert abs(result["atr"] - 2.0) < 0.01


class TestFibonacciLevels:
    def test_fibonacci_levels_computed_from_pdc(self, atr_daily_df):
        """trigger_bull = PDC + 0.236×ATR (exact Pine Script formula)."""
        result = atr_levels(atr_daily_df)
        pdc = result["pdc"]
        atr = result["atr"]
        assert result["levels"]["trigger_bull"]["price"] == round(pdc + atr * 0.236, 4)
        assert result["levels"]["trigger_bear"]["price"] == round(pdc - atr * 0.236, 4)
        assert result["levels"]["mid_range_bull"]["price"] == round(pdc + atr * 0.618, 4)
        assert result["levels"]["full_range_bull"]["price"] == round(pdc + atr * 1.000, 4)

    def test_call_trigger_alias_matches_trigger_bull(self, atr_daily_df):
        """Top-level call_trigger == levels['trigger_bull']['price']."""
        result = atr_levels(atr_daily_df)
        assert result["call_trigger"] == result["levels"]["trigger_bull"]["price"]

    def test_put_trigger_alias_matches_trigger_bear(self, atr_daily_df):
        """Top-level put_trigger == levels['trigger_bear']['price']."""
        result = atr_levels(atr_daily_df)
        assert result["put_trigger"] == result["levels"]["trigger_bear"]["price"]

    def test_all_core_levels_present(self, atr_daily_df):
        """All 12 core level keys (6 fibs × 2 directions) must be present."""
        result = atr_levels(atr_daily_df)
        expected_keys = [
            "trigger_bull", "trigger_bear",
            "golden_gate_bull", "golden_gate_bear",
            "mid_50_bull", "mid_50_bear",
            "mid_range_bull", "mid_range_bear",
            "fib_786_bull", "fib_786_bear",
            "full_range_bull", "full_range_bear",
        ]
        for key in expected_keys:
            assert key in result["levels"], f"Missing level key: {key}"


class TestAtrCoverage:
    def test_atr_covered_pct_formula(self, atr_daily_df):
        """atr_covered_pct = round((today_H − today_L) / ATR × 100, 1)."""
        result = atr_levels(atr_daily_df)
        today_h = float(atr_daily_df["high"].iloc[-1])
        today_l = float(atr_daily_df["low"].iloc[-1])
        expected = round((today_h - today_l) / result["atr"] * 100, 1)
        assert result["atr_covered_pct"] == expected

    def test_atr_status_green(self):
        """≤70% ATR covered → status='green', atr_room_ok=True."""
        # Last bar range = 0.2 vs ATR≈2.0 → ~10% → green
        df = _build_flat_df(last_high=100.1, last_low=99.9)
        result = atr_levels(df)
        assert result["atr_status"] == "green"
        assert result["atr_room_ok"] is True

    def test_atr_status_orange(self):
        """70–90% ATR covered → status='orange'."""
        # Last bar range = 1.7 vs ATR≈2.0 → 85% → orange
        df = _build_flat_df(last_high=101.7, last_low=100.0)
        result = atr_levels(df)
        assert result["atr_status"] == "orange"

    def test_atr_status_red(self, atr_daily_df):
        """≥90% ATR covered → status='red', atr_room_ok=False."""
        # atr_daily_df: range=2.0, ATR≈2.0 → ~100% → red
        result = atr_levels(atr_daily_df)
        assert result["atr_covered_pct"] >= 90
        assert result["atr_status"] == "red"
        assert result["atr_room_ok"] is False

    def test_atr_covered_zero_when_atr_is_zero(self, flat_df):
        """ATR=0 → atr_covered_pct=0.0 (divide-by-zero guard)."""
        result = atr_levels(flat_df)
        assert result["atr_covered_pct"] == 0.0


class TestTriggerBox:
    def test_trigger_box_inside_flag(self):
        """Price between put/call trigger → trigger_box.inside=True, chopzilla=True."""
        # Flat df: current_price = PDC = 100.0, triggers at ±0.472 → inside
        df = _build_flat_df(last_high=101.0, last_low=99.0, last_close=100.0)
        result = atr_levels(df)
        assert result["trigger_box"]["inside"] is True
        assert result["chopzilla"] is True

    def test_trigger_box_outside_above(self, atr_daily_df):
        """Price above call_trigger → trigger_box.inside=False."""
        result = atr_levels(atr_daily_df)
        # current_price=102 > call_trigger≈100.47
        assert result["trigger_box"]["inside"] is False


class TestPricePosition:
    def test_price_position_above_full_range(self, atr_daily_df):
        """current_price >= full_range_bull → price_position='above_full_range'."""
        result = atr_levels(atr_daily_df)
        # PDC=100, ATR≈2, full_range_bull=102, current=102 → above_full_range
        assert result["price_position"] == "above_full_range"

    def test_price_position_inside_box(self):
        """Price at PDC (inside trigger box) → price_position='inside_trigger_box'."""
        df = _build_flat_df(last_close=100.0)
        result = atr_levels(df)
        assert result["price_position"] == "inside_trigger_box"


class TestTrendLabel:
    def test_trend_bullish_stack(self, trending_up_df):
        """Increasing prices → close >= EMA8 >= EMA21 >= EMA34 → trend='bullish'."""
        result = atr_levels(trending_up_df)
        assert result["trend"] == "bullish"

    def test_trend_bearish_stack(self, trending_down_df):
        """Decreasing prices → close <= EMA8 <= EMA21 <= EMA34 → trend='bearish'."""
        result = atr_levels(trending_down_df)
        assert result["trend"] == "bearish"


class TestMinimumBars:
    def test_minimum_bars_raises(self):
        """Fewer than 2 daily bars must raise ValueError."""
        single = pd.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.0]},
            index=pd.date_range("2024-01-01", periods=1, freq="B"),
        )
        with pytest.raises(ValueError, match="at least 2"):
            atr_levels(single)


class TestExtensionLevels:
    def test_extensions_not_included_by_default(self, atr_daily_df):
        """No ext_* keys in result['levels'] when include_extensions=False."""
        result = atr_levels(atr_daily_df)
        for key in result["levels"]:
            assert not key.startswith("ext_"), f"Unexpected extension key: {key}"

    def test_extensions_included_when_flagged(self, atr_daily_df):
        """ext_1236_bull and ext_1618_bull present when include_extensions=True."""
        result = atr_levels(atr_daily_df, include_extensions=True)
        assert "ext_1236_bull" in result["levels"]
        assert "ext_1618_bull" in result["levels"]
        assert "ext_2000_bull" in result["levels"]

    def test_extension_formula(self, atr_daily_df):
        """Extension levels computed correctly: ext_1236_bull = full_range_bull + 0.236×ATR."""
        result = atr_levels(atr_daily_df, include_extensions=True)
        atr = result["atr"]
        pdc = result["pdc"]
        full_bull = result["levels"]["full_range_bull"]["price"]
        ext_bull = result["levels"]["ext_1236_bull"]["price"]
        # ext_1236 = full_range + 0.236*atr
        expected = round(full_bull + atr * 0.236, 4)
        assert abs(ext_bull - expected) < 1e-3
