"""Daily-timeframe phase oscillator proxy for the Kell+Saty swing system.

This is a **simplified daily-TF proxy** — NOT a faithful port of the Pine Script
intraday oscillator in `api/indicators/satyland/phase_oscillator.py`, which is the
authoritative Saty version.  If higher fidelity is needed (e.g. volume-weighted
phases, intraday reversal signals), refactor to reuse or extend that module.

Normalization approach
----------------------
MACD signal line (fast_ema - slow_ema, smoothed by signal-period EMA) is divided
by the rolling standard deviation of the close over `slow` periods, then scaled by
100.  This keeps the oscillator in a roughly [-100, +100] range for typical price
series without requiring an explicit ATR call.

    osc = (macd_signal / rolling_std_slow * 100).clip(-200, 200)
"""
import pandas as pd


def phase_oscillator_daily(
    bars: pd.DataFrame,
    fast: int = 8,
    slow: int = 21,
    signal: int = 9,
) -> pd.Series:
    """Simplified daily-TF phase oscillator proxy.

    Parameters
    ----------
    bars:   daily OHLCV DataFrame with a 'close' column.
    fast:   span for the fast EMA.
    slow:   span for the slow EMA.
    signal: span for the signal EMA applied to the MACD line.

    Returns
    -------
    pd.Series, same length as bars, normalized to roughly [-100, +100].
    """
    close = bars["close"]
    macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    rolling_std = close.rolling(slow).std()
    # avoid division by zero on flat series; fillna keeps length intact
    osc = (macd_signal / rolling_std.replace(0, float("nan")) * 100).clip(-200, 200)
    return osc.reset_index(drop=True)
