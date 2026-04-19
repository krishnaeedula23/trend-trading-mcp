import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timezone

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


def _seed_idea(sb, **overrides):
    base = {
        "id": str(uuid4()),
        "ticker": "NVDA",
        "cycle_stage": "wedge_pop",
        "setup_kell": "wedge_pop",
        "confluence_score": 5,
        "entry_zone_low": 100.0, "entry_zone_high": 102.0,
        "stop_price": 98.0, "first_target": 110.0, "second_target": None,
        "status": "active",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "base_thesis": None, "thesis_status": "pending",
        "market_health": {}, "risk_flags": {}, "detection_evidence": {},
    }
    base.update(overrides)
    sb.table("swing_ideas").insert([base])
    return base


def test_list_ideas_no_filter_ordered_by_score(client, fake_sb):
    """Seed 3 ideas with scores 7, 5, 9. All returned ordered by score desc."""
    _seed_idea(fake_sb, ticker="AAPL", confluence_score=7)
    _seed_idea(fake_sb, ticker="TSLA", confluence_score=5)
    _seed_idea(fake_sb, ticker="NVDA", confluence_score=9)

    r = client.get("/api/swing/ideas")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    scores = [idea["confluence_score"] for idea in body["ideas"]]
    assert scores == sorted(scores, reverse=True)


def test_list_ideas_status_filter(client, fake_sb):
    """Seed 2 active + 1 exited; status=active returns only 2."""
    _seed_idea(fake_sb, ticker="AAPL", status="active")
    _seed_idea(fake_sb, ticker="TSLA", status="active")
    _seed_idea(fake_sb, ticker="MSFT", status="exited")

    r = client.get("/api/swing/ideas?status=active")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(idea["status"] == "active" for idea in body["ideas"])


def test_get_idea_by_id(client, fake_sb):
    """Seed 1 idea with known ID; GET by that ID returns matching body."""
    known_id = str(uuid4())
    seeded = _seed_idea(fake_sb, id=known_id, ticker="CRWD", confluence_score=8)

    r = client.get(f"/api/swing/ideas/{known_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "CRWD"
    assert body["confluence_score"] == 8
    assert body["id"] == known_id


def test_get_idea_not_found(client, fake_sb):
    """GET with a non-existent UUID returns 404."""
    r = client.get(f"/api/swing/ideas/{uuid4()}")
    assert r.status_code == 404


def test_list_ideas_thesis_status_filter(client, fake_sb):
    """?thesis_status=pending returns only ideas with that thesis_status."""
    _seed_idea(fake_sb, ticker="AAPL", thesis_status="pending")
    _seed_idea(fake_sb, ticker="NVDA", thesis_status="pending")
    _seed_idea(fake_sb, ticker="TSLA", thesis_status="ready")

    r = client.get("/api/swing/ideas?thesis_status=pending")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(idea["thesis_status"] == "pending" for idea in body["ideas"])


def test_list_ideas_ticker_filter(client, fake_sb):
    """?ticker=NVDA returns only rows for that ticker (case-insensitive)."""
    _seed_idea(fake_sb, ticker="NVDA", cycle_stage="wedge_pop")
    _seed_idea(fake_sb, ticker="NVDA", cycle_stage="ema_crossback")
    _seed_idea(fake_sb, ticker="AAPL")

    r = client.get("/api/swing/ideas?ticker=nvda")  # lowercase upstreams to NVDA
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(idea["ticker"] == "NVDA" for idea in body["ideas"])
