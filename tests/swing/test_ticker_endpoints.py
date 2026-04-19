import pandas as pd
import pytest
from fastapi.testclient import TestClient
from datetime import date

from api.main import app
from api.endpoints import swing as swing_endpoints
from api.endpoints import swing_ticker_service as svc


@pytest.fixture
def client():
    return TestClient(app)


def _fake_bars(days: int, tf: str = "daily") -> pd.DataFrame:
    dates = pd.date_range("2026-01-02", periods=days, freq="B")
    return pd.DataFrame({
        "date": dates, "open": 100.0, "high": 101.0, "low": 99.0,
        "close": 100.5, "volume": 1_000_000,
    })


def test_bars_returns_requested_lookback(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_bars", lambda t, tf, lookback: _fake_bars(lookback))
    r = client.get("/api/swing/ticker/NVDA/bars?tf=daily&lookback=30")
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"
    assert len(r.json()["bars"]) == 30


def test_bars_rejects_bad_tf(client):
    r = client.get("/api/swing/ticker/NVDA/bars?tf=1m&lookback=30")
    assert r.status_code == 422


def test_bars_rejects_unknown_ticker(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_bars", lambda *a, **k: pd.DataFrame())
    r = client.get("/api/swing/ticker/ZZZZZ/bars?tf=daily&lookback=30")
    assert r.status_code == 404


def test_fundamentals_returns_shape(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_fundamentals", lambda t: {
        "fundamentals": {"trailingPE": 30.0, "marketCap": 1e12},
        "next_earnings_date": date(2026, 5, 20),
        "beta": 1.6,
        "avg_daily_dollar_volume": 5e9,
    })
    r = client.get("/api/swing/ticker/NVDA/fundamentals")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["beta"] == 1.6
