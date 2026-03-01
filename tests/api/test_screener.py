"""Tests for the screener orchestrator endpoint."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """FastAPI test client with mocked Schwab dependency."""
    from api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_schwab_token():
    """Skip the token check for all screener tests."""
    with patch("api.endpoints.schwab.token_exists", return_value=True):
        yield


class TestScreenerScan:
    def test_returns_ranked_results(self, client):
        """Screener should accept tickers, run indicators, and return graded results."""
        mock_trade_plan = {
            "ticker": "AAPL",
            "atr_levels": {"atr": 3.5, "pdc": 190.0, "current_price": 195.0,
                           "atr_status": "green", "atr_covered_pct": 0.3, "atr_room_ok": True,
                           "trend": "up", "chopzilla": False, "trading_mode": "trending",
                           "call_trigger": 193.5, "put_trigger": 186.5,
                           "trigger_box": {"low": 186.5, "high": 193.5, "inside": False},
                           "levels": {}},
            "pivot_ribbon": {"ribbon_state": "bullish", "bias_candle": "blue",
                             "in_compression": False, "above_200ema": True,
                             "ema8": 194, "ema13": 193, "ema21": 192, "ema48": 190, "ema200": 180,
                             "spread": 0.02, "chopzilla": False,
                             "bias_signal": "pullback", "conviction_arrow": "none",
                             "last_conviction_type": "none", "last_conviction_bars_ago": None,
                             "above_48ema": True},
            "phase_oscillator": {"oscillator": 65, "phase": "green",
                                  "in_compression": False, "current_zone": "momentum",
                                  "oscillator_prev": 60,
                                  "zone_crosses": {}, "zones": {},
                                  "last_mr_type": None, "last_mr_bars_ago": None},
            "green_flag": {"grade": "A+", "score": 7, "max_score": 10,
                           "direction": "bullish", "recommendation": "Strong trade",
                           "flags": {}, "verbal_audit": "All flags met"},
            "direction": "bullish",
            "price_structure": {"pdh": 196, "pdl": 189, "pmh": 200, "pml": 185},
        }

        with patch("api.endpoints.screener.calculate_trade_plan",
                    new_callable=AsyncMock, return_value=mock_trade_plan):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["AAPL"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["ticker"] == "AAPL"
        assert data["results"][0]["grade"] == "A+"

    def test_empty_tickers_returns_422(self, client):
        resp = client.post("/api/screener/scan", json={
            "tickers": [],
            "timeframe": "1d",
            "direction": "bullish",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_results_sorted_by_grade_then_score(self, client):
        """A+ should come before A, A before B."""
        mock = AsyncMock(side_effect=[
            {**_base_plan(), "ticker": "B_STOCK",
             "green_flag": {"grade": "B", "score": 3, "max_score": 10,
                            "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
            {**_base_plan(), "ticker": "A_PLUS",
             "green_flag": {"grade": "A+", "score": 7, "max_score": 10,
                            "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
            {**_base_plan(), "ticker": "A_STOCK",
             "green_flag": {"grade": "A", "score": 4, "max_score": 10,
                            "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""}},
        ])
        with patch("api.endpoints.screener.calculate_trade_plan", mock):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["B_STOCK", "A_PLUS", "A_STOCK"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        data = resp.json()
        grades = [r["grade"] for r in data["results"]]
        assert grades == ["A+", "A", "B"]

    def test_failed_ticker_becomes_skip(self, client):
        """If calculate_trade_plan raises, that ticker should get grade='skip'."""
        mock = AsyncMock(side_effect=ValueError("No data for FAKE at 1d"))
        with patch("api.endpoints.screener.calculate_trade_plan", mock):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["FAKE"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        data = resp.json()
        assert data["results"][0]["grade"] == "skip"
        assert data["errors"] == 1
        assert data["scanned"] == 0

    def test_response_shape(self, client):
        """Verify the ScanResponse shape."""
        mock = AsyncMock(return_value={
            **_base_plan(),
            "ticker": "SPY",
            "green_flag": {"grade": "A", "score": 5, "max_score": 10,
                           "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""},
        })
        with patch("api.endpoints.screener.calculate_trade_plan", mock):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["SPY"],
                "timeframe": "1d",
                "direction": "bullish",
            })

        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "scanned" in data
        assert "errors" in data
        assert data["total"] == 1
        assert data["scanned"] == 1
        assert data["errors"] == 0

    def test_vix_passed_to_calculate(self, client):
        """Verify that vix from request is forwarded to calculate_trade_plan."""
        mock = AsyncMock(return_value={
            **_base_plan(),
            "ticker": "SPY",
            "green_flag": {"grade": "A", "score": 5, "max_score": 10,
                           "direction": "bullish", "recommendation": "", "flags": {}, "verbal_audit": ""},
        })
        with patch("api.endpoints.screener.calculate_trade_plan", mock):
            resp = client.post("/api/screener/scan", json={
                "tickers": ["SPY"],
                "timeframe": "1d",
                "direction": "bullish",
                "vix": 15.2,
            })

        assert resp.status_code == 200
        mock.assert_called_once_with("SPY", "1d", "bullish", 15.2)


def _base_plan() -> dict:
    """Minimal trade plan dict for test mocking."""
    return {
        "atr_levels": {"atr": 3, "pdc": 100, "current_price": 103,
                        "atr_status": "green", "atr_covered_pct": 0.3, "atr_room_ok": True,
                        "trend": "up", "chopzilla": False, "trading_mode": "trending",
                        "call_trigger": 101, "put_trigger": 97,
                        "trigger_box": {"low": 97, "high": 101, "inside": False}, "levels": {}},
        "pivot_ribbon": {"ribbon_state": "bullish", "bias_candle": "green",
                         "in_compression": False, "above_200ema": True,
                         "ema8": 102, "ema13": 101, "ema21": 100, "ema48": 98, "ema200": 90,
                         "spread": 0.02, "chopzilla": False,
                         "bias_signal": "pullback", "conviction_arrow": "none",
                         "last_conviction_type": "none", "last_conviction_bars_ago": None,
                         "above_48ema": True},
        "phase_oscillator": {"oscillator": 50, "phase": "green", "in_compression": False,
                              "current_zone": "momentum", "oscillator_prev": 45,
                              "zone_crosses": {}, "zones": {},
                              "last_mr_type": None, "last_mr_bars_ago": None},
        "direction": "bullish",
        "price_structure": {"pdh": 105, "pdl": 98, "pmh": 108, "pml": 95},
    }
