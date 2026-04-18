"""Tests for api.indicators.swing.setups.reversal_extension."""

import pandas as pd
import pytest

from api.indicators.swing.setups.reversal_extension import detect


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_bars(closes: list[float], vol_factor: float = 1.0) -> pd.DataFrame:
    """Build OHLCV bars with narrow intraday range (high=+0.2%, low=-0.2%).

    Keeping the intraday range small keeps Wilder's ATR small (~0.4 at price 100),
    which lets the EMA10-vs-close stretch condition pass even on moderate pullbacks.
    """
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c * 1.002 for c in closes],
            "low": [c * 0.998 for c in closes],
            "close": closes,
            "volume": [10_000_000] * len(closes),
        }
    )
    # Set last-bar volume to vol_factor × average of prior 20 bars
    avg_vol = float(df["volume"].iloc[-21:-1].mean())
    df.loc[df.index[-1], "volume"] = int(avg_vol * vol_factor)
    return df


def _happy_closes() -> list[float]:
    """240 bars: 230 flat at 100 then 10-bar declining finish.

    The final 10 bars provide:
    - price lower low (93.0 > ... > 92.7 monotone — current is the minimum)
    - large stretch of EMA10 above current close
    - weekly_base_low support (close ≈ weekly low, within 1%)

    Phase oscillator is monkeypatched in each test.
    """
    flat = [100.0] * 230
    tail = [100.0, 98.5, 97.0, 95.5, 94.5, 93.8, 93.3, 93.0, 92.8, 92.7]
    return flat + tail


def _divergent_osc(n: int) -> pd.Series:
    """Phase oscillator that is oversold and shows bullish divergence on last bar.

    First (n-10) bars: neutral (-20).
    Last 10 bars: drops then recovers — osc minimum is at bar -6 (-72), while
    current bar (-1) is at -52, which is ABOVE the prior min → divergence fires.
    """
    return pd.Series(
        [-20.0] * (n - 10) + [-20.0, -40.0, -60.0, -70.0, -72.0, -70.0, -65.0, -60.0, -55.0, -52.0]
    )


def _no_divergence_osc(n: int) -> pd.Series:
    """Phase oscillator that is oversold but has NO divergence (still falling).

    Last bar is the minimum of the 10-bar window — osc and price both at lows.
    """
    return pd.Series(
        [-20.0] * (n - 10) + [-20.0, -40.0, -55.0, -60.0, -65.0, -68.0, -70.0, -72.0, -74.0, -76.0]
    )


def _ctx(ticker: str = "AAPL") -> dict:
    return {"ticker": ticker, "prior_ideas": []}


def _qqq(n: int) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.0] * n,
            "volume": [10_000_000] * n,
        }
    )


# ---------------------------------------------------------------------------
# Test 1: Happy path — all 5 conditions fire → SetupHit returned
# ---------------------------------------------------------------------------

def test_happy_path_fires(monkeypatch):
    closes = _happy_closes()
    bars = _make_bars(closes, vol_factor=1.6)
    n = len(bars)

    osc = _divergent_osc(n)
    monkeypatch.setattr(
        "api.indicators.swing.setups.reversal_extension.phase_oscillator_daily",
        lambda b, **kw: osc,
    )

    hit = detect(bars, _qqq(n), _ctx())

    assert hit is not None
    assert hit.setup_kell == "reversal_extension"
    assert hit.cycle_stage == "reversal_extension"
    assert hit.ticker == "AAPL"
    assert hit.raw_score >= 3
    assert hit.detection_evidence["support_type"] == "weekly_low"
    assert hit.detection_evidence["phase_osc"] == pytest.approx(-52.0, abs=1e-3)
    assert hit.detection_evidence["volume_vs_20d_avg"] == pytest.approx(1.6, abs=0.01)


# ---------------------------------------------------------------------------
# Test 2: No divergence — osc also at its minimum on the last bar → None
# ---------------------------------------------------------------------------

def test_no_divergence_returns_none(monkeypatch):
    closes = _happy_closes()
    bars = _make_bars(closes, vol_factor=1.6)
    n = len(bars)

    osc = _no_divergence_osc(n)
    monkeypatch.setattr(
        "api.indicators.swing.setups.reversal_extension.phase_oscillator_daily",
        lambda b, **kw: osc,
    )

    hit = detect(bars, _qqq(n), _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 3: Far from any support — close far above all support levels → None
# ---------------------------------------------------------------------------

def test_far_from_support_returns_none(monkeypatch):
    # 240 bars: 230 flat at 100, then 10 bars RISING to 130 (far from all support)
    flat = [100.0] * 230
    tail = [100.0, 105.0, 110.0, 115.0, 118.0, 120.0, 123.0, 126.0, 128.0, 130.0]
    bars = _make_bars(flat + tail, vol_factor=1.6)
    n = len(bars)

    osc = _divergent_osc(n)
    monkeypatch.setattr(
        "api.indicators.swing.setups.reversal_extension.phase_oscillator_daily",
        lambda b, **kw: osc,
    )

    hit = detect(bars, _qqq(n), _ctx())
    assert hit is None


# ---------------------------------------------------------------------------
# Test 4: second_target is explicitly None on happy path
# ---------------------------------------------------------------------------

def test_second_target_is_none(monkeypatch):
    closes = _happy_closes()
    bars = _make_bars(closes, vol_factor=1.6)
    n = len(bars)

    osc = _divergent_osc(n)
    monkeypatch.setattr(
        "api.indicators.swing.setups.reversal_extension.phase_oscillator_daily",
        lambda b, **kw: osc,
    )

    hit = detect(bars, _qqq(n), _ctx())

    assert hit is not None
    assert hit.second_target is None
