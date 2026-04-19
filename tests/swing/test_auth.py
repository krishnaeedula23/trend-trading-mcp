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


def test_idempotent_recovers_on_insert_conflict():
    """Concurrent-writer race: handler runs, another writer planted the cached
    response mid-flight, our INSERT raises unique_violation. We must catch,
    re-SELECT, and return the other writer's response instead of bubbling 500.

    Simulate real Postgres PK-conflict semantics by wrapping the
    swing_idempotency_keys table's insert so it raises when the incoming row's
    `key` is already present in the table.
    """
    sb = FakeSupabaseClient()
    real_table = sb.table

    class PKEnforcingTable:
        def __init__(self, t):
            self._t = t
        def __getattr__(self, name):
            return getattr(self._t, name)
        def insert(self, rows):
            row_list = [rows] if isinstance(rows, dict) else rows
            existing_keys = {r["key"] for r in self._t.rows if "key" in r}
            for r in row_list:
                if r.get("key") in existing_keys:
                    raise RuntimeError("duplicate key value violates unique constraint")
            return self._t.insert(rows)

    def patched_table(name):
        t = real_table(name)
        return PKEnforcingTable(t) if name == "swing_idempotency_keys" else t

    sb.table = patched_table  # type: ignore[method-assign]

    race_key = "00000000-0000-0000-0000-000000000003"
    handler_ran = {"n": 0}

    def handler():
        handler_ran["n"] += 1
        # Simulate the other writer winning between our initial SELECT-miss and
        # our INSERT: they plant the cached response first.
        sb.table("swing_idempotency_keys").insert({
            "key": race_key,
            "endpoint": "/test",
            "response_json": {"result": "winner_race"},
        }).execute()
        return {"result": "loser_race"}

    result = idempotent(sb, race_key, "/test", handler)

    assert handler_ran["n"] == 1
    assert result == {"result": "winner_race"}
