"""Tests for the momentum scanner endpoint."""

from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """FastAPI test client with mocked Schwab dependency."""
    from api.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_schwab_token():
    """Skip the token check for all momentum tests."""
    with patch("api.endpoints.schwab.token_exists", return_value=True):
        yield


# ---------------------------------------------------------------------------
# Helpers for building synthetic yfinance DataFrames
# ---------------------------------------------------------------------------

def _make_dates(n: int = 150) -> pd.DatetimeIndex:
    """Generate n business-day dates ending today."""
    return pd.bdate_range(end=pd.Timestamp.now(), periods=n)


def _make_multi_df(
    tickers: dict[str, dict],
    n_days: int = 150,
) -> pd.DataFrame:
    """Build a MultiIndex DataFrame mimicking yf.download output.

    Args:
        tickers: Mapping of ticker -> config dict with keys:
            base_price: starting close price
            daily_return: multiplicative daily return (e.g. 1.001 for +0.1%/day)
        n_days: Number of trading days to generate.

    Returns:
        DataFrame with MultiIndex columns (Price, Ticker).
    """
    dates = _make_dates(n_days)
    frames = {}

    for ticker, cfg in tickers.items():
        base = cfg.get("base_price", 100.0)
        daily_ret = cfg.get("daily_return", 1.0)

        closes = [base * (daily_ret ** i) for i in range(n_days)]
        highs = [c * 1.01 for c in closes]
        lows = [c * 0.99 for c in closes]
        opens = [c * 1.005 for c in closes]
        volumes = [1_000_000] * n_days

        df = pd.DataFrame(
            {
                "Open": opens,
                "High": highs,
                "Low": lows,
                "Close": closes,
                "Volume": volumes,
            },
            index=dates,
        )
        frames[ticker] = df

    # Build MultiIndex DataFrame like yf.download
    combined = pd.concat(frames, axis=1)
    combined.columns = pd.MultiIndex.from_tuples(
        [(price, ticker) for ticker, df in frames.items() for price in df.columns],
        names=["Price", "Ticker"],
    )
    return combined


