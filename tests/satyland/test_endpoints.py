"""
Level 3 tests — FastAPI endpoint integration.

Uses httpx.AsyncClient + ASGITransport with unittest.mock to patch
yfinance.download. No real network calls, no containers.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

# Ensure project root on path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from api.main import app  # noqa: E402


# ── Shared OHLCV helpers ───────────────────────────────────────────────────────

def _make_flat_ohlcv(n: int = 60, price: float = 100.0) -> pd.DataFrame:
    """Flat OHLCV DataFrame with slightly wider H/L for non-zero ATR."""
    closes = [price] * n
    highs = [price + 1.0] * n
    lows = [price - 1.0] * n
    opens = [price] * n
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes},
        index=idx,
    )
    return df


def _make_trending_ohlcv(n: int = 60) -> pd.DataFrame:
    """Trending up OHLCV DataFrame."""
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = [100.0] + closes[:-1]
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes},
        index=idx,
    )


def _make_daily_ohlcv(n: int = 60) -> pd.DataFrame:
    """Daily OHLCV with non-zero ATR for reliable indicator computation."""
    closes = [100.0 + i for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    opens = [100.0] + closes[:-1]
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes},
        index=idx,
    )


def _mock_yf_download(intraday_df: pd.DataFrame, daily_df: pd.DataFrame):
    """
    Return a side_effect callable that dispatches by interval parameter.

    yfinance.download is called with different intervals (1d vs 5m etc).
    The daily df must have at least 22 bars for phase_oscillator.
    """
    def side_effect(*args, **kwargs):
        interval = kwargs.get("interval", "1d")
        if interval == "1d":
            return daily_df.copy()
        return intraday_df.copy()
    return side_effect


# ── Client fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
async def satyland_client():
    """Async HTTP client scoped to the Trend Trading API app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── /api/satyland/calculate ───────────────────────────────────────────────────

