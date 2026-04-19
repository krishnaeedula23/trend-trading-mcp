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
def idea_id(fake_sb):
    i = str(uuid.uuid4())
    fake_sb.table("swing_ideas").insert({
        "id": i, "ticker": "AMD", "cycle_stage": "ema_crossback",
        "setup_kell": "ema_crossback", "confluence_score": 6,
        "stop_price": 150.0, "status": "watching", "thesis_status": "pending",
    }).execute()
    return i


AUTH = {"Authorization": "Bearer tk"}


def test_events_requires_auth(client, idea_id):
    r = client.post(f"/api/swing/ideas/{idea_id}/events",
                    json={"event_type": "user_note", "payload": None, "summary": "hi"})
    assert r.status_code == 401


def test_events_inserts_row(client, fake_sb, idea_id):
    r = client.post(
        f"/api/swing/ideas/{idea_id}/events",
        headers=AUTH,
        json={"event_type": "user_note", "payload": {"txt": "looks strong"}, "summary": "user note"},
    )
    assert r.status_code == 200, r.text
    rows = fake_sb.table("swing_events").select("*").eq("idea_id", idea_id).execute().data
    assert len(rows) == 1
    assert rows[0]["event_type"] == "user_note"
    assert rows[0]["summary"] == "user note"


def test_events_404_unknown_idea(client, fake_sb):
    r = client.post(
        f"/api/swing/ideas/{uuid.uuid4()}/events",
        headers=AUTH,
        json={"event_type": "user_note", "summary": "x"},
    )
    assert r.status_code == 404


def test_events_idempotent(client, fake_sb, idea_id):
    key = str(uuid.uuid4())
    body = {"event_type": "user_note", "summary": "once"}
    r1 = client.post(f"/api/swing/ideas/{idea_id}/events", headers={**AUTH, "Idempotency-Key": key}, json=body)
    r2 = client.post(f"/api/swing/ideas/{idea_id}/events", headers={**AUTH, "Idempotency-Key": key}, json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    rows = fake_sb.table("swing_events").select("*").eq("idea_id", idea_id).execute().data
    assert len(rows) == 1  # dedup'd
