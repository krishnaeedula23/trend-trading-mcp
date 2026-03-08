"""Unit tests for market monitor breadth computation functions.

Tests _compute_breadth_scans and _compute_theme_tracker using synthetic
DataFrames that match the yfinance MultiIndex format. No HTTP endpoints,
no Supabase, no external I/O.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on the path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from api.endpoints.market_monitor import (
    BREADTH_SCANS,
    THEME_PERIODS,
    _compute_breadth_scans,
    _compute_theme_tracker,
)


# ---------------------------------------------------------------------------
# Helpers to build yfinance-style MultiIndex DataFrames
# ---------------------------------------------------------------------------


def _make_multiindex_df(
    ticker_data: dict[str, dict[str, list[float]]],
    n_days: int = 80,
    start_date: str = "2024-01-01",
) -> pd.DataFrame:
    """Build a DataFrame matching yf.download MultiIndex format.

    Args:
        ticker_data: ``{"AAPL": {"Close": [...], "Volume": [...]}, ...}``
            Each list must have length ``n_days``.
        n_days: Number of trading days.
        start_date: Start date for the index.

    Returns:
        DataFrame with MultiIndex columns ``(Price, Ticker)``.
    """
    idx = pd.bdate_range(start_date, periods=n_days)
    arrays: dict[tuple[str, str], list[float]] = {}

    for ticker, cols in ticker_data.items():
        for price_field, values in cols.items():
            arrays[(price_field, ticker)] = values

    columns = pd.MultiIndex.from_tuples(list(arrays.keys()), names=["Price", "Ticker"])
    return pd.DataFrame(arrays, index=idx, columns=columns)


def _constant_series(value: float, n: int) -> list[float]:
    """Return a list of ``n`` identical values."""
    return [value] * n


def _ramp_series(start: float, end: float, n: int) -> list[float]:
    """Return a linearly spaced list from ``start`` to ``end``."""
    return list(np.linspace(start, end, n))


# ---------------------------------------------------------------------------
# Tests for _compute_breadth_scans
# ---------------------------------------------------------------------------


class TestComputeBreadthScans:
    """Tests for the pure breadth scan computation."""

    def test_returns_all_10_scan_keys(self):
        """Result dict must contain all 10 scan keys."""
        n = 80
        df = _make_multiindex_df(
            {
                "AAPL": {
                    "Close": _constant_series(100.0, n),
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["AAPL"])
        expected_keys = {s["key"] for s in BREADTH_SCANS}
        assert set(result.keys()) == expected_keys

    def test_each_scan_has_count_and_tickers(self):
        """Each scan result must have 'count' and 'tickers' keys."""
        n = 80
        df = _make_multiindex_df(
            {
                "AAPL": {
                    "Close": _constant_series(150.0, n),
                    "Volume": _constant_series(500_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["AAPL"])
        for key, val in result.items():
            assert "count" in val, f"{key} missing 'count'"
            assert "tickers" in val, f"{key} missing 'tickers'"
            assert val["count"] == len(val["tickers"])

    def test_detects_6pct_daily_up(self):
        """A stock that jumps 6% in one day must appear in 4pct_up_1d."""
        n = 80
        closes = _constant_series(100.0, n)
        closes[-1] = 106.0  # 6% jump on last day
        df = _make_multiindex_df(
            {
                "JUMPER": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["JUMPER"])
        assert "JUMPER" in result["4pct_up_1d"]["tickers"]
        assert result["4pct_up_1d"]["count"] >= 1

    def test_does_not_detect_3pct_daily_up(self):
        """A 3% jump must NOT appear in 4pct_up_1d (threshold is 4%)."""
        n = 80
        closes = _constant_series(100.0, n)
        closes[-1] = 103.0  # 3% jump — below threshold
        df = _make_multiindex_df(
            {
                "SMALL": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["SMALL"])
        assert "SMALL" not in result["4pct_up_1d"]["tickers"]

    def test_detects_5pct_daily_down(self):
        """A stock that drops 5% in one day must appear in 4pct_down_1d."""
        n = 80
        closes = _constant_series(100.0, n)
        closes[-1] = 95.0  # -5% drop
        df = _make_multiindex_df(
            {
                "DROPPER": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["DROPPER"])
        assert "DROPPER" in result["4pct_down_1d"]["tickers"]

    def test_detects_30pct_up_over_20d(self):
        """A stock that rises 30% from its min over the 20-day window
        must appear in 25pct_up_20d.
        """
        n = 80
        closes = _constant_series(100.0, n)
        # Set the min close to 80 somewhere in the last 20 days, then close at 106
        # pct = (106 - 80) / 80 = 32.5%
        closes[-15] = 80.0
        closes[-1] = 106.0
        df = _make_multiindex_df(
            {
                "RISER": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["RISER"])
        assert "RISER" in result["25pct_up_20d"]["tickers"]

    def test_detects_30pct_down_over_20d(self):
        """A stock that drops 30% from its max over 20 days must appear
        in 25pct_down_20d.
        """
        n = 80
        closes = _constant_series(100.0, n)
        # Set max to 120 somewhere in the lookback, then close at 80
        # pct = (80 - 120) / 120 = -33%
        closes[-15] = 120.0
        closes[-1] = 80.0
        df = _make_multiindex_df(
            {
                "FALLER": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["FALLER"])
        assert "FALLER" in result["25pct_down_20d"]["tickers"]

    def test_volume_filter_excludes_low_liquidity(self):
        """Stocks with avg_close * avg_volume < 250,000 should be excluded."""
        n = 80
        closes = _constant_series(1.0, n)  # $1 stock
        closes[-1] = 1.06  # 6% up
        volumes = _constant_series(100.0, n)  # avg(close)*avg(vol) = 1.0*100 = 100 < 250k
        df = _make_multiindex_df(
            {
                "PENNY": {
                    "Close": closes,
                    "Volume": volumes,
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["PENNY"])
        assert "PENNY" not in result["4pct_up_1d"]["tickers"]

    def test_flat_stock_hits_nothing(self):
        """A completely flat stock should not appear in any scan."""
        n = 80
        df = _make_multiindex_df(
            {
                "FLAT": {
                    "Close": _constant_series(100.0, n),
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["FLAT"])
        for key, val in result.items():
            assert "FLAT" not in val["tickers"], f"FLAT should not appear in {key}"

    def test_multiple_tickers_independent(self):
        """Scans work correctly with multiple tickers in the DataFrame."""
        n = 80
        closes_up = _constant_series(100.0, n)
        closes_up[-1] = 107.0  # 7% up
        closes_flat = _constant_series(100.0, n)

        df = _make_multiindex_df(
            {
                "UP": {
                    "Close": closes_up,
                    "Volume": _constant_series(1_000_000, n),
                },
                "FLAT": {
                    "Close": closes_flat,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["UP", "FLAT"])
        assert "UP" in result["4pct_up_1d"]["tickers"]
        assert "FLAT" not in result["4pct_up_1d"]["tickers"]

    def test_missing_ticker_handled_gracefully(self):
        """Tickers not in the DataFrame are silently skipped."""
        n = 80
        df = _make_multiindex_df(
            {
                "AAPL": {
                    "Close": _constant_series(100.0, n),
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        # Include a ticker that does not exist in the DataFrame
        result = _compute_breadth_scans(df, ["AAPL", "NONEXISTENT"])
        # Should not raise and NONEXISTENT should not appear anywhere
        for key, val in result.items():
            assert "NONEXISTENT" not in val["tickers"]

    def test_65d_lookback_requires_enough_data(self):
        """Stocks with < 66 bars should not appear in the 65-day scans."""
        n = 60  # Only 60 bars — not enough for 65-day lookback
        closes = _ramp_series(50, 150, n)  # Big move but not enough bars
        df = _make_multiindex_df(
            {
                "SHORT": {
                    "Close": closes,
                    "Volume": _constant_series(1_000_000, n),
                },
            },
            n_days=n,
        )
        result = _compute_breadth_scans(df, ["SHORT"])
        assert "SHORT" not in result["25pct_up_65d"]["tickers"]
        assert "SHORT" not in result["25pct_down_65d"]["tickers"]


# ---------------------------------------------------------------------------
# Tests for _compute_theme_tracker
# ---------------------------------------------------------------------------


class TestComputeThemeTracker:
    """Tests for the pure theme tracker computation."""

    def test_returns_all_period_keys(self):
        """Result dict must contain all 4 period keys (1d, 1w, 1m, 3m)."""
        n = 80
        df = _make_multiindex_df(
            {
                "AAPL": {
                    "Close": _constant_series(100.0, n),
                },
            },
            n_days=n,
        )
        result = _compute_theme_tracker(df, ["AAPL"], {"AAPL": "Technology"})
        assert set(result.keys()) == set(THEME_PERIODS.keys())

    def test_each_entry_has_expected_fields(self):
        """Each sector entry must have sector, gainers, losers, net."""
        n = 80
        df = _make_multiindex_df(
            {
                "AAPL": {
                    "Close": _ramp_series(100, 110, n),
                },
            },
            n_days=n,
        )
        result = _compute_theme_tracker(df, ["AAPL"], {"AAPL": "Technology"})
        for period, rankings in result.items():
            assert len(rankings) > 0, f"No rankings for {period}"
            for entry in rankings:
                assert "sector" in entry
                assert "gainers" in entry
                assert "losers" in entry
                assert "net" in entry

    def test_ranks_sectors_correctly(self):
        """A sector with more gainers should rank higher (higher net)."""
        n = 80
        # Tech stocks go up, Energy goes down
        df = _make_multiindex_df(
            {
                "AAPL": {"Close": _ramp_series(100, 120, n)},
                "MSFT": {"Close": _ramp_series(200, 230, n)},
                "XOM": {"Close": _ramp_series(100, 90, n)},
                "CVX": {"Close": _ramp_series(120, 100, n)},
            },
            n_days=n,
        )
        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "XOM": "Energy",
            "CVX": "Energy",
        }
        result = _compute_theme_tracker(df, ["AAPL", "MSFT", "XOM", "CVX"], sector_map)

        # For 1d period, tech should be ranked above energy
        rankings_1d = result["1d"]
        sector_order = [r["sector"] for r in rankings_1d]
        tech_idx = sector_order.index("Technology")
        energy_idx = sector_order.index("Energy")
        assert tech_idx < energy_idx, "Technology should rank above Energy"

    def test_net_is_gainers_minus_losers(self):
        """net = gainers - losers for each sector."""
        n = 80
        df = _make_multiindex_df(
            {
                "UP1": {"Close": _ramp_series(100, 110, n)},
                "DOWN1": {"Close": _ramp_series(100, 90, n)},
                "FLAT1": {"Close": _constant_series(100.0, n)},
            },
            n_days=n,
        )
        sector_map = {"UP1": "Tech", "DOWN1": "Tech", "FLAT1": "Tech"}
        result = _compute_theme_tracker(df, ["UP1", "DOWN1", "FLAT1"], sector_map)

        for period, rankings in result.items():
            for entry in rankings:
                assert entry["net"] == entry["gainers"] - entry["losers"]

    def test_all_gainers_positive_net(self):
        """If all stocks in a sector go up, net should be positive."""
        n = 80
        df = _make_multiindex_df(
            {
                "BULL1": {"Close": _ramp_series(100, 120, n)},
                "BULL2": {"Close": _ramp_series(50, 70, n)},
            },
            n_days=n,
        )
        sector_map = {"BULL1": "BullSector", "BULL2": "BullSector"}
        result = _compute_theme_tracker(df, ["BULL1", "BULL2"], sector_map)

        for period, rankings in result.items():
            for entry in rankings:
                if entry["sector"] == "BullSector":
                    assert entry["net"] > 0, f"Expected positive net for {period}"

    def test_all_losers_negative_net(self):
        """If all stocks in a sector go down, net should be negative."""
        n = 80
        df = _make_multiindex_df(
            {
                "BEAR1": {"Close": _ramp_series(100, 80, n)},
                "BEAR2": {"Close": _ramp_series(50, 30, n)},
            },
            n_days=n,
        )
        sector_map = {"BEAR1": "BearSector", "BEAR2": "BearSector"}
        result = _compute_theme_tracker(df, ["BEAR1", "BEAR2"], sector_map)

        for period, rankings in result.items():
            for entry in rankings:
                if entry["sector"] == "BearSector":
                    assert entry["net"] < 0, f"Expected negative net for {period}"

    def test_unknown_sector_for_unmapped_tickers(self):
        """Tickers without a sector mapping should land in 'Unknown'."""
        n = 80
        df = _make_multiindex_df(
            {
                "MYSTERY": {"Close": _ramp_series(100, 110, n)},
            },
            n_days=n,
        )
        result = _compute_theme_tracker(df, ["MYSTERY"], {})
        for period, rankings in result.items():
            sectors = [r["sector"] for r in rankings]
            assert "Unknown" in sectors

    def test_multiple_sectors_all_present(self):
        """All sectors represented in the sector_map should appear in results."""
        n = 80
        df = _make_multiindex_df(
            {
                "A": {"Close": _ramp_series(100, 110, n)},
                "B": {"Close": _ramp_series(100, 90, n)},
                "C": {"Close": _ramp_series(100, 105, n)},
            },
            n_days=n,
        )
        sector_map = {"A": "Tech", "B": "Energy", "C": "Health"}
        result = _compute_theme_tracker(df, ["A", "B", "C"], sector_map)
        for period, rankings in result.items():
            sectors = {r["sector"] for r in rankings}
            assert {"Tech", "Energy", "Health"}.issubset(sectors)
