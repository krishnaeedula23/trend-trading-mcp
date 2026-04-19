from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_model_book._get_supabase")
def test_create_model_book_entry(mock_sb):
    mock_sb.return_value = FakeSupabaseClient()
    client = TestClient(app)
    r = client.post("/api/swing/model-book", json={
        "title": "NVDA 2024 base-n-break winner",
        "ticker": "NVDA",
        "setup_kell": "base_n_break",
        "outcome": "winner",
        "r_multiple": 4.2,
        "narrative": "Textbook 6-week base, breakout on earnings.",
        "key_takeaways": ["Volume confirms the break", "Hold 20-EMA"],
        "tags": ["semis", "AI"],
    }, headers={"Authorization": "Bearer t"})
    assert r.status_code == 201
    assert r.json()["title"].startswith("NVDA")


@patch("api.endpoints.swing_model_book._get_supabase")
def test_list_model_book_filters_by_setup(mock_sb):
    sb = FakeSupabaseClient()
    sb.table("swing_model_book").insert([
        {"id": str(uuid4()), "title": "A", "ticker": "A", "setup_kell": "wedge_pop", "outcome": "winner", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
        {"id": str(uuid4()), "title": "B", "ticker": "B", "setup_kell": "base_n_break", "outcome": "winner", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get("/api/swing/model-book?setup_kell=wedge_pop")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["ticker"] == "A"


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_model_book._get_supabase")
def test_patch_narrative(mock_sb):
    sb = FakeSupabaseClient()
    entry_id = str(uuid4())
    sb.table("swing_model_book").insert([{"id": entry_id, "title": "X", "ticker": "X", "setup_kell": "wedge_pop", "outcome": "example", "narrative": "old", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.patch(f"/api/swing/model-book/{entry_id}", json={"narrative": "updated"}, headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert sb.table("swing_model_book").rows[0]["narrative"] == "updated"