def _flat_universe(tickers: list[str]) -> list[str]:
    """Return a simple ticker list for mocking _load_universe."""
    return tickers


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMomentumScan:
    """Tests for POST /api/screener/momentum-scan."""

    def test_momentum_scan_returns_200(self, client):
        """Happy path: should return 200 with valid data."""
        # 12% weekly gain -> passes weekly_10pct
        multi_df = _make_multi_df({"AAPL": {"base_price": 100, "daily_return": 1.025}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["AAPL"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
                "min_price": 4.0,
            })

        assert resp.status_code == 200

    def test_response_shape(self, client):
        """Verify all MomentumScanResponse fields are present."""
        multi_df = _make_multi_df({"SPY": {"base_price": 500, "daily_return": 1.005}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["SPY"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert "hits" in data
        assert "total_scanned" in data
        assert "total_hits" in data
        assert "total_errors" in data
        assert "skipped_low_price" in data
        assert "scan_duration_seconds" in data
        assert "universes_used" in data
        assert data["total_scanned"] == 1

    def test_price_filter_excludes_cheap_stocks(self, client):
        """Stocks below min_price should be excluded from hits."""
        multi_df = _make_multi_df({
            "CHEAP": {"base_price": 2.50, "daily_return": 1.0},   # Below $4 (flat)
            "GOOD": {"base_price": 50.0, "daily_return": 1.05},   # Above $4 + strong
        })

        with (
            patch("api.endpoints.screener._load_universe", return_value=["CHEAP", "GOOD"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
                "min_price": 4.0,
            })

        data = resp.json()
        hit_tickers = [h["ticker"] for h in data["hits"]]
        assert "CHEAP" not in hit_tickers
        assert "GOOD" in hit_tickers
        assert data["skipped_low_price"] >= 1

    def test_weekly_10pct_criterion(self, client):
        """A stock with 12% weekly gain should trigger weekly_10pct."""
        # ~2.3% daily for 5 days = ~12% weekly
        multi_df = _make_multi_df({"FAST": {"base_price": 50, "daily_return": 1.023}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["FAST"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] >= 1
        hit = data["hits"][0]
        labels = [c["label"] for c in hit["criteria_met"]]
        assert "weekly_10pct" in labels

    def test_monthly_25pct_criterion(self, client):
        """A stock with 30% monthly gain should trigger monthly_25pct."""
        # ~1.25% daily for 21 days = ~30% monthly
        multi_df = _make_multi_df({"MOON": {"base_price": 20, "daily_return": 1.0125}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["MOON"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] >= 1
        hit = data["hits"][0]
        labels = [c["label"] for c in hit["criteria_met"]]
        assert "monthly_25pct" in labels

    def test_3month_50pct_criterion(self, client):
        """A stock with 60% 3-month gain should trigger 3month_50pct."""
        # ~0.75% daily for 63 days = ~60%
        multi_df = _make_multi_df({"ROCKET": {"base_price": 30, "daily_return": 1.0075}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["ROCKET"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] >= 1
        hit = data["hits"][0]
        labels = [c["label"] for c in hit["criteria_met"]]
        assert "3month_50pct" in labels

    def test_6month_100pct_criterion(self, client):
        """A stock with 120% 6-month gain should trigger 6month_100pct."""
        # ~0.6% daily for 126 days = ~113%
        multi_df = _make_multi_df({"HYPER": {"base_price": 10, "daily_return": 1.006}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["HYPER"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] >= 1
        hit = data["hits"][0]
        labels = [c["label"] for c in hit["criteria_met"]]
        assert "6month_100pct" in labels

    def test_no_criteria_met_excluded(self, client):
        """A flat-price stock should not appear in hits."""
        # daily_return=1.0 → 0% change everywhere
        multi_df = _make_multi_df({"FLAT": {"base_price": 100, "daily_return": 1.0}})

        with (
            patch("api.endpoints.screener._load_universe", return_value=["FLAT"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] == 0
        assert len(data["hits"]) == 0

    def test_sorted_by_max_pct_change(self, client):
        """Hits should be sorted by max_pct_change descending."""
        multi_df = _make_multi_df({
            "SLOW": {"base_price": 50, "daily_return": 1.023},   # ~12% weekly
            "FAST": {"base_price": 50, "daily_return": 1.04},    # ~22% weekly
            "MID": {"base_price": 50, "daily_return": 1.03},     # ~16% weekly
        })

        with (
            patch("api.endpoints.screener._load_universe", return_value=["SLOW", "FAST", "MID"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        pct_changes = [h["max_pct_change"] for h in data["hits"]]
        assert pct_changes == sorted(pct_changes, reverse=True)

    def test_empty_download_returns_zero_hits(self, client):
        """If yf.download returns empty DataFrame, no hits should be returned."""
        empty_df = pd.DataFrame()

        with (
            patch("api.endpoints.screener._load_universe", return_value=["AAPL", "MSFT"]),
            patch("api.endpoints.screener.yf.download", return_value=empty_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
            })

        data = resp.json()
        assert data["total_hits"] == 0
        assert data["total_errors"] == 2  # Both tickers counted as errors

    def test_custom_tickers_merged(self, client):
        """custom_tickers should be added to the universe."""
        multi_df = _make_multi_df({
            "AAPL": {"base_price": 200, "daily_return": 1.025},
            "CUSTOM1": {"base_price": 50, "daily_return": 1.025},
        })

        with (
            patch("api.endpoints.screener._load_universe", return_value=["AAPL"]),
            patch("api.endpoints.screener.yf.download", return_value=multi_df),
        ):
            resp = client.post("/api/screener/momentum-scan", json={
                "universes": ["sp500"],
                "custom_tickers": ["CUSTOM1"],
            })

        data = resp.json()
        assert data["total_scanned"] == 2
        hit_tickers = [h["ticker"] for h in data["hits"]]
        assert "CUSTOM1" in hit_tickers
