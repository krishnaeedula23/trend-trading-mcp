# tests/swing/test_universe_refresh_endpoint.py
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api.indicators.swing.pipeline.universe_refresh import run_swing_universe_refresh
from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def test_skip_when_deepvue_is_fresh():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    sb.table("swing_universe").insert([{
        "id": 1, "ticker": "NVDA", "source": "deepvue-csv", "batch_id": str(uuid4()),
        "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None,
    }])
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is True
    assert "deepvue" in result["skip_reason"].lower()


@patch("api.indicators.swing.pipeline.universe_refresh.generate_backend_universe")
def test_runs_generator_when_universe_stale(mock_gen):
    sb = FakeSupabaseClient()
    mock_gen.return_value = {
        "passers": {"AAPL": {"fundamentals": {"quarterly_revenue_yoy": [0.45]}}},
        "stats": {"base_count": 100, "stage12_count": 50, "stage3_count": 10, "final_count": 1},
    }
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is False
    assert result["final_count"] == 1
    rows = sb.table("swing_universe").rows
    assert any(r["ticker"] == "AAPL" and r["source"] == "backend-generated" for r in rows)


@patch("api.endpoints.swing_postmarket._get_supabase")
def test_universe_refresh_endpoint_requires_bearer(mock_sb, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "secret")
    client = TestClient(app)
    r = client.post("/api/swing/pipeline/universe-refresh")
    assert r.status_code == 401


@patch("api.endpoints.swing_postmarket.run_swing_universe_refresh")
@patch("api.endpoints.swing_postmarket._get_supabase")
def test_universe_refresh_endpoint_runs_helper(mock_sb, mock_run, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "secret")
    mock_sb.return_value = FakeSupabaseClient()
    mock_run.return_value = {
        "ran_at": "2026-04-19T00:00:00+00:00",
        "skipped": False,
        "skip_reason": None,
        "base_count": 500,
        "final_count": 42,
        "batch_id": "00000000-0000-0000-0000-000000000000",
    }
    client = TestClient(app)
    r = client.post("/api/swing/pipeline/universe-refresh", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["final_count"] == 42
    assert body["skipped"] is False
