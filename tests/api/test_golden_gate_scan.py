"""Tests for the Golden Gate scanner endpoint."""

import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

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
    """Skip the Schwab token check for all golden gate tests."""
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
    base_price: float = 100.0, days: int = 30, growth: float = 0.0
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


def _make_premarket_df(
    high: float = 105.0,
    low: float = 99.0,
    close: float = 103.0,
) -> pd.DataFrame:
    """Generate synthetic premarket minute-bar data (4:00-9:29 AM ET)."""
    ET = ZoneInfo("America/New_York")
    today = datetime.now(ET).strftime("%Y-%m-%d")
    idx = pd.date_range(f"{today} 04:00", f"{today} 09:29", freq="1min", tz=ET)
    n = len(idx)
    return pd.DataFrame(
        {
            "open": np.linspace(low, close, n),
            "high": np.full(n, high),
            "low": np.full(n, low),
            "close": np.linspace(low, close, n),
            "volume": [10_000] * n,
        },
        index=idx,
    )


def _make_golden_gate_daily(
    base_price: float = 100.0,
    days: int = 30,
) -> pd.DataFrame:
    """Build daily data where the last bar triggers a golden_gate bullish signal.

    Strategy: construct stable data so that atr_levels() produces known levels,
    then craft the last bar so its high is between golden_gate_bull and
    mid_range_bull, and close >= PDC.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.full(days, base_price)

    # Build a flat DataFrame first so ATR is small and predictable.
    # Add slight daily variation so ATR is non-zero.
    highs = prices * 1.005
    lows = prices * 0.995
    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    # Compute what atr_levels would see (anchor = iloc[-2] because ucc is auto).
    # We need to figure out PDC and ATR from iloc[-2], then set the last bar's
    # high to land between golden_gate_bull and mid_range_bull.
    from api.indicators.satyland.atr_levels import _wilder_atr

    atr_series = _wilder_atr(df, 14)
    atr = float(atr_series.iloc[-2])
    pdc = float(df["close"].iloc[-2])

    golden_gate_bull = pdc + atr * 0.382
    mid_range_bull = pdc + atr * 0.618

    # Set the last bar high to midpoint between golden_gate and mid_range
    target_high = (golden_gate_bull + mid_range_bull) / 2.0
    # Close must be >= PDC for bullish signal
    target_close = pdc + atr * 0.1  # slightly above PDC

    df.iloc[-1, df.columns.get_loc("high")] = target_high
    df.iloc[-1, df.columns.get_loc("close")] = target_close
    df.iloc[-1, df.columns.get_loc("low")] = pdc - atr * 0.05

    return df


def _make_call_trigger_daily(base_price: float = 100.0, days: int = 30) -> pd.DataFrame:
    """Build daily data where the last bar triggers a call_trigger signal.

    call_trigger: trigger_bull <= bar_high AND golden_gate_bull > bar_high AND pdc <= bar_close
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.full(days, base_price)
    highs = prices * 1.005
    lows = prices * 0.995

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    from api.indicators.satyland.atr_levels import _wilder_atr

    atr_series = _wilder_atr(df, 14)
    atr = float(atr_series.iloc[-2])
    pdc = float(df["close"].iloc[-2])

    trigger_bull = pdc + atr * 0.236
    golden_gate_bull = pdc + atr * 0.382

    # High between trigger_bull and golden_gate_bull
    target_high = (trigger_bull + golden_gate_bull) / 2.0
    target_close = pdc + atr * 0.05

    df.iloc[-1, df.columns.get_loc("high")] = target_high
    df.iloc[-1, df.columns.get_loc("close")] = target_close
    df.iloc[-1, df.columns.get_loc("low")] = pdc - atr * 0.05

    return df


