"""
Shared synthetic OHLCV fixtures for Satyland indicator tests.

All fixtures build deterministic pandas DataFrames with no external I/O.
No containers (postgres/redis) are required for the satyland test suite.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure project root is on the path so `api.*` imports resolve
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Trend fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """
    50 bars of linearly increasing prices.

    close[i] = 90 + i  (90 → 139)
    high  = close + 0.5
    low   = close - 0.5
    open  = previous close  (open[0] = 90)

    ATR ≈ 1.0 (H−L = 1 dominates; no large gaps).
    EMA8 > EMA21 > EMA48, close > EMA8 → bullish ribbon.
    """
    n = 50
    closes = [90.0 + i for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = [90.0] + closes[:-1]
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )


@pytest.fixture
def trending_down_df() -> pd.DataFrame:
    """
    50 bars of linearly decreasing prices.

    close[i] = 139 − i  (139 → 90)
    EMA8 < EMA21 < EMA48, close < EMA8 → bearish ribbon.
    """
    n = 50
    closes = [139.0 - i for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = [139.0] + closes[:-1]
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )


@pytest.fixture
def flat_df() -> pd.DataFrame:
    """
    50 bars of completely flat prices (all OHLC = 100.0).

    ATR → 0, stdev → 0.
    Tests divide-by-zero guards in atr_covered_pct and phase oscillator.
    """
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [100.0] * n,
            "low": [100.0] * n,
            "close": [100.0] * n,
        },
        index=idx,
    )


@pytest.fixture
def atr_daily_df() -> pd.DataFrame:
    """
    Daily df engineered for known ATR and price-position assertions.

    Bars 0..48 (n-2): O=C=100.0, H=101.0, L=99.0  → TR=2.0 every bar → ATR≈2.0
    Bar 49  (today):  C=102.0, H=103.0, L=101.0
      - PDC (iloc[-2].close) = 100.0
      - ATR (iloc[-2])       ≈ 2.0  (Wilder-settled previous bar)
      - daily_range          = 2.0  (103−101)
      - atr_covered_pct      ≈ 100% → atr_status = "red"
      - call_trigger         = 100 + 0.236×2 = 100.472
      - full_range_bull       = 100 + 1.0×2  = 102.0
      - current_price        = 102.0 → price_position = "above_full_range"
    """
    n = 50
    closes = [100.0] * (n - 1) + [102.0]
    highs = [101.0] * (n - 1) + [103.0]
    lows = [99.0] * (n - 1) + [101.0]
    opens = [100.0] * n
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )
