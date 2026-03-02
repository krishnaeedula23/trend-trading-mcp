"""Tests for the VOMY / iVOMY scanner endpoint."""

import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Universe fixture data
# ---------------------------------------------------------------------------

UNIVERSE = {
    "sp500": ["AAPL", "MSFT"],
    "nasdaq100": ["AAPL", "TSLA"],
    "all_unique": ["AAPL", "MSFT", "TSLA"],
    "counts": {"sp500": 2, "nasdaq100": 2, "all_unique": 3},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """FastAPI test client."""
    from api.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_schwab_token():
    """Skip the Schwab token check for all VOMY tests."""
    with patch("api.endpoints.schwab.token_exists", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_universe(tmp_path):
    """Write a small test universe.json and patch UNIVERSE_PATH."""
    universe_file = tmp_path / "universe.json"
    universe_file.write_text(json.dumps(UNIVERSE))

    with patch("api.endpoints.screener.UNIVERSE_PATH", universe_file):
        yield universe_file


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------


def _make_daily_df(
    base_price: float = 100.0, days: int = 60, growth: float = 0.0
) -> pd.DataFrame:
    """Generate synthetic daily OHLCV data.

    The growth parameter controls linear price progression from
    base_price to base_price * (1 + growth) over the period.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.linspace(base_price, base_price * (1 + growth), days)
    return pd.DataFrame(
        {
            "open": prices * 0.998,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )


def _make_vomy_daily(base_price: float = 100.0, days: int = 60) -> pd.DataFrame:
    """Build daily data where the last bar triggers a VOMY (bearish) signal.

    VOMY: EMA13 >= close AND EMA48 <= close AND EMA13 >= EMA21 >= EMA34 >= EMA48

    Strategy: use stable prices then introduce a mild downtrend in the last
    ~15 bars.  Shorter EMAs (13) track the decline faster and sit higher than
    longer EMAs (48) which lag behind.  Set the last close between EMA48 and
    EMA13 to satisfy the sandwich condition.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")

    # Flat for the first portion, then a controlled decline
    flat_count = days - 15
    flat = np.full(flat_count, base_price)
    # Decline from base_price to base_price * 0.92 over 15 bars
    decline = np.linspace(base_price, base_price * 0.92, 15)
    prices = np.concatenate([flat, decline])

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices.copy(),
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Compute EMAs to figure out where they land
    close = df["close"]
    ema13 = close.ewm(span=13, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema34 = close.ewm(span=34, adjust=False).mean()
    ema48 = close.ewm(span=48, adjust=False).mean()

    # The last bar close needs: ema48 <= close <= ema13
    # With our downtrend, shorter EMAs should be higher (they were at base_price
    # more recently), so ema13 > ema21 > ema34 > ema48 might not hold if the
    # decline is too steep.  Actually with decline, shorter EMAs react faster
    # and drop MORE, so we need an uptrend-then-reversal pattern instead.
    #
    # Re-think: In a downtrend, shorter EMAs drop faster than longer ones.
    # So ema13 < ema21 < ema34 < ema48 (inverted from what we need).
    # We need ema13 >= ema21 >= ema34 >= ema48, which means the price has
    # been RISING (or was recently higher).
    #
    # VOMY is a bearish flip: price WAS above EMAs and is now sandwiching
    # between them.  So: uptrend followed by a pullback on the last bars.

    # Rebuild: uptrend then slight pullback at end
    uptick = np.linspace(base_price, base_price * 1.15, days - 5)
    # Pull back on the last 5 bars
    pullback = np.linspace(base_price * 1.15, base_price * 1.08, 5)
    prices = np.concatenate([uptick, pullback])

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices.copy(),
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Recompute EMAs
    close = df["close"]
    ema13 = close.ewm(span=13, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema34 = close.ewm(span=34, adjust=False).mean()
    ema48 = close.ewm(span=48, adjust=False).mean()

    e13 = float(ema13.iloc[-1])
    e21 = float(ema21.iloc[-1])
    e34 = float(ema34.iloc[-1])
    e48 = float(ema48.iloc[-1])

    # After uptrend + pullback, shorter EMAs should be higher because they
    # were tracking the peak price more closely.  Verify ordering:
    # ema13 >= ema21 >= ema34 >= ema48 should hold.
    # If not, adjust the pullback magnitude.
    assert e13 >= e21 >= e34 >= e48, (
        f"EMA ordering failed for VOMY: e13={e13:.4f}, e21={e21:.4f}, "
        f"e34={e34:.4f}, e48={e48:.4f}"
    )

    # Set last close so that: ema48 <= close <= ema13
    # Midpoint between ema48 and ema13
    target_close = (e48 + e13) / 2.0
    df.iloc[-1, df.columns.get_loc("close")] = target_close
    df.iloc[-1, df.columns.get_loc("open")] = target_close * 0.999
    df.iloc[-1, df.columns.get_loc("high")] = target_close * 1.005
    df.iloc[-1, df.columns.get_loc("low")] = target_close * 0.995

    return df


def _make_ivomy_daily(base_price: float = 100.0, days: int = 60) -> pd.DataFrame:
    """Build daily data where the last bar triggers an iVOMY (bullish) signal.

    iVOMY: EMA13 <= close AND EMA48 >= close AND EMA13 <= EMA21 <= EMA34 <= EMA48

    Strategy: downtrend followed by a bounce on the last few bars.
    In a downtrend, shorter EMAs drop faster and sit BELOW longer EMAs.
    Then bounce the close back up to sit between ema13 and ema48.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")

    # Downtrend then bounce
    downtrend = np.linspace(base_price, base_price * 0.85, days - 5)
    bounce = np.linspace(base_price * 0.85, base_price * 0.92, 5)
    prices = np.concatenate([downtrend, bounce])

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices.copy(),
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Compute EMAs
    close = df["close"]
    ema13 = close.ewm(span=13, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema34 = close.ewm(span=34, adjust=False).mean()
    ema48 = close.ewm(span=48, adjust=False).mean()

    e13 = float(ema13.iloc[-1])
    e21 = float(ema21.iloc[-1])
    e34 = float(ema34.iloc[-1])
    e48 = float(ema48.iloc[-1])

    # After downtrend + bounce, shorter EMAs should be lower:
    # ema13 <= ema21 <= ema34 <= ema48
    assert e13 <= e21 <= e34 <= e48, (
        f"EMA ordering failed for iVOMY: e13={e13:.4f}, e21={e21:.4f}, "
        f"e34={e34:.4f}, e48={e48:.4f}"
    )

    # Set last close so that: ema13 <= close <= ema48
    target_close = (e13 + e48) / 2.0
    df.iloc[-1, df.columns.get_loc("close")] = target_close
    df.iloc[-1, df.columns.get_loc("open")] = target_close * 0.999
    df.iloc[-1, df.columns.get_loc("high")] = target_close * 1.005
    df.iloc[-1, df.columns.get_loc("low")] = target_close * 0.995

    return df


# ---------------------------------------------------------------------------
# Fake ATR result for enrichment
# ---------------------------------------------------------------------------

_FAKE_ATR_RESULT = {
    "pdc": 100.0,
    "atr": 2.5,
    "current_price": 100.5,
    "atr_status": "bull_zone",
    "atr_covered_pct": 35.0,
    "trend": "bullish",
    "levels": {},
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVomyScan:
    """Tests for POST /api/screener/vomy-scan."""

    def _mock_fetch(
        self, daily_df: pd.DataFrame, premarket_df: pd.DataFrame | None = None
    ):
        """Return context managers that patch data-fetching helpers."""
        return (
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=lambda ticker, tf: daily_df,
            ),
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=lambda ticker, mode: daily_df,
            ),
            patch(
                "api.endpoints.screener._fetch_premarket",
                side_effect=lambda ticker: premarket_df,
            ),
            patch(
                "api.endpoints.screener.resolve_use_current_close",
                return_value=False,
            ),
        )

    # 1. Happy path returns 200
    def test_returns_200(self, client):
        daily = _make_daily_df(base_price=100.0, days=60)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        assert resp.status_code == 200

    # 2. Response shape
    def test_response_shape(self, client):
        daily = _make_daily_df(base_price=100.0, days=60)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        data = resp.json()
        assert "hits" in data
        assert "total_scanned" in data
        assert "total_hits" in data
        assert "total_errors" in data
        assert "skipped_low_price" in data
        assert "scan_duration_seconds" in data
        assert "signal_type" in data
        assert "timeframe" in data
        assert isinstance(data["hits"], list)
        assert isinstance(data["total_scanned"], int)
        assert isinstance(data["total_hits"], int)
        assert isinstance(data["total_errors"], int)
        assert isinstance(data["skipped_low_price"], int)
        assert isinstance(data["scan_duration_seconds"], float)
        assert isinstance(data["signal_type"], str)
        assert isinstance(data["timeframe"], str)

    # 3. VOMY signal detected
    def test_vomy_signal_detected(self, client):
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "vomy",
                    "timeframe": "1d",
                },
            )

        data = resp.json()
        assert data["total_hits"] > 0, f"Expected VOMY hits, got 0. data={data}"
        hit = data["hits"][0]
        assert hit["signal"] == "vomy"
        # Verify all expected fields are present
        expected_fields = [
            "ticker",
            "last_close",
            "signal",
            "ema13",
            "ema21",
            "ema34",
            "ema48",
            "distance_from_ema48_pct",
            "atr",
            "pdc",
            "atr_status",
            "atr_covered_pct",
            "trend",
            "trading_mode",
            "timeframe",
        ]
        for field in expected_fields:
            assert field in hit, f"Missing field: {field}"

    # 4. iVOMY signal detected
    def test_ivomy_signal_detected(self, client):
        daily = _make_ivomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "ivomy",
                    "timeframe": "1d",
                },
            )

        data = resp.json()
        assert data["total_hits"] > 0, f"Expected iVOMY hits, got 0. data={data}"
        hit = data["hits"][0]
        assert hit["signal"] == "ivomy"

    # 5. signal_type="both" returns vomy or ivomy hits
    def test_signal_type_both(self, client):
        # Use VOMY data -- "both" should still find the vomy signal
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "both",
                    "timeframe": "1d",
                },
            )

        data = resp.json()
        assert data["total_hits"] > 0, "Expected hits with signal_type=both, got 0"
        for hit in data["hits"]:
            assert hit["signal"] in ("vomy", "ivomy")

    # 6. Price filter
    def test_price_filter(self, client):
        """Stocks below min_price are excluded and counted as skipped_low_price."""
        daily = _make_daily_df(base_price=2.0, days=60)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "min_price": 4.0},
            )

        data = resp.json()
        assert data["skipped_low_price"] > 0
        assert data["total_hits"] == 0

    # 7. Custom tickers merged
    def test_custom_tickers_merged(self, client):
        daily = _make_daily_df(base_price=100.0, days=60)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "custom_tickers": ["GOOG", "AMZN"],
                },
            )

        data = resp.json()
        # sp500 has 2 tickers (AAPL, MSFT) + 2 custom = 4
        assert data["total_scanned"] == 4

    # 8. Timeframe passed through
    def test_timeframe_passed(self, client):
        daily = _make_daily_df(base_price=100.0, days=60)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={
                    "universes": ["sp500"],
                    "timeframe": "1h",
                },
            )

        data = resp.json()
        assert data["timeframe"] == "1h"

    # 9. Fetch error counted
    def test_fetch_error_counted(self, client):
        """When _fetch_intraday raises, the error is counted."""
        with (
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=RuntimeError("yfinance down"),
            ),
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=RuntimeError("yfinance down"),
            ),
            patch(
                "api.endpoints.screener._fetch_premarket",
                side_effect=lambda ticker: None,
            ),
            patch(
                "api.endpoints.screener.resolve_use_current_close",
                return_value=False,
            ),
        ):
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"]},
            )

        data = resp.json()
        assert resp.status_code == 200
        assert data["total_errors"] == 2  # AAPL and MSFT both fail
        assert data["total_hits"] == 0
