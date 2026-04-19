# tests/swing/test_exhaustion_extension.py
import pandas as pd

from api.indicators.swing.setups.exhaustion_extension import (
    detect_exhaustion_extension,
    ExhaustionFlag,
)


def _bars(closes, volumes=None, highs=None, lows=None, opens=None):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": opens or [c * 0.995 for c in closes],
        "high": highs or [c * 1.01 for c in closes],
        "low": lows or [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes or [1_000_000] * n,
    })


def test_no_warning_when_price_normal():
    # Price glued to its 10-EMA, normal volume → no triggers
    closes = [100.0 + i * 0.1 for i in range(60)]
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=20)
    assert flags == ExhaustionFlag(kell_2nd_extension=False, climax_bar=False,
                                    far_above_10ema=False, weekly_air=False)


def test_kell_2nd_extension_triggers():
    # Two separate pokes > 1 ATR above 10-EMA since base breakout (idx 20)
    closes = [100.0] * 20 + [115.0, 108.0, 104.0, 102.0] + [103.0] * 10 + [120.0] + [104.0] * 25
    df = _bars(closes, volumes=[1_000_000] * 60)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=20)
    assert flags.kell_2nd_extension is True


def test_climax_bar_triggers_on_volume_and_upper_wick():
    closes = [100.0] * 40 + [100.0 + i for i in range(20)]     # trending up
    volumes = [1_000_000] * 59 + [3_000_000]                    # 3x surge on last bar
    highs = [c * 1.01 for c in closes[:59]] + [closes[-1] * 1.05]  # big upper wick
    lows = [c * 0.99 for c in closes[:59]] + [closes[-1] * 0.995]
    df = _bars(closes, volumes=volumes, highs=highs, lows=lows)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=40)
    assert flags.climax_bar is True


def test_heuristic_far_above_10ema():
    closes = [100.0] * 50 + [200.0]                            # massive gap above any 10-EMA
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=10)
    assert flags.far_above_10ema is True


def test_missing_base_breakout_idx_skips_kell_count():
    # When there's no recorded base breakout, Kell 2nd-extension is not counted,
    # but heuristics still run.
    closes = [100.0 + i * 0.1 for i in range(60)]
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=None)
    assert flags.kell_2nd_extension is False
