import uuid
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.endpoints import swing as swing_endpoints
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@pytest.fixture
def fake_sb(monkeypatch):
    monkeypatch.setenv("SWING_API_TOKEN", "tk")
    fake = FakeSupabaseClient()
    monkeypatch.setattr(swing_endpoints, "_get_supabase", lambda: fake)
    return fake


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seed_idea(fake_sb):
    idea_id = str(uuid.uuid4())
    fake_sb.table("swing_ideas").insert({
        "id": idea_id,
        "ticker": "NVDA",
        "cycle_stage": "wedge_pop",
        "setup_kell": "wedge_pop",
        "confluence_score": 7,
        "stop_price": 100.0,
        "status": "watching",
        "thesis_status": "pending",
        "base_thesis": None,
        "deep_thesis": None,
    }).execute()
    return idea_id


AUTH = {"Authorization": "Bearer tk"}


def test_thesis_write_requires_auth(client, seed_idea):
    r = client.post(f"/api/swing/ideas/{seed_idea}/thesis",
                    json={"layer": "base", "text": "Thesis here.", "model": "claude-opus-4-7"})
    assert r.status_code == 401


def test_thesis_write_base_updates_idea(client, fake_sb, seed_idea):
    r = client.post(
        f"/api/swing/ideas/{seed_idea}/thesis",
        headers=AUTH,
        json={"layer": "base", "text": "NVDA wedge pop with RS.", "model": "claude-opus-4-7"},
    )
    assert r.status_code == 200, r.text
    row = fake_sb.table("swing_ideas").select("*").eq("id", seed_idea).execute().data[0]
    assert row["base_thesis"] == "NVDA wedge pop with RS."
    assert row["base_thesis_at"] is not None
    assert row["thesis_status"] == "ready"


def test_thesis_write_deep_stores_sources_and_panel(client, fake_sb, seed_idea):
    r = client.post(
        f"/api/swing/ideas/{seed_idea}/thesis",
        headers=AUTH,
        json={
            "layer": "deep",
            "text": "Deep analysis body ...",
            "model": "claude-opus-4-7",
            "sources": ["https://deepvue.com/x", "tv-chart"],
            "deepvue_panel": {"rev_yoy": 0.42},
        },
    )
    assert r.status_code == 200
    row = fake_sb.table("swing_ideas").select("*").eq("id", seed_idea).execute().data[0]
    assert row["deep_thesis"] == "Deep analysis body ..."
    assert row["deep_thesis_sources"] == ["https://deepvue.com/x", "tv-chart"]
    # Deep does NOT flip thesis_status — that gates on base.
    assert row["base_thesis"] is None


def test_thesis_write_404_unknown_idea(client, fake_sb):
    r = client.post(
        f"/api/swing/ideas/{uuid.uuid4()}/thesis",
        headers=AUTH,
        json={"layer": "base", "text": "thesis text.", "model": "claude-opus-4-7"},
    )
    assert r.status_code == 404


def test_thesis_write_is_idempotent(client, fake_sb, seed_idea):
    key = str(uuid.uuid4())
    body = {"layer": "base", "text": "first version", "model": "claude-opus-4-7"}
    r1 = client.post(f"/api/swing/ideas/{seed_idea}/thesis", headers={**AUTH, "Idempotency-Key": key}, json=body)
    assert r1.status_code == 200

    r2 = client.post(f"/api/swing/ideas/{seed_idea}/thesis", headers={**AUTH, "Idempotency-Key": key},
                     json={"layer": "base", "text": "SECOND version", "model": "claude-opus-4-7"})
    assert r2.status_code == 200
    row = fake_sb.table("swing_ideas").select("*").eq("id", seed_idea).execute().data[0]
    assert row["base_thesis"] == "first version"
