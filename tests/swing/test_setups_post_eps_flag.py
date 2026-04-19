"""Tests for api.indicators.swing.setups.post_eps_flag."""

import pandas as pd
import pytest

from api.indicators.swing.setups import synth_bars
from api.indicators.swing.setups.post_eps_flag import detect


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _ctx(ticker: str = "NVDA"):
    return {"ticker": ticker}


def _happy_bars(gap_pct: float = 0.07, vol_ratio: float = 0.5, wide_consol: bool = False):
    """Build bars that satisfy all 5 conditions.

    Structure:
      - 30 steady uptrend bars (close: 100 → 114.5) to seed 10-EMA
      - Gap bar (index 30): open = prev_close * (1 + gap_pct), close = open - 0.7
      - 5 tight consolidation bars post-gap
      - Volume: all bars at 10M, last bar at 10M * vol_ratio
    """
    closes_uptrend = [100.0 + i * 0.5 for i in range(30)]  # 100 … 114.5
    prev_close = closes_uptrend[-1]  # 114.5

    # Gap bar
    gap_open = prev_close * (1 + gap_pct)  # e.g. 114.5 * 1.07 = 122.515
    gap_close = round(gap_open - 0.7, 2)    # e.g. 121.815

    # 5 tight consolidation bars (range ~1.5% each unless wide_consol)
    if wide_consol:
        consol_closes = [gap_close + x for x in [0.5, 0.2, 0.3, 0.1, -0.2]]
    else:
        consol_closes = [gap_close + x for x in [0.5, 0.2, 0.3, 0.1, -0.2]]

    all_closes = closes_uptrend + [gap_close] + consol_closes
    n = len(all_closes)

    dates = pd.date_range("2026-01-01", periods=n, freq="B")

    # Build OHLCV manually for precise control
    opens = list(all_closes)
    opens[30] = gap_open  # gap bar: open is above prev close

    if wide_consol:
        # Force daily range > 4% on consolidation bars
        highs = [c * 1.01 for c in all_closes]
        lows  = [c * 0.99 for c in all_closes]
        for i in range(31, n):
            highs[i] = all_closes[i] * 1.03   # 6% range → fails < 4% check
            lows[i]  = all_closes[i] * 0.97
    else:
        # Tight: range ~1.5%
        highs = [c * 1.01 for c in all_closes]
        lows  = [c * 0.99 for c in all_closes]
        for i in range(31, n):
            highs[i] = all_closes[i] * 1.0075
            lows[i]  = all_closes[i] * 0.9925

    vol = [10_000_000] * n
    vol[-1] = int(10_000_000 * vol_ratio)  # drying up on last bar

    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": all_closes,
        "volume": vol,
    })
    return df


# ---------------------------------------------------------------------------
# Test 1: Happy path — should fire
# ---------------------------------------------------------------------------

def test_happy_path_fires():
    """7% gap 5 bars ago, 5 tight bars (<1.5% range), all above 10-EMA, volume 0.5x."""
    bars = _happy_bars(gap_pct=0.07, vol_ratio=0.5)
    hit = detect(bars, bars, _ctx("NVDA"))

    assert hit is not None
    assert hit.setup_kell == "post_eps_flag"
    assert hit.cycle_stage == "post_eps_flag"
    assert hit.ticker == "NVDA"
    assert hit.second_target is None

    # entry_zone = (close, close * 1.02)
    cur_close = bars["close"].iloc[-1]
    assert hit.entry_zone[0] == pytest.approx(cur_close)
    assert hit.entry_zone[1] == pytest.approx(cur_close * 1.02, rel=1e-4)

    # detection_evidence keys
    assert set(hit.detection_evidence.keys()) == {
        "gap_pct",
        "gap_bars_ago",
        "consolidation_bars",
        "consolidation_range_pct",
        "volume_vs_20d_avg",
    }

    ev = hit.detection_evidence
    assert ev["gap_pct"] >= 0.05
    assert ev["consolidation_bars"] == 5
    assert ev["gap_bars_ago"] == 5
    assert ev["volume_vs_20d_avg"] == pytest.approx(0.5, rel=0.1)


def test_happy_path_raw_score():
    """Big gap (>8%) and 5+ consolidation bars → score 5."""
    bars = _happy_bars(gap_pct=0.10, vol_ratio=0.5)
    hit = detect(bars, bars, _ctx())
    assert hit is not None
    assert hit.raw_score == 5  # 3 base + 1 big gap + 1 consol >= 5


def test_happy_path_small_gap_score():
    """7% gap and 5 consolidation bars → score 4 (no big gap bonus, yes consol bonus)."""
    bars = _happy_bars(gap_pct=0.07, vol_ratio=0.5)
    hit = detect(bars, bars, _ctx())
    assert hit is not None
    assert hit.raw_score == 4  # 3 base + 0 big gap + 1 consol


# ---------------------------------------------------------------------------
# Test 2: No gap in last 10 bars → None
# ---------------------------------------------------------------------------

def test_no_gap_returns_none():
    """Flat uptrend bars with no gap-up > 5% → None."""
    bars = synth_bars(closes=[100.0 + i * 0.3 for i in range(40)])
    hit = detect(bars, bars, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 3: Consolidation too wide → None
# ---------------------------------------------------------------------------

def test_consolidation_too_wide_returns_none():
    """Post-gap daily range ~6% (>4%) → fails tightness check → None."""
    bars = _happy_bars(gap_pct=0.07, vol_ratio=0.5, wide_consol=True)
    hit = detect(bars, bars, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 4: Volume not drying up → None
# ---------------------------------------------------------------------------

def test_high_volume_returns_none():
    """Current bar volume is 1.2x average → vol_ratio >= 0.8 → None."""
    bars = _happy_bars(gap_pct=0.07, vol_ratio=1.2)
    hit = detect(bars, bars, _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 5: stop_price and first_target sanity
# ---------------------------------------------------------------------------

def test_stop_and_target_values():
    """stop_price = min(consol_low, ema10) and first_target = close + consol_height."""
    bars = _happy_bars(gap_pct=0.07, vol_ratio=0.5)
    hit = detect(bars, bars, _ctx())
    assert hit is not None

    # stop_price must be below current close
    assert hit.stop_price < bars["close"].iloc[-1]
    # first_target must be above current close
    assert hit.first_target > bars["close"].iloc[-1]


# ---------------------------------------------------------------------------
# Test 6: Fewer than 3 consolidation bars → None
# ---------------------------------------------------------------------------

def test_too_few_consolidation_bars_returns_none():
    """Gap bar is only 2 bars ago — only 2 consolidation bars → None."""
    closes_uptrend = [100.0 + i * 0.5 for i in range(30)]
    prev_close = closes_uptrend[-1]
    gap_open = prev_close * 1.07
    gap_close = round(gap_open - 0.7, 2)
    # Only 2 tight bars after gap
    consol_closes = [gap_close + 0.5, gap_close + 0.2]
    all_closes = closes_uptrend + [gap_close] + consol_closes
    n = len(all_closes)

    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    opens = list(all_closes)
    opens[30] = gap_open
    highs = [c * 1.0075 for c in all_closes]
    lows = [c * 0.9925 for c in all_closes]
    vol = [10_000_000] * n
    vol[-1] = 5_000_000

    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": all_closes,
        "volume": vol,
    })
    hit = detect(df, df, _ctx())
    assert hit is None
