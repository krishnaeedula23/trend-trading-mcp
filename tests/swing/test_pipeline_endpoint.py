"""Tests for POST /api/swing/pipeline/premarket endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.endpoints import swing as swing_endpoints
from tests.fixtures.swing_fixtures import FakeSupabaseClient

# Canned return value for monkey-patched run_premarket_detection
_CANNED_RESULT = {
    "new_ideas": 3,
    "transitions": 1,
    "invalidations": 0,
    "universe_source": "deepvue-csv",
    "universe_size": 10,
    "market_health": {"trend": "bullish"},
}


@pytest.fixture
def fake_sb(monkeypatch):
    fake = FakeSupabaseClient()
    monkeypatch.setattr(swing_endpoints, "_get_supabase", lambda: fake)
    return fake


@pytest.fixture
def client(fake_sb):
    return TestClient(app)


@pytest.fixture
def patched_pipeline(monkeypatch):
    """Monkey-patch run_premarket_detection so no real bars/DB needed."""
    import api.endpoints.swing as ep
    # The endpoint does a local import; patch the module-level function in pipeline
    import api.indicators.swing.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "run_premarket_detection", lambda sb: _CANNED_RESULT)
    return _CANNED_RESULT


def test_no_cron_secret_skips_auth(client, patched_pipeline, monkeypatch):
    """When CRON_SECRET env var is not set, request succeeds without auth header."""
    monkeypatch.delenv("CRON_SECRET", raising=False)
    r = client.post("/api/swing/pipeline/premarket")
    assert r.status_code == 200
    body = r.json()
    assert body["new_ideas"] == 3
    assert body["universe_source"] == "deepvue-csv"


def test_missing_auth_header_returns_401(client, patched_pipeline, monkeypatch):
    """When CRON_SECRET is set and Authorization header is absent, return 401."""
    monkeypatch.setenv("CRON_SECRET", "testkey")
    r = client.post("/api/swing/pipeline/premarket")
    assert r.status_code == 401


def test_wrong_token_returns_401(client, patched_pipeline, monkeypatch):
    """When CRON_SECRET is set and wrong token is supplied, return 401."""
    monkeypatch.setenv("CRON_SECRET", "testkey")
    r = client.post("/api/swing/pipeline/premarket", headers={"Authorization": "Bearer wrongtoken"})
    assert r.status_code == 401


def test_correct_token_returns_200_with_shape(client, patched_pipeline, monkeypatch):
    """Correct Bearer token returns 200 with expected response shape."""
    monkeypatch.setenv("CRON_SECRET", "testkey")
    r = client.post(
        "/api/swing/pipeline/premarket",
        headers={"Authorization": "Bearer testkey"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["new_ideas"] == 3
    assert body["transitions"] == 1
    assert body["invalidations"] == 0
    assert body["universe_source"] == "deepvue-csv"
    assert body["universe_size"] == 10
    assert body["market_health"] == {"trend": "bullish"}