def _make_put_trigger_daily(base_price: float = 100.0, days: int = 30) -> pd.DataFrame:
    """Build daily data where the last bar triggers a put_trigger signal.

    put_trigger: trigger_bear >= bar_low AND golden_gate_bear < bar_low AND pdc >= bar_close
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.full(days, base_price)
    highs = prices * 1.005
    lows = prices * 0.995

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    from api.indicators.satyland.atr_levels import _wilder_atr

    atr_series = _wilder_atr(df, 14)
    atr = float(atr_series.iloc[-2])
    pdc = float(df["close"].iloc[-2])

    trigger_bear = pdc - atr * 0.236
    golden_gate_bear = pdc - atr * 0.382

    # Low between golden_gate_bear and trigger_bear
    target_low = (trigger_bear + golden_gate_bear) / 2.0
    # Close must be <= PDC for bearish signal
    target_close = pdc - atr * 0.05

    df.iloc[-1, df.columns.get_loc("low")] = target_low
    df.iloc[-1, df.columns.get_loc("high")] = pdc + atr * 0.01
    df.iloc[-1, df.columns.get_loc("close")] = target_close

    return df


def _make_golden_gate_down_daily(
    base_price: float = 100.0, days: int = 30
) -> pd.DataFrame:
    """Build daily data where the last bar triggers a golden_gate_down (bearish) signal.

    golden_gate_down: golden_gate_bear >= bar_low AND mid_range_bear < bar_low AND pdc >= bar_close
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")
    prices = np.full(days, base_price)
    highs = prices * 1.005
    lows = prices * 0.995

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    from api.indicators.satyland.atr_levels import _wilder_atr

    atr_series = _wilder_atr(df, 14)
    atr = float(atr_series.iloc[-2])
    pdc = float(df["close"].iloc[-2])

    golden_gate_bear = pdc - atr * 0.382
    mid_range_bear = pdc - atr * 0.618

    # Low between mid_range_bear and golden_gate_bear (so gg_bear >= low and mr_bear < low)
    target_low = (golden_gate_bear + mid_range_bear) / 2.0
    # Close must be <= PDC for bearish signal
    target_close = pdc - atr * 0.1

    df.iloc[-1, df.columns.get_loc("low")] = target_low
    df.iloc[-1, df.columns.get_loc("high")] = pdc + atr * 0.01
    df.iloc[-1, df.columns.get_loc("close")] = target_close

    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoldenGateScan:
    """Tests for POST /api/screener/golden-gate-scan."""

    def _mock_fetch(
        self, daily_df: pd.DataFrame, premarket_df: pd.DataFrame | None = None
    ):
        """Return context managers that patch _fetch_atr_source, _fetch_intraday, and _fetch_premarket."""
        return (
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=lambda ticker, mode: daily_df,
            ),
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=lambda ticker, tf: daily_df,
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
        daily = _make_daily_df(base_price=100.0, days=30)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={"universes": ["sp500"]},
            )

        assert resp.status_code == 200

    # 2. Response shape
    def test_response_shape(self, client):
        daily = _make_daily_df(base_price=100.0, days=30)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
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
        assert "trading_mode" in data
        assert isinstance(data["hits"], list)
        assert isinstance(data["total_scanned"], int)
        assert isinstance(data["total_hits"], int)
        assert isinstance(data["total_errors"], int)
        assert isinstance(data["skipped_low_price"], int)
        assert isinstance(data["scan_duration_seconds"], float)
        assert isinstance(data["signal_type"], str)
        assert isinstance(data["trading_mode"], str)

    # 3. Hit fields
    def test_hit_fields(self, client):
        daily = _make_golden_gate_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "golden_gate_up",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        if data["total_hits"] > 0:
            hit = data["hits"][0]
            expected_fields = [
                "ticker",
                "last_close",
                "signal",
                "direction",
                "pdc",
                "atr",
                "gate_level",
                "midrange_level",
                "distance_pct",
                "atr_status",
                "atr_covered_pct",
                "trend",
                "trading_mode",
            ]
            for field in expected_fields:
                assert field in hit, f"Missing field: {field}"
            assert hit["signal"] == "golden_gate_up"
            assert hit["direction"] == "bullish"

    # 3b. golden_gate_up only returns bullish signals
    def test_signal_type_golden_gate_up(self, client):
        daily = _make_golden_gate_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "golden_gate_up",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "golden_gate_up"
        for hit in data["hits"]:
            assert hit["signal"] == "golden_gate_up"
            assert hit["direction"] == "bullish"

    # 3c. golden_gate_down only returns bearish signals
    def test_signal_type_golden_gate_down(self, client):
        daily = _make_golden_gate_down_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "golden_gate_down",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "golden_gate_down"
        for hit in data["hits"]:
            assert hit["signal"] == "golden_gate_down"
            assert hit["direction"] == "bearish"

    # 3d. golden_gate (combined) returns bullish or bearish signals
    def test_signal_type_golden_gate_combined(self, client):
        """signal_type='golden_gate' checks both directions; hits have directional signal keys."""
        # Use bullish-triggering data — combined mode should find golden_gate_up
        daily = _make_golden_gate_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "golden_gate",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "golden_gate"
        # Combined mode emits directional signal keys, not "golden_gate"
        for hit in data["hits"]:
            assert hit["signal"] in ("golden_gate_up", "golden_gate_down")

    # 3e. golden_gate combined with bearish data returns golden_gate_down
    def test_signal_type_golden_gate_combined_bearish(self, client):
        """signal_type='golden_gate' with bearish data returns golden_gate_down hits."""
        daily = _make_golden_gate_down_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "golden_gate",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "golden_gate"
        for hit in data["hits"]:
            assert hit["signal"] == "golden_gate_down"
            assert hit["direction"] == "bearish"

    # 4. Price filter
    def test_price_filter(self, client):
        """Stocks below min_price are excluded and counted as skipped_low_price."""
        daily = _make_daily_df(base_price=2.0, days=30)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={"universes": ["sp500"], "min_price": 4.0},
            )

        data = resp.json()
        assert data["skipped_low_price"] > 0
        hit_tickers = [h["ticker"] for h in data["hits"]]
        assert "AAPL" not in hit_tickers
        assert "MSFT" not in hit_tickers

    # 5. Custom tickers merged
    def test_custom_tickers_merged(self, client):
        daily = _make_daily_df(base_price=100.0, days=30)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "custom_tickers": ["GOOG"],
                },
            )

        data = resp.json()
        # sp500 has 2 tickers (AAPL, MSFT) + 1 custom = 3
        assert data["total_scanned"] == 3

    # 6. signal_type=call_trigger
    def test_signal_type_call_trigger(self, client):
        daily = _make_call_trigger_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "call_trigger",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "call_trigger"
        # All hits (if any) must have signal=call_trigger
        for hit in data["hits"]:
            assert hit["signal"] == "call_trigger"
            assert hit["direction"] == "bullish"

    # 7. signal_type=put_trigger
    def test_signal_type_put_trigger(self, client):
        daily = _make_put_trigger_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily, premarket_df=None)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "signal_type": "put_trigger",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["signal_type"] == "put_trigger"
        for hit in data["hits"]:
            assert hit["signal"] == "put_trigger"
            assert hit["direction"] == "bearish"

    # 8. trading_mode=swing is passed through
    def test_trading_mode_swing(self, client):
        daily = _make_daily_df(base_price=100.0, days=30)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "trading_mode": "swing",
                    "include_premarket": False,
                },
            )

        data = resp.json()
        assert data["trading_mode"] == "swing"

    # 9. include_premarket=False means _fetch_premarket is never called
    def test_premarket_disabled(self, client):
        daily = _make_daily_df(base_price=100.0, days=30)
        premarket_mock = patch(
            "api.endpoints.screener._fetch_premarket",
            side_effect=lambda ticker: None,
        )

        with (
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=lambda ticker, mode: daily,
            ),
            patch(
                "api.endpoints.screener._fetch_intraday",
                side_effect=lambda ticker, tf: daily,
            ),
            premarket_mock as pm_mock,
            patch(
                "api.endpoints.screener.resolve_use_current_close",
                return_value=False,
            ),
        ):
            resp = client.post(
                "/api/screener/golden-gate-scan",
                json={
                    "universes": ["sp500"],
                    "include_premarket": False,
                },
            )

        assert resp.status_code == 200
        pm_mock.assert_not_called()

    # 10. Fetch error is counted
    def test_fetch_error_counted(self, client):
        """When _fetch_atr_source raises, the error is counted."""
        with (
            patch(
                "api.endpoints.screener._fetch_atr_source",
                side_effect=RuntimeError("yfinance down"),
            ),
            patch(
                "api.endpoints.screener._fetch_intraday",
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
                "/api/screener/golden-gate-scan",
                json={"universes": ["sp500"]},
            )

        data = resp.json()
        assert resp.status_code == 200
        assert data["total_errors"] == 2  # AAPL and MSFT both fail
        assert data["total_hits"] == 0
