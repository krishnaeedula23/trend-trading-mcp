import pandas as pd


def ema(bars: pd.DataFrame, period: int) -> pd.Series:
    """Exponential moving average of close prices (pandas EMA, adjust=False)."""
    return bars["close"].ewm(span=period, adjust=False).mean()


def sma(bars: pd.DataFrame, period: int) -> pd.Series:
    """Simple moving average of close prices. First period-1 values are NaN."""
    return bars["close"].rolling(period).mean()


def weekly_resample(daily_bars: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV bars to Friday-anchored weekly bars."""
    weekly = (
        daily_bars.resample("W-FRI", on="date")
        .agg(open=("open", "first"), high=("high", "max"),
             low=("low", "min"), close=("close", "last"),
             volume=("volume", "sum"))
        .dropna(subset=["open"])
        .reset_index(drop=True)
    )
    return weekly
