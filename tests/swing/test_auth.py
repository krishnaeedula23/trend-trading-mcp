import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from api.endpoints.swing_auth import require_swing_token, idempotent
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@pytest.fixture
def app_with_token(monkeypatch):
    monkeypatch.setenv("SWING_API_TOKEN", "testtoken123")
    app = FastAPI()

    @app.post("/write")
    def write(_=Depends(require_swing_token)):
        return {"ok": True}

    @app.get("/read")
    def read():
        return {"public": True}

    return app


def test_write_requires_bearer_token(app_with_token):
    client = TestClient(app_with_token)
    r = client.post("/write")
    assert r.status_code == 401


def test_write_rejects_wrong_token(app_with_token):
    client = TestClient(app_with_token)
    r = client.post("/write", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_write_accepts_correct_token(app_with_token):
    client = TestClient(app_with_token)
    r = client.post("/write", headers={"Authorization": "Bearer testtoken123"})
    assert r.status_code == 200


def test_read_does_not_require_token(app_with_token):
    client = TestClient(app_with_token)
    r = client.get("/read")
    assert r.status_code == 200


def test_require_swing_token_500s_if_env_missing(monkeypatch):
    monkeypatch.delenv("SWING_API_TOKEN", raising=False)
    app = FastAPI()

    @app.post("/w")
    def w(_=Depends(require_swing_token)):
        return {}

    client = TestClient(app)
    r = client.post("/w", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 500


def test_idempotent_returns_cached_on_second_call():
    sb = FakeSupabaseClient()
    key = "00000000-0000-0000-0000-000000000001"
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        return {"result": calls["n"]}

    first = idempotent(sb, key, "/test", handler)
    second = idempotent(sb, key, "/test", handler)
    assert first == {"result": 1}
    assert second == {"result": 1}       # cached
    assert calls["n"] == 1               # handler ran once


def test_idempotent_no_key_always_runs():
    sb = FakeSupabaseClient()
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        return {"result": calls["n"]}

    r1 = idempotent(sb, None, "/test", handler)
    r2 = idempotent(sb, None, "/test", handler)
    assert calls["n"] == 2
    assert r1 != r2
