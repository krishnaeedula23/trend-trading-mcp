"""Endpoint tests for the morning screener API."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints.screener_morning import router as screener_router
from api.schemas.screener import (
    IndicatorOverlay,
    ScreenerRunResponse,
    TickerResult,
)


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(screener_router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def test_run_morning_endpoint_calls_runner(client):
    fake_response = ScreenerRunResponse(
        run_id="run-1",
        mode="swing",
        ran_at=datetime.now(timezone.utc),
        universe_size=10,
        scan_count=1,
        hit_count=1,
        duration_seconds=1.2,
        tickers=[TickerResult(
            ticker="NVDA",
            last_close=900.0,
            overlay=IndicatorOverlay(atr_pct=0.03, pct_from_50ma=0.05, extension=1.67, sma_50=857.0, atr_14=27.0),
            scans_hit=["coiled_spring"],
            confluence=1,
        )],
    )
    with patch("api.endpoints.screener_morning._resolve_active_universe", return_value=["NVDA"]):
        with patch("api.endpoints.screener_morning.fetch_daily_bars_bulk", return_value={"NVDA": MagicMock()}):
            with patch("api.endpoints.screener_morning.run_screener", return_value=fake_response):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post("/api/screener/morning/run", json={"mode": "swing"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "swing"
    assert body["tickers"][0]["ticker"] == "NVDA"


def test_universe_show_endpoint(client):
    with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL", "TSLA"], "deepvue")):
        with patch("api.endpoints.screener_morning.list_overrides", return_value=(["NVDA"], ["TSLA"])):
            with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                res = client.get("/api/screener/universe?mode=swing")
    assert res.status_code == 200
    body = res.json()
    assert "NVDA" in body["effective_tickers"]
    assert "TSLA" not in body["effective_tickers"]
    assert "AAPL" in body["effective_tickers"]
    assert body["base_source"] == "deepvue"


def test_universe_update_add_action(client):
    with patch("api.endpoints.screener_morning.add_overrides") as mock_add:
        with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL"], "deepvue")):
            with patch("api.endpoints.screener_morning.list_overrides", return_value=(["NVDA"], [])):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post(
                        "/api/screener/universe/update",
                        json={"mode": "swing", "action": "add", "tickers": ["NVDA"]},
                    )
    assert res.status_code == 200
    mock_add.assert_called_once()
    body = res.json()
    assert "NVDA" in body["overrides_added"]


def test_universe_update_clear_overrides(client):
    with patch("api.endpoints.screener_morning.clear_overrides") as mock_clear:
        with patch("api.endpoints.screener_morning._resolve_base_universe", return_value=(["AAPL"], "deepvue")):
            with patch("api.endpoints.screener_morning.list_overrides", return_value=([], [])):
                with patch("api.endpoints.screener_morning._get_supabase", return_value=MagicMock()):
                    res = client.post(
                        "/api/screener/universe/update",
                        json={"mode": "swing", "action": "clear_overrides"},
                    )
    assert res.status_code == 200
    mock_clear.assert_called_once()
