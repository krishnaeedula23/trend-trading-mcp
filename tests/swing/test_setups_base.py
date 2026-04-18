"""Tests for api.indicators.swing.setups.base."""

import pytest

from api.indicators.swing.setups import (
    SetupHit,
    volume_vs_avg,
    prior_swing_high,
    prior_swing_low,
    synth_bars,
)


# ---------------------------------------------------------------------------
# SetupHit
# ---------------------------------------------------------------------------

def test_setup_hit_fields():
    hit = SetupHit(
        ticker="NVDA",
        setup_kell="wedge_pop",
        cycle_stage="stage2",
        entry_zone=(100.0, 105.0),
        stop_price=95.0,
        first_target=115.0,
        second_target=130.0,
        detection_evidence={"ema_diff": 1.5},
        raw_score=4,
    )
    assert hit.ticker == "NVDA"
    assert hit.setup_kell == "wedge_pop"
    assert hit.entry_zone == (100.0, 105.0)
    assert hit.first_target == 115.0
    assert hit.second_target == 130.0
    assert hit.raw_score == 4
    assert hit.detection_evidence == {"ema_diff": 1.5}


def test_setup_hit_optional_targets_none():
    hit = SetupHit(
        ticker="AAPL",
        setup_kell="ema_crossback",
        cycle_stage="stage1",
        entry_zone=(150.0, 152.0),
        stop_price=145.0,
        first_target=None,
        second_target=None,
        detection_evidence={},
        raw_score=2,
    )
    assert hit.first_target is None
    assert hit.second_target is None


# ---------------------------------------------------------------------------
# synth_bars
# ---------------------------------------------------------------------------

def test_synth_bars_closes():
    df = synth_bars(closes=[100.0, 101.0, 102.0])
    assert len(df) == 3
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert df["high"].iloc[0] == pytest.approx(101.0)
    assert df["low"].iloc[0] == pytest.approx(99.0)
    assert df["open"].iloc[0] == df["close"].iloc[0]


def test_synth_bars_days_flat():
    """synth_bars(days=5) produces 5 rows of flat closes at 100.0."""
    df = synth_bars(days=5)
    assert len(df) == 5
    assert all(df["close"] == 100.0)


def test_synth_bars_both_consistent():
    df = synth_bars(days=3, closes=[50.0, 51.0, 52.0])
    assert len(df) == 3
    assert df["close"].tolist() == [50.0, 51.0, 52.0]


def test_synth_bars_both_inconsistent_raises():
    with pytest.raises(AssertionError):
        synth_bars(days=4, closes=[50.0, 51.0, 52.0])


def test_synth_bars_neither_raises():
    with pytest.raises(ValueError):
        synth_bars()


# ---------------------------------------------------------------------------
# volume_vs_avg
# ---------------------------------------------------------------------------

def _vol_bars(prior_vol: float, current_vol: float, n: int = 20):
    """Build bars where the prior `n` bars have `prior_vol` and current = `current_vol`."""
    closes = [100.0] * (n + 1)
    df = synth_bars(closes=closes)
    df["volume"] = [int(prior_vol)] * n + [int(current_vol)]
    return df


def test_volume_vs_avg_two_x():
    df = _vol_bars(prior_vol=1_000_000, current_vol=2_000_000, n=20)
    assert volume_vs_avg(df, lookback=20) == pytest.approx(2.0)


def test_volume_vs_avg_half():
    df = _vol_bars(prior_vol=2_000_000, current_vol=1_000_000, n=20)
    assert volume_vs_avg(df, lookback=20) == pytest.approx(0.5)


def test_volume_vs_avg_insufficient_data():
    df = synth_bars(closes=[100.0] * 5)
    with pytest.raises(ValueError, match="at least"):
        volume_vs_avg(df, lookback=20)


# ---------------------------------------------------------------------------
# prior_swing_high / prior_swing_low
# ---------------------------------------------------------------------------

def _price_bars(highs: list[float], lows: list[float]):
    """Build a bar DataFrame with explicit high/low overrides."""
    closes = [100.0] * len(highs)
    df = synth_bars(closes=closes)
    df["high"] = highs
    df["low"] = lows
    return df


def test_prior_swing_high():
    highs = [10.0, 12.0, 15.0, 11.0, 9.0, 13.0]
    lows  = [8.0,  9.0,  12.0, 8.0,  7.0, 10.0]
    df = _price_bars(highs, lows)
    # lookback=5: bars[-6:-1] = highs[0:5] = [10, 12, 15, 11, 9] → max = 15
    result = prior_swing_high(df, lookback=5)
    assert result == pytest.approx(15.0)


def test_prior_swing_low():
    highs = [10.0, 12.0, 15.0, 11.0, 9.0, 13.0]
    lows  = [8.0,  9.0,  12.0, 8.0,  7.0, 10.0]
    df = _price_bars(highs, lows)
    # lookback=5: bars[-6:-1] = lows[0:5] = [8, 9, 12, 8, 7] → min = 7
    result = prior_swing_low(df, lookback=5)
    assert result == pytest.approx(7.0)


def test_prior_swing_high_insufficient():
    df = synth_bars(closes=[100.0] * 3)
    assert prior_swing_high(df, lookback=60) is None


def test_prior_swing_low_insufficient():
    df = synth_bars(closes=[100.0] * 3)
    assert prior_swing_low(df, lookback=60) is None
