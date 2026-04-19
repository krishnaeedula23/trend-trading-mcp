import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.endpoints import swing as swing_endpoints


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SWING_API_TOKEN", "tk")
    return TestClient(app)


AUTH = {"Authorization": "Bearer tk"}


def test_detect_requires_auth(client):
    r = client.post("/api/swing/ticker/NVDA/detect", json={})
    assert r.status_code == 401


def test_detect_happy_path(client):
    fake_hits = [{"setup_kell": "wedge_pop", "cycle_stage": "wedge_pop", "raw_score": 7,
                  "entry_zone": [100.0, 101.0], "stop_price": 99.0, "first_target": 110.0}]
    fake_fund = {"fundamentals": {}, "next_earnings_date": None, "beta": 1.2, "avg_daily_dollar_volume": 2e9}
    with patch.object(swing_endpoints, "_run_detectors_for_ticker", return_value=fake_hits), \
         patch.object(swing_endpoints, "_ticker_health_snapshot",
                      return_value={"qqq_above_20ema": True, "cycle": "green"}):
        with patch("api.endpoints.swing_ticker_service.fetch_fundamentals", return_value=fake_fund):
            r = client.post("/api/swing/ticker/NVDA/detect", headers=AUTH, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["data_sufficient"] is True
    assert len(body["setups"]) == 1
    assert body["market_health"]["cycle"] == "green"


def test_detect_insufficient_data(client):
    with patch.object(swing_endpoints, "_run_detectors_for_ticker",
                      side_effect=swing_endpoints.InsufficientData("only 30 bars")):
        r = client.post("/api/swing/ticker/ZZZ/detect", headers=AUTH, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["data_sufficient"] is False
    assert body["setups"] == []
    assert "only 30 bars" in body["reason"]