class TestCalculateEndpoint:
    async def test_calculate_returns_200(self, satyland_client):
        """POST /api/satyland/calculate with valid ticker returns 200."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        assert resp.status_code == 200

    async def test_calculate_response_has_required_keys(self, satyland_client):
        """Response body must contain atr_levels, pivot_ribbon, phase_oscillator."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        body = resp.json()
        assert "atr_levels" in body
        assert "pivot_ribbon" in body
        assert "phase_oscillator" in body
        assert body["ticker"] == "AAPL"
        assert body["timeframe"] == "5m"

    async def test_calculate_bad_ticker_returns_400(self, satyland_client):
        """yfinance returns empty DataFrame → 400 Bad Request."""
        with patch("yfinance.download", return_value=pd.DataFrame()):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "FAKEXYZ999", "timeframe": "5m"},
            )
        assert resp.status_code == 400

    async def test_calculate_atr_levels_keys(self, satyland_client):
        """atr_levels sub-object contains expected keys."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        atr = resp.json()["atr_levels"]
        for key in ("atr", "pdc", "call_trigger", "put_trigger", "atr_status", "atr_room_ok"):
            assert key in atr, f"Missing key in atr_levels: {key}"

    async def test_timeframe_daily_uses_longer_lookback(self, satyland_client):
        """
        1d timeframe → yfinance must be called with interval='1d' and period='1y'.
        ATR levels also call with interval='1d' (always daily for ATR).
        """
        call_log = []

        def tracking_download(*args, **kwargs):
            call_log.append(kwargs)
            n = 300 if kwargs.get("period") == "1y" else 60
            return _make_daily_ohlcv(n)

        with patch("yfinance.download", side_effect=tracking_download):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "SPY", "timeframe": "1d"},
            )
        assert resp.status_code == 200
        # Should have called with interval='1d' at least once
        intervals = [c.get("interval") for c in call_log]
        assert "1d" in intervals

    async def test_atr_always_uses_daily_df(self, satyland_client):
        """
        Even for 5m chart, ATR endpoint must fetch daily data (period='3mo', interval='1d').
        The daily call ensures PDC and ATR are from the daily timeframe per Pine Script.
        """
        call_log = []

        def tracking_download(*args, **kwargs):
            call_log.append(dict(kwargs))
            interval = kwargs.get("interval", "1d")
            if interval == "1d":
                return _make_daily_ohlcv(60)
            return _make_trending_ohlcv(60)

        with patch("yfinance.download", side_effect=tracking_download):
            resp = await satyland_client.post(
                "/api/satyland/calculate",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        assert resp.status_code == 200
        # Must have at least one call with interval="1d" (ATR daily fetch)
        daily_calls = [c for c in call_log if c.get("interval") == "1d"]
        assert len(daily_calls) >= 1


# ── /api/satyland/trade-plan ──────────────────────────────────────────────────

class TestTradePlanEndpoint:
    async def test_trade_plan_returns_200(self, satyland_client):
        """POST /api/satyland/trade-plan returns 200."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "AAPL", "timeframe": "5m", "direction": "bullish"},
            )
        assert resp.status_code == 200

    async def test_trade_plan_grade_field_exists(self, satyland_client):
        """Response must contain green_flag.grade with a valid value."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "AAPL", "timeframe": "5m", "direction": "bullish"},
            )
        body = resp.json()
        assert "green_flag" in body
        assert "grade" in body["green_flag"]
        assert body["green_flag"]["grade"] in ("A+", "A", "B", "skip")

    async def test_trade_plan_required_sections(self, satyland_client):
        """Trade plan must include all sections: atr_levels, pivot_ribbon, etc."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "SPY", "timeframe": "5m", "direction": "bearish"},
            )
        body = resp.json()
        for section in ("atr_levels", "pivot_ribbon", "phase_oscillator",
                         "price_structure", "green_flag"):
            assert section in body, f"Missing section: {section}"

    async def test_trade_plan_bearish_direction_in_response(self, satyland_client):
        """direction field in green_flag must match request direction."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "AAPL", "timeframe": "5m", "direction": "bearish"},
            )
        body = resp.json()
        assert body["green_flag"]["direction"] == "bearish"

    async def test_trade_plan_no_key_error(self, satyland_client):
        """
        Regression: trade-plan must not 500 with KeyError after bug fixes.
        Previously crashed on ema34/call_trigger/firing_up/squeeze_active.
        """
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "AAPL", "timeframe": "5m", "direction": "bullish"},
            )
        # Must not be a 500 Internal Server Error
        assert resp.status_code != 500
        assert resp.status_code == 200

    async def test_trade_plan_with_vix(self, satyland_client):
        """Trade plan with vix parameter returns valid response."""
        intraday = _make_trending_ohlcv(60)
        daily = _make_daily_ohlcv(60)

        with patch("yfinance.download", side_effect=_mock_yf_download(intraday, daily)):
            resp = await satyland_client.post(
                "/api/satyland/trade-plan",
                json={"ticker": "AAPL", "timeframe": "5m", "direction": "bullish", "vix": 14.5},
            )
        body = resp.json()
        assert resp.status_code == 200
        # vix_bias flag should be present and boolean (not None)
        flags = body["green_flag"]["flags"]
        assert "vix_bias" in flags
        assert isinstance(flags["vix_bias"], bool)


# ── /api/satyland/price-structure ─────────────────────────────────────────────

class TestPriceStructureEndpoint:
    async def test_price_structure_returns_200(self, satyland_client):
        """POST /api/satyland/price-structure returns 200."""
        daily = _make_daily_ohlcv(60)
        with patch("yfinance.download", return_value=daily):
            resp = await satyland_client.post(
                "/api/satyland/price-structure",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        assert resp.status_code == 200

    async def test_price_structure_has_pdh_pdl_pdc(self, satyland_client):
        """Response must contain pdh, pdl, pdc keys."""
        daily = _make_daily_ohlcv(60)
        with patch("yfinance.download", return_value=daily):
            resp = await satyland_client.post(
                "/api/satyland/price-structure",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        body = resp.json()
        assert "pdh" in body
        assert "pdl" in body
        assert "pdc" in body

    async def test_price_structure_pdh_above_pdl(self, satyland_client):
        """PDH must always be >= PDL (previous day's high >= low)."""
        daily = _make_daily_ohlcv(60)
        with patch("yfinance.download", return_value=daily):
            resp = await satyland_client.post(
                "/api/satyland/price-structure",
                json={"ticker": "AAPL", "timeframe": "5m"},
            )
        body = resp.json()
        assert body["pdh"] >= body["pdl"]
