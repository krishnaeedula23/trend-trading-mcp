import pandas as pd
import pytest

from api.indicators.swing.universe.filters import (
    stage1_price_liquidity,
    stage2_trend_base,
    stage3_fundamentals,
    stage4_relative_strength,
)


def _bars(ticker: str, price: float, volume: int = 1_000_000, days: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-03-01", periods=days, freq="B")
    return pd.DataFrame({
        "ticker": ticker,
        "date": dates,
        "close": price,
        "volume": volume,
    })


def test_stage1_passes_high_price_high_volume():
    df = _bars("AAPL", price=200.0, volume=10_000_000)   # $2B/day volume
    assert stage1_price_liquidity(df)


def test_stage1_fails_low_price():
    df = _bars("PENNY", price=3.0, volume=10_000_000)
    assert not stage1_price_liquidity(df)


def test_stage1_fails_low_dollar_volume():
    df = _bars("ILLIQ", price=200.0, volume=50_000)   # $10M/day
    assert not stage1_price_liquidity(df)


def test_stage1_fails_price_too_high():
    df = _bars("BRK", price=5_000.0, volume=100_000)
    assert not stage1_price_liquidity(df)


def test_stage2_passes_above_200sma_tight_range():
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = [100.0] * 180 + [200.0] * 40
    df = pd.DataFrame({"date": dates, "close": closes, "volume": 1_000_000})
    assert stage2_trend_base(df)


def test_stage2_fails_below_200sma():
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = [200.0] * 180 + [100.0] * 40
    df = pd.DataFrame({"date": dates, "close": closes, "volume": 1_000_000})
    assert not stage2_trend_base(df)


def test_stage2_fails_wide_range_no_base():
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = list(range(100, 300)) + [400.0] * 20
    df = pd.DataFrame({"date": dates, "close": closes, "volume": 1_000_000})
    assert not stage2_trend_base(df)


def test_stage3_passes_accelerating_growth():
    fundamentals = {"quarterly_revenue_yoy": [0.45, 0.38, 0.30, 0.22]}
    assert stage3_fundamentals(fundamentals)


def test_stage3_fails_below_threshold():
    fundamentals = {"quarterly_revenue_yoy": [0.20, 0.18, 0.15]}
    assert not stage3_fundamentals(fundamentals)


def test_stage3_fails_decelerating():
    fundamentals = {"quarterly_revenue_yoy": [0.30, 0.45, 0.50]}
    assert not stage3_fundamentals(fundamentals)


def test_stage3_fails_no_data():
    fundamentals = {}
    assert not stage3_fundamentals(fundamentals)


def test_stage4_passes_outperforms_qqq_63d():
    dates = pd.date_range("2026-01-01", periods=70, freq="B")
    ticker = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.5 for i in range(70)]})
    qqq = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.1 for i in range(70)]})
    assert stage4_relative_strength(ticker, qqq)


def test_stage4_fails_underperforms_qqq():
    dates = pd.date_range("2026-01-01", periods=70, freq="B")
    ticker = pd.DataFrame({"date": dates, "close": [100.0 - i * 0.1 for i in range(70)]})
    qqq = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.5 for i in range(70)]})
    assert not stage4_relative_strength(ticker, qqq)
