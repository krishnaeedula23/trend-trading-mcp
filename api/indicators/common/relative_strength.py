import numpy as np
import pandas as pd


def rs_vs_benchmark(
    ticker_bars: pd.DataFrame,
    benchmark_bars: pd.DataFrame,
    lookback_days: int = 20,
) -> pd.Series:
    """Log-return spread of ticker vs benchmark over a rolling lookback window.

    Returns a Series of the same length as the shorter input.
    First lookback_days values will be NaN.
    """
    n = min(len(ticker_bars), len(benchmark_bars))
    ticker_close = ticker_bars["close"].iloc[:n]
    bench_close = benchmark_bars["close"].iloc[:n]
    return (
        np.log(ticker_close / ticker_close.shift(lookback_days))
        - np.log(bench_close / bench_close.shift(lookback_days))
    ).reset_index(drop=True)
