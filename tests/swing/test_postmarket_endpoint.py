from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch("api.endpoints.swing_postmarket._get_supabase")
@patch("api.endpoints.swing_postmarket.run_swing_postmarket_snapshot")
def test_postmarket_endpoint_requires_bearer(mock_run, mock_sb, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "secret")
    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket")
    assert r.status_code == 401


@patch("api.endpoints.swing_postmarket._get_supabase")
@patch("api.endpoints.swing_postmarket.run_swing_postmarket_snapshot")
def test_postmarket_endpoint_rejects_wrong_token(mock_run, mock_sb, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "secret")
    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


@patch("api.endpoints.swing_postmarket._get_supabase")
@patch("api.endpoints.swing_postmarket.run_swing_postmarket_snapshot")
def test_postmarket_endpoint_runs_pipeline(mock_run, mock_sb, monkeypatch):
    from datetime import datetime, timezone
    from api.indicators.swing.pipeline.postmarket import PostmarketResult
    monkeypatch.setenv("CRON_SECRET", "secret")

    mock_sb.return_value = FakeSupabaseClient()
    mock_run.return_value = PostmarketResult(
        ran_at=datetime.now(timezone.utc),
        active_ideas_processed=3, stage_transitions=1,
        exhaustion_warnings=1, stop_violations=0, snapshots_written=3,
    )

    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["active_ideas_processed"] == 3
    assert body["snapshots_written"] == 3
