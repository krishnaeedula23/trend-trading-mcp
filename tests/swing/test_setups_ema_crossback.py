"""Tests for api.indicators.swing.setups.ema_crossback."""

import pandas as pd

from api.indicators.swing.setups import synth_bars
from api.indicators.swing.setups.ema_crossback import detect


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _base_closes(n: int = 70) -> list[float]:
    """Mildly oscillating closes to give ATR ~2.0, EMA converging near 100."""
    pattern = [99.0, 101.0, 100.0, 100.5, 99.5]
    return [pattern[i % len(pattern)] for i in range(n)]


def _happy_bars(vol_ratio: float = 0.6, override_close: float | None = None):
    """Build bars where all 4 EMA Crossback conditions fire.

    - 70 bars of mild oscillation → ATR ~2.1, EMA10/EMA20 converge near 100.15.
    - Last bar: close = 100.3 (within 0.5*ATR ~1.06 of EMA10 ~100.15), low = 100.2
      (strictly above EMA10).
    - Volume set to vol_ratio × 20-bar average.

    EMA10 on these bars empirically lands at ~100.148, so low=100.2 > EMA10.
    """
    closes = _base_closes(70)
    last_close = override_close if override_close is not None else 100.3
    closes[-1] = last_close
    df = synth_bars(closes=closes, volume=10_000_000)

    # Set last bar low explicitly above the EMA10 (~100.148)
    df.loc[df.index[-1], "low"] = 100.2

    # Adjust volume: last bar = vol_ratio × average of prior 20 bars
    avg_vol = float(df["volume"].iloc[-21:-1].mean())
    df.loc[df.index[-1], "volume"] = int(avg_vol * vol_ratio)

    return df


def _ctx_with_prior(bars: pd.DataFrame, ticker: str = "AAPL"):
    """ctx with a wedge_pop prior idea whose detected_at falls within bars[-30:]."""
    # Use a date 10 bars from the end — guaranteed within last-30-bar window
    detected_date = str(bars["date"].iloc[-10].date())
    return {
        "ticker": ticker,
        "prior_ideas": [{"setup_kell": "wedge_pop", "detected_at": detected_date}],
    }


def _ctx_empty(ticker: str = "AAPL"):
    return {"ticker": ticker, "prior_ideas": []}


def _qqq(n: int):
    return synth_bars(closes=[100.0] * n)


# ---------------------------------------------------------------------------
# Test 1: Happy path — all 4 conditions pass → fires
# ---------------------------------------------------------------------------

def test_happy_path_fires():
    bars = _happy_bars(vol_ratio=0.6)
    qqq  = _qqq(len(bars))
    ctx  = _ctx_with_prior(bars)
    hit  = detect(bars, qqq, ctx)

    assert hit is not None
    assert hit.setup_kell  == "ema_crossback"
    assert hit.cycle_stage == "ema_crossback"
    assert hit.ticker      == "AAPL"
    assert hit.raw_score   >= 3
    assert hit.second_target is None
    assert hit.detection_evidence["respected_ema"] in ("ema10", "ema20")
    assert "prior_wedge_at" in hit.detection_evidence


# ---------------------------------------------------------------------------
# Test 2: No prior Wedge Pop → None
# ---------------------------------------------------------------------------

def test_no_prior_wedge_pop_returns_none():
    bars = _happy_bars(vol_ratio=0.6)
    qqq  = _qqq(len(bars))
    hit  = detect(bars, qqq, _ctx_empty())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 3: Close below respected EMA → None
#
# Strategy: force close well below EMA (90.0 vs EMA ~100).
# dist = |90 - 100| = 10; half_atr ~1.0 → fails cond 2 (too far away).
# Also confirms cond 3 would block it even if cond 2 were relaxed.
# ---------------------------------------------------------------------------

def test_close_below_respected_ema_returns_none():
    bars = _happy_bars(vol_ratio=0.6)
    qqq  = _qqq(len(bars))
    ctx  = _ctx_with_prior(bars)

    # Push close well below EMA so dist > 0.5*ATR — cond 2 fails
    bars.loc[bars.index[-1], "close"] = 90.0
    bars.loc[bars.index[-1], "low"]   = 89.0   # also below EMA

    hit = detect(bars, qqq, ctx)
    assert hit is None


# ---------------------------------------------------------------------------
# Test 4: Volume not drying up (ratio = 1.0) → None
# ---------------------------------------------------------------------------

def test_high_volume_returns_none():
    bars = _happy_bars(vol_ratio=1.0)
    qqq  = _qqq(len(bars))
    ctx  = _ctx_with_prior(bars)
    hit  = detect(bars, qqq, ctx)
    assert hit is None
