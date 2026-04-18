import pandas as pd

from api.indicators.common.moving_averages import ema, sma, weekly_resample
from api.indicators.common.atr import atr


def _daily_bars(n: int, close: float = 100.0, high: float = 101.0, low: float = 99.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-02", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1_000_000,
    })


# ── EMA ───────────────────────────────────────────────────────────────────────

def test_ema_matches_pandas():
    bars = _daily_bars(30)
    result = ema(bars, 10)
    expected = bars["close"].ewm(span=10, adjust=False).mean()
    pd.testing.assert_series_equal(result, expected)


def test_ema_length_equals_input():
    bars = _daily_bars(20)
    assert len(ema(bars, 5)) == len(bars)


# ── SMA ───────────────────────────────────────────────────────────────────────

def test_sma_known_value():
    # close = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], sma(5) last value = (6+7+8+9+10)/5 = 8.0
    bars = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "close": list(range(1, 11)),
    })
    result = sma(bars, 5)
    assert result.iloc[-1] == 8.0


def test_sma_first_values_nan():
    bars = _daily_bars(10)
    result = sma(bars, 5)
    assert result.iloc[:4].isna().all()
    assert not pd.isna(result.iloc[4])


# ── ATR ───────────────────────────────────────────────────────────────────────

def test_atr_stable_bars():
    # high=101, low=99, close=100 → TR always 2.0 → ATR stabilizes to 2.0
    bars = _daily_bars(30, close=100.0, high=101.0, low=99.0)
    result = atr(bars, period=14)
    assert abs(float(result.iloc[-1]) - 2.0) < 1e-6


def test_atr_length_equals_input():
    bars = _daily_bars(20)
    assert len(atr(bars)) == len(bars)


# ── weekly_resample ───────────────────────────────────────────────────────────

def test_weekly_resample_two_weeks():
    # Mon 2026-01-05 .. Fri 2026-01-09 (week 1) + Mon 2026-01-12 .. Fri 2026-01-16 (week 2)
    dates = pd.bdate_range("2026-01-05", periods=10)
    bars = pd.DataFrame({
        "date": dates,
        "open": 100.0,
        "high": [101.0, 102.0, 100.5, 103.0, 101.5,  # week 1
                 102.0, 104.0, 101.0, 103.5, 102.5],  # week 2
        "low": 99.0,
        "close": 100.0,
        "volume": 1_000,
    })
    weekly = weekly_resample(bars)
    assert len(weekly) == 2


def test_weekly_resample_volume_summed():
    dates = pd.bdate_range("2026-01-05", periods=10)
    bars = pd.DataFrame({
        "date": dates,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1_000,
    })
    weekly = weekly_resample(bars)
    assert weekly["volume"].iloc[0] == 5_000


def test_weekly_resample_high_is_max():
    dates = pd.bdate_range("2026-01-05", periods=5)  # one week
    highs = [101.0, 103.0, 102.0, 104.0, 100.5]
    bars = pd.DataFrame({
        "date": dates,
        "open": 100.0,
        "high": highs,
        "low": 99.0,
        "close": 100.0,
        "volume": 1_000,
    })
    weekly = weekly_resample(bars)
    assert weekly["high"].iloc[0] == 104.0
