"""Tests for api.indicators.swing.setups.base_n_break."""

import pytest

from api.indicators.swing.setups import synth_bars
from api.indicators.swing.setups.base_n_break import detect


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_bars(
    n_warmup: int = 10,
    n_base: int = 40,
    base_val: float = 102.0,
    breakout_close: float = 106.0,
    vol_ratio: float = 1.6,
):
    """Build bars: n_warmup flat at 100 + n_base flat at base_val + 1 breakout bar.

    Warm-up at 100 so EMAs start below base_val. The flat base at 102 means
    every base close (102) is strictly above the EMA (which rises from ~100 toward
    102 asymptotically). Tightness = ~2% (well within 15%). Breakout at 106 >
    base_high (~103.02, i.e. 102 * 1.01).
    """
    warmup = [100.0] * n_warmup
    base_closes = [base_val] * n_base
    closes = warmup + base_closes + [breakout_close]

    df = synth_bars(closes=closes, volume=10_000_000)

    # Set breakout bar volume to vol_ratio × prior-20-bar average
    avg_vol = float(df["volume"].iloc[-21:-1].mean())
    df.loc[df.index[-1], "volume"] = int(avg_vol * vol_ratio)

    return df


def _ctx(ticker: str = "AAPL") -> dict:
    return {"ticker": ticker, "prior_ideas": [], "universe_extras": {}, "today": None}


# ---------------------------------------------------------------------------
# Test 1: Happy path — all 5 rules pass → fires
# ---------------------------------------------------------------------------

def test_happy_path_fires():
    bars = _make_bars()
    hit = detect(bars, None, _ctx("AAPL"))

    assert hit is not None
    assert hit.setup_kell == "base_n_break"
    assert hit.cycle_stage == "base_n_break"
    assert hit.ticker == "AAPL"
    assert hit.second_target is None

    # first_target ≈ close + (base_high - base_low)
    base_high = hit.detection_evidence["base_high"]
    base_low = hit.detection_evidence["base_low"]
    cur_close = float(bars["close"].iloc[-1])
    expected_target = cur_close + (base_high - base_low)
    assert hit.first_target == pytest.approx(expected_target, abs=0.01)


# ---------------------------------------------------------------------------
# Test 2: Base violates MA (one bar close < ema20) → None
# ---------------------------------------------------------------------------

def test_base_ma_violation_returns_none():
    """Inject a base bar with close below ema20 — isolates Rule 3."""
    bars = _make_bars()
    # Force the midpoint of the base to have a very low close
    # Base occupies bars[10:-1], midpoint roughly bars[10+20]=bars[30]
    bars.loc[bars.index[30], "close"] = 85.0
    hit = detect(bars, None, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 3: Breakout without volume (ratio 1.2 < 1.5) → None
# ---------------------------------------------------------------------------

def test_low_volume_returns_none():
    bars = _make_bars(vol_ratio=1.2)
    hit = detect(bars, None, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 4: Base too short (< 25 bars of data total) → None
# ---------------------------------------------------------------------------

def test_too_few_bars_returns_none():
    """Only 20 bars total — base window would be < 25, must return None."""
    bars = _make_bars(n_warmup=0, n_base=19, breakout_close=105.0)
    # 20 bars: 19 base + 1 breakout
    assert len(bars) == 20
    hit = detect(bars, None, _ctx())
    assert hit is None
