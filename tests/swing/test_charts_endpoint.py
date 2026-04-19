from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_charts._get_supabase")
def test_post_chart_rejects_multiple_owners(mock_sb):
    mock_sb.return_value = FakeSupabaseClient()
    client = TestClient(app)
    r = client.post("/api/swing/charts", json={
        "image_url": "https://blob.vercel/x.png",
        "timeframe": "daily", "source": "deepvue-auto",
        "idea_id": str(uuid4()), "event_id": 1,
    }, headers={"Authorization": "Bearer t"})
    assert r.status_code == 400
    assert "exactly one" in r.json()["detail"].lower()


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_charts._get_supabase")
def test_post_chart_attached_to_idea(mock_sb):
    sb = FakeSupabaseClient()
    mock_sb.return_value = sb
    idea_id = str(uuid4())
    client = TestClient(app)
    r = client.post("/api/swing/charts", json={
        "image_url": "https://blob.vercel/x.png",
        "timeframe": "daily", "source": "user-markup",
        "idea_id": idea_id,
    }, headers={"Authorization": "Bearer t"})
    assert r.status_code == 201
    assert sb.table("swing_charts").rows[0]["idea_id"] == idea_id


@patch("api.endpoints.swing_charts._get_supabase")
def test_get_charts_by_idea(mock_sb):
    sb = FakeSupabaseClient()
    idea_id = str(uuid4())
    sb.table("swing_charts").insert([
        {"id": str(uuid4()), "idea_id": idea_id, "image_url": "a.png", "timeframe": "daily", "source": "deepvue-auto", "captured_at": "2026-04-19T00:00:00+00:00"},
        {"id": str(uuid4()), "idea_id": idea_id, "image_url": "b.png", "timeframe": "weekly", "source": "deepvue-auto", "captured_at": "2026-04-19T00:00:00+00:00"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get(f"/api/swing/ideas/{idea_id}/charts")
    assert r.status_code == 200
    assert len(r.json()) == 2
