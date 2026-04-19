from datetime import date
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_snapshots._get_supabase")
def test_mac_can_attach_claude_analysis_to_existing_snapshot(mock_sb):
    idea_id = str(uuid4())
    sb = FakeSupabaseClient()
    sb.table("swing_idea_snapshots").insert([{
        "id": 1, "idea_id": idea_id, "snapshot_date": "2026-04-18",
        "snapshot_type": "daily", "daily_close": 100.0,
    }])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.post(f"/api/swing/ideas/{idea_id}/snapshots", json={
        "snapshot_date": "2026-04-18",
        "snapshot_type": "daily",
        "claude_analysis": "Constructive setup; waiting for volume confirmation.",
        "claude_model": "claude-opus-4-7",
        "chart_daily_url": "https://blob.vercel/d.png",
    }, headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    row = sb.table("swing_idea_snapshots").rows[0]
    assert row["claude_analysis"].startswith("Constructive")
    assert row["daily_close"] == 100.0  # preserved


@patch("api.endpoints.swing_snapshots._get_supabase")
def test_get_snapshots_by_idea(mock_sb):
    idea_id = str(uuid4())
    sb = FakeSupabaseClient()
    sb.table("swing_idea_snapshots").insert([
        {"id": 1, "idea_id": idea_id, "snapshot_date": "2026-04-15", "snapshot_type": "daily"},
        {"id": 2, "idea_id": idea_id, "snapshot_date": "2026-04-16", "snapshot_type": "daily"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get(f"/api/swing/ideas/{idea_id}/snapshots")
    assert r.status_code == 200
    assert len(r.json()) == 2
