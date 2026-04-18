import pandas as pd


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's Average True Range.

    True range = max(high-low, |high-prev_close|, |low-prev_close|).
    Smoothed with Wilder's EMA: alpha = 1/period, adjust=False.
    """
    high = bars["high"]
    low = bars["low"]
    close = bars["close"]
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
