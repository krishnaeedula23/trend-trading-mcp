from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch("api.endpoints.swing_weekly._get_supabase")
def test_list_weekly_groups_by_week(mock_sb):
    sb = FakeSupabaseClient()
    id1, id2 = str(uuid4()), str(uuid4())
    sb.table("swing_idea_snapshots").insert([
        {"id": 1, "idea_id": id1, "snapshot_date": "2026-04-12", "snapshot_type": "weekly", "claude_analysis": "NVDA: consolidating."},
        {"id": 2, "idea_id": id2, "snapshot_date": "2026-04-12", "snapshot_type": "weekly", "claude_analysis": "AMD: breaking."},
        {"id": 3, "idea_id": id1, "snapshot_date": "2026-04-05", "snapshot_type": "weekly", "claude_analysis": "NVDA: first base week."},
    ])
    sb.table("swing_ideas").insert([
        {"id": id1, "ticker": "NVDA", "status": "triggered", "cycle_stage": "base_n_break", "confluence_score": 7, "stop_price": 100.0, "setup_kell": "base_n_break", "direction": "long"},
        {"id": id2, "ticker": "AMD", "status": "triggered", "cycle_stage": "wedge_pop", "confluence_score": 6, "stop_price": 90.0, "setup_kell": "wedge_pop", "direction": "long"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get("/api/swing/weekly")
    assert r.status_code == 200
    weeks = r.json()
    assert len(weeks) == 2
    assert weeks[0]["week_of"] == "2026-04-12"
    assert len(weeks[0]["entries"]) == 2
