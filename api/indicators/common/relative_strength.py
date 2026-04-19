import numpy as np
import pandas as pd


def rs_vs_benchmark(
    ticker_bars: pd.DataFrame,
    benchmark_bars: pd.DataFrame,
    lookback_days: int = 20,
) -> pd.Series:
    """Log-return spread of ticker vs benchmark over a rolling lookback window.

    Aligns on the `date` column when present (so gaps/halts on either side don't
    produce garbage). Falls back to positional alignment when neither frame has
    a `date` column. First `lookback_days` values are NaN.
    """
    if "date" in ticker_bars.columns and "date" in benchmark_bars.columns:
        t = ticker_bars[["date", "close"]].rename(columns={"close": "t_close"})
        b = benchmark_bars[["date", "close"]].rename(columns={"close": "b_close"})
        merged = pd.merge(t, b, on="date", how="inner").sort_values("date")
        ticker_close = merged["t_close"].reset_index(drop=True)
        bench_close = merged["b_close"].reset_index(drop=True)
    else:
        n = min(len(ticker_bars), len(benchmark_bars))
        ticker_close = ticker_bars["close"].iloc[:n].reset_index(drop=True)
        bench_close = benchmark_bars["close"].iloc[:n].reset_index(drop=True)

    return (
        np.log(ticker_close / ticker_close.shift(lookback_days))
        - np.log(bench_close / bench_close.shift(lookback_days))
    )
