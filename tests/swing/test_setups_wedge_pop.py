"""Tests for api.indicators.swing.setups.wedge_pop."""

import pytest

from api.indicators.swing.setups import synth_bars
from api.indicators.swing.setups.wedge_pop import detect


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _happy_bars(vol_ratio: float = 1.3):
    """Build bars where all 6 Wedge Pop conditions fire.

    Structure:
      - 35 flat bars at 100.0 (EMA10/EMA20 converge; volume baseline)
      - Reclaim bar (bar 35): close = 103.0, 1-bar pop above both EMAs

    The window bars[-16:-1] have manually overridden highs that descend (108→94)
    and lows that descend (87.8→92), giving:
      - lower-high pairs in window  (cond 3b)
      - current low > window min low (cond 3a)
      - ATR is elevated from the override → slope/spread thresholds stay loose (conds 1,2)
    """
    closes = [100.0] * 35 + [103.0]
    df = synth_bars(closes=closes)

    # Inject descending channel into window (bars 20..34, i.e. bars[-16:-1])
    window_highs = [108.0 - i for i in range(15)]         # 108 → 94
    window_lows  = [92.0 - i * 0.3 for i in range(15)]    # 92.0 → 87.8
    df.loc[df.index[20:35], "high"] = window_highs
    df.loc[df.index[20:35], "low"]  = window_lows

    # Current bar: low comfortably above window min (87.8)
    df.loc[df.index[-1], "low"]    = 102.0 * 0.99

    # Volume spike
    avg_vol = 10_000_000
    df.loc[df.index[-1], "volume"] = int(avg_vol * vol_ratio)

    return df


def _qqq_flat(n: int):
    """Flat QQQ bars at 100.0 — ticker's RS will be positive if ticker went up."""
    return synth_bars(closes=[100.0] * n)


def _ctx(ticker: str = "NVDA"):
    return {"ticker": ticker, "universe_extras": {}, "prior_ideas": [], "today": None}


# ---------------------------------------------------------------------------
# Test 1: Happy path — should fire
# ---------------------------------------------------------------------------

def test_happy_path_fires():
    bars = _happy_bars(vol_ratio=1.3)
    qqq  = _qqq_flat(len(bars))
    hit  = detect(bars, qqq, _ctx("NVDA"))

    assert hit is not None
    assert hit.setup_kell    == "wedge_pop"
    assert hit.cycle_stage   == "wedge_pop"
    assert hit.ticker        == "NVDA"
    assert hit.raw_score     >= 3
    assert hit.second_target is None


# ---------------------------------------------------------------------------
# Test 2: Low volume — returns None
# ---------------------------------------------------------------------------

def test_low_volume_returns_none():
    bars = _happy_bars(vol_ratio=0.9)
    qqq  = _qqq_flat(len(bars))
    hit  = detect(bars, qqq, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 3: No prior descending structure — returns None
# ---------------------------------------------------------------------------

def test_no_descending_structure_returns_none():
    """Take the happy-path base and override only window highs to be monotonically
    rising, so no lower-high pair exists in the last 15 bars. All other conditions
    still hold — isolates the descending-structure guard."""
    bars = _happy_bars(vol_ratio=1.3)
    qqq  = _qqq_flat(len(bars))
    bars.loc[bars.index[20:35], "high"] = [101.0 + i for i in range(15)]  # monotonic up
    hit = detect(bars, qqq, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 4: Stop price calculation
# ---------------------------------------------------------------------------

def test_stop_price_uses_higher_of_reclaim_low_and_consolidation_min():
    """Reclaim-bar low = 95, prior 3-bar lows = [93, 94, 96] → stop = max(95, 93) = 95."""
    bars = _happy_bars(vol_ratio=1.3)
    qqq  = _qqq_flat(len(bars))

    # Override last 4 lows: bars[-4], [-3], [-2] = prior; bars[-1] = current
    bars.loc[bars.index[-4], "low"] = 93.0
    bars.loc[bars.index[-3], "low"] = 94.0
    bars.loc[bars.index[-2], "low"] = 96.0
    bars.loc[bars.index[-1], "low"] = 95.0

    hit = detect(bars, qqq, _ctx())
    assert hit is not None
    assert hit.stop_price == pytest.approx(95.0)


# ---------------------------------------------------------------------------
# Test 5: detection_evidence keys
# ---------------------------------------------------------------------------

def test_detection_evidence_keys():
    bars = _happy_bars(vol_ratio=1.3)
    qqq  = _qqq_flat(len(bars))
    hit  = detect(bars, qqq, _ctx())

    assert hit is not None
    assert set(hit.detection_evidence.keys()) == {
        "ema10",
        "ema20",
        "ema10_slope",
        "rs_vs_qqq_10d",
        "volume_vs_20d_avg",
    }
