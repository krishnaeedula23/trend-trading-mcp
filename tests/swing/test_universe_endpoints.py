import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.endpoints import swing as swing_endpoints
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@pytest.fixture
def fake_sb(monkeypatch):
    fake = FakeSupabaseClient()
    monkeypatch.setattr(swing_endpoints, "_get_supabase", lambda: fake)
    return fake


@pytest.fixture
def client(fake_sb):
    return TestClient(app)


def test_get_universe_empty(client: TestClient):
    r = client.get("/api/swing/universe")
    assert r.status_code == 200
    data = r.json()
    assert data["active_count"] == 0
    assert data["tickers"] == []


def test_add_single_ticker_success(client, fake_sb):
    r = client.post("/api/swing/universe", json={"ticker": "nvda"})
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"
    assert r.json()["source"] == "manual"


def test_add_single_ticker_conflict(client, fake_sb):
    client.post("/api/swing/universe", json={"ticker": "NVDA"})
    r = client.post("/api/swing/universe", json={"ticker": "NVDA"})
    assert r.status_code == 409


def test_upload_csv_add_mode(client, fake_sb):
    csv_body = "ticker,revenue_growth\nAAPL,0.45\nNVDA,0.78\n"
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", csv_body, "text/csv")},
        data={"mode": "add"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tickers_added"] == 2
    assert body["tickers_removed"] == 0
    assert body["mode"] == "add"
    listing = client.get("/api/swing/universe").json()
    aapl = next(t for t in listing["tickers"] if t["ticker"] == "AAPL")
    assert aapl["extras"]["revenue_growth"] == "0.45"


def test_upload_csv_replace_mode(client, fake_sb):
    csv1 = "ticker\nAAPL\nNVDA\nMSFT\n"
    csv2 = "ticker\nNVDA\nCRWD\n"
    client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv1, "text/csv")}, data={"mode": "add"})
    r = client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv2, "text/csv")}, data={"mode": "replace"})
    assert r.status_code == 200
    assert r.json()["tickers_removed"] == 3
    assert r.json()["tickers_added"] == 2
    listing = client.get("/api/swing/universe").json()
    assert {t["ticker"] for t in listing["tickers"]} == {"NVDA", "CRWD"}


def test_upload_csv_missing_ticker_column(client, fake_sb):
    bad = "name,value\nFoo,1\n"
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", bad, "text/csv")},
        data={"mode": "add"},
    )
    assert r.status_code == 400


def test_upload_csv_non_csv_file(client, fake_sb):
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.txt", "AAPL", "text/plain")},
        data={"mode": "add"},
    )
    assert r.status_code == 400


def test_upload_csv_invalid_mode(client, fake_sb):
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", "ticker\nAAPL\n", "text/csv")},
        data={"mode": "wipe"},
    )
    assert r.status_code == 400


def test_remove_ticker_success(client, fake_sb):
    client.post("/api/swing/universe", json={"ticker": "AAPL"})
    r = client.delete("/api/swing/universe/AAPL")
    assert r.status_code == 200
    listing = client.get("/api/swing/universe").json()
    assert listing["active_count"] == 0


def test_remove_ticker_not_found(client, fake_sb):
    r = client.delete("/api/swing/universe/XYZXYZ")
    assert r.status_code == 404


def test_history_groups_by_batch(client, fake_sb):
    csv_body = "ticker\nAAPL\nNVDA\n"
    client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv_body, "text/csv")}, data={"mode": "add"})
    r = client.get("/api/swing/universe/history")
    assert r.status_code == 200
    batches = r.json()["batches"]
    assert any(b["ticker_count"] == 2 and b["source"] == "deepvue-csv" for b in batches)
