# Plan 3 — Claude Analysis Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Reference Plans 1 and 2 for conventions.

**Goal:** Wire Claude-on-Mac (Max subscription) into the swing system so base theses, ad-hoc ticker analysis, and idea reviews flow between the user's Mac and Railway — with zero Claude API spend on Railway.

**Architecture:** Railway gets a bearer-auth layer on write endpoints (`SWING_API_TOKEN`) plus three new write endpoints (thesis, events, on-demand detect) and two new read endpoints (bars, fundamentals) — all pure Python, no LLM imports. Mac-side, four `.claude/skills/*.md` slash commands drive the Claude Code CLI: one scheduled (`/swing-analyze-pending` at 6:30am PT via `scheduled-tasks` MCP) and three ad-hoc (`/swing-analyze`, `/swing-review`, `/swing-compare`). Frontend gains a `/swing-ideas/[id]` detail page and a thesis preview on Plan 2's Active/Watching list.

**Tech Stack:** Python 3.12 + FastAPI + Supabase (Railway side), Claude Code CLI + `scheduled-tasks` MCP + shell `curl` (Mac side), Next.js 16 + React 19 + Tailwind 4 + SWR hook pattern (frontend). No Anthropic SDK anywhere in Railway.

**Reference:**
- Spec: [docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md](../specs/2026-04-18-kell-saty-swing-system-design.md) — especially Sections 8 (Claude Analysis Layer), 9[B][D][E] (Mac scheduled tasks), 5 (data model).
- Plan 1: [docs/superpowers/plans/2026-04-18-plan-1-foundation-universe.md](./2026-04-18-plan-1-foundation-universe.md) — conventions: `_get_supabase()` singleton pattern, `FakeSupabaseClient`, file layout, TDD/commit cadence, `railwayFetch` proxy, Alembic-bypass-via-MCP.
- Plan 2: `docs/superpowers/plans/2026-04-18-plan-2-detection-pipeline.md` (merged to main before Plan 3 executes) — provides `GET /api/swing/ideas`, the ideas list hook, and the Active/Watching tab scaffolding that this plan extends.
- Kell notes: [docs/kell/source-notes.md](../../kell/source-notes.md) — terminology reference.

---

## File Structure (created/modified by this plan)

**Backend — new:**
- `docs/schema/017_add_swing_idempotency_keys.sql` — SQL for `swing_idempotency_keys` table (applied via Supabase MCP `apply_migration` or SQL Editor; no Alembic)
- `api/endpoints/swing_auth.py` — shared bearer-token dependency + idempotency helper
- `api/endpoints/swing_ticker_service.py` — thin wrapper around yfinance + Plan 2 detectors for `/ticker/<T>/*` routes (keeps the router file lean)

**Backend — modified:**
- `api/endpoints/swing.py` — add 5 new routes (`POST /ideas/<id>/thesis`, `POST /ideas/<id>/events`, `POST /ticker/<T>/detect`, `GET /ticker/<T>/bars`, `GET /ticker/<T>/fundamentals`); apply auth dependency to writes
- `api/schemas/swing.py` — append Pydantic models (`ThesisWriteRequest`, `EventWriteRequest`, `TickerDetectResponse`, `TickerBarsResponse`, `TickerFundamentalsResponse`)

**Backend — tests:**
- `tests/swing/test_auth.py` — bearer-token + idempotency unit tests
- `tests/swing/test_thesis_endpoint.py`
- `tests/swing/test_events_endpoint.py`
- `tests/swing/test_ticker_endpoints.py`
- `tests/swing/test_ticker_detect_endpoint.py`

**Mac-side — new (checked into repo):**
- `.claude/skills/swing-analyze-pending.md`
- `.claude/skills/swing-analyze.md`
- `.claude/skills/swing-review.md`
- `.claude/skills/swing-compare.md`
- `.claude/skills/_swing-shared.md` — shared "Prerequisites to verify" + auth-token-reading snippet referenced by the other four
- `scripts/swing/bootstrap-mac.sh` — one-shot: writes token file, registers `scheduled-tasks` MCP entry, runs pre-flight checks

**Frontend — new:**
- `frontend/src/app/swing-ideas/[id]/page.tsx` — idea detail page (thesis + timeline stub + base info)
- `frontend/src/components/swing/thesis-panel.tsx` — renders base + deep thesis with "pending" state
- `frontend/src/components/swing/idea-header.tsx` — sticky ticker/status/cycle-stage header
- `frontend/src/components/swing/idea-timeline.tsx` — timeline stub (Plan 4 fills events/snapshots)
- `frontend/src/hooks/use-swing-idea-detail.ts` — SWR hook for a single idea
- `frontend/src/app/api/swing/ideas/[id]/route.ts` — GET proxy for single idea (Plan 2 owns the list proxy)

**Frontend — modified:**
- `frontend/src/components/swing/active-list.tsx` (created in Plan 2) — add expanded-row base thesis preview
- `frontend/src/lib/types.ts` — append `SwingThesis`, `SwingEvent`, `SwingIdeaDetail` types

---

## Cross-cutting Conventions

These apply to every task in this plan. Reference them; don't restate them.

### C-1. Supabase access

Use Plan 1's `_get_supabase()` singleton in `api/endpoints/swing.py`. Do not introduce FastAPI `Depends` for Supabase. Tests monkey-patch `swing_endpoints._get_supabase` using Plan 1's `FakeSupabaseClient` fixture.

### C-2. Auth (new in this plan)

All **write** endpoints added here (POST) require a shared bearer token.
- Railway env var: `SWING_API_TOKEN` (32-byte hex)
- Mac file: `~/.config/trend-trading-mcp/swing-api.token` (mode 600, first line = token)
- Header: `Authorization: Bearer <token>`
- Implementation: FastAPI dependency (`require_swing_token`) — **not** a middleware — applied per-route.
- **Read endpoints (GET) remain unauthenticated** — matches the existing repo pattern where `/api/swing/universe`, `/api/swing/ideas`, etc. are open. Public data, private writes.
- Rotation: edit env var on Railway → edit token file on Mac → no code change.

### C-3. Idempotency

Write endpoints accept optional `Idempotency-Key: <uuid>` header. A new Supabase table `swing_idempotency_keys` dedupes for 24h.

```sql
-- docs/schema/017_add_swing_idempotency_keys.sql
CREATE TABLE swing_idempotency_keys (
  key UUID PRIMARY KEY,
  endpoint TEXT NOT NULL,
  response_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX swing_idempotency_keys_created
  ON swing_idempotency_keys (created_at);
-- Clean-up (manual or pg_cron): DELETE FROM swing_idempotency_keys WHERE created_at < NOW() - INTERVAL '24 hours';
```

Helper flow (see Task 2 for the `idempotent()` wrapper):
1. On request with `Idempotency-Key`: look up key. Hit → return stored `response_json` verbatim. Miss → execute handler, store result, return it.
2. No key header → handler runs unconditionally (no persistence).
3. If handler raises, do not persist.

### C-4. Alembic bypass

New tables ship via `docs/schema/<NNN>_add_<name>.sql`. Implementer applies it via Supabase MCP `apply_migration` **or** Supabase SQL Editor. **Do not** add an Alembic revision for Plan 3 tables.

### C-5. Zero Claude API spend

After every commit in this plan:
```bash
grep -r "^import anthropic\|^from anthropic" api/ --include='*.py' | grep -v tests/
```
Expected: empty output. If non-empty, stop and remove the import.

### C-6. Python env

`.venv/bin/python` (not `venv/`). Pytest: `.venv/bin/python -m pytest tests/swing/ -v`.

### C-7. Frontend proxy

All frontend routes call `railwayFetch("/api/swing/...")` — matches Plan 1's `frontend/src/app/api/swing/universe/route.ts`. **Read endpoints need no auth header.** If a future write-from-browser is needed, add the token to Vercel env and forward it — not in this plan. All writes in Plan 3 come from Mac, not the browser.

### C-8. Slash command skill format

`.claude/skills/<name>.md` files follow the format used elsewhere in the repo's `.claude/skills/` (trading skills like `/note`, `/journal`). Front matter header + a procedural body. See Task 10 for the template.

### C-9. Commit cadence

One commit per task step completion. Commit messages follow the repo's existing style (recent history: `feat: ...`, `fix: ...`, `docs: ...`, lowercase type, imperative). Include the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.

---

## Task 1: Prerequisites verification (ONE-TIME, before any code)

This task is documentation + manual verification. **No code changes.** It gates the architecture. If any check fails, STOP and record the failure in "Open Questions" before proceeding.

**Files:** none (outputs go in implementer's scratchpad + plan-execution log)

- [ ] **Step 1: Verify `scheduled-tasks` MCP is installed and functional on Mac**

```bash
# On the user's Mac, in any Claude Code session:
claude mcp list | grep scheduled-tasks
```

Expected: row present. If missing, install per the `anthropic-skills:schedule` skill docs.

- [ ] **Step 2: Verify `scheduled-tasks` fires when Mac is awake + Claude Code is idle**

Create a throwaway scheduled task that fires in 2 minutes writing `echo ok > /tmp/sched-ok.txt`. Wait 3 min. Verify file exists. Delete the task.

Record behaviors observed:
- Does it fire with lid closed? (Spec §8 prereq 1a — expected: no, unless plugged in + caffeinate)
- Does it launch a new Claude Code session, or inject into an existing one? (Spec §8 prereq 1b)
- Does it queue or fail silently if Mac is asleep at fire time? (Spec §8 prereq 1c)

Document in plan-execution log. **If closed-lid firing fails:** fallback is macOS `launchd` + `caffeinate -s` wrapper (captured as "Open Question" — don't block Plan 3 MVP; daily runs assume lid-open during market hours).

- [ ] **Step 3: Verify Claude Code CLI can run a slash command headlessly**

```bash
claude -p "/help" --print --output-format text | head -20
```

Expected: prints help. If `claude` CLI can't run non-interactively, Plan 3's `scheduled-tasks` integration is broken — stop and escalate.

- [ ] **Step 4: Confirm `SWING_API_TOKEN` is not yet set on Railway**

```bash
# From repo root, with Railway CLI authed:
railway variables | grep SWING_API_TOKEN || echo "not set"
```

Expected: `not set`. We set it in Task 4.

- [ ] **Step 5: Commit the prereq log**

```bash
git add docs/superpowers/plans/2026-04-18-plan-3-claude-analysis-layer.md  # (if you edited the Open Questions section with findings)
git commit -m "docs(swing): record Plan 3 prerequisite verification results

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

(If no edits, skip this commit.)

---

## Task 2: Supabase table for idempotency keys (no Alembic)

**Files:**
- Create: `docs/schema/017_add_swing_idempotency_keys.sql`

- [ ] **Step 1: Write the SQL**

```sql
-- docs/schema/017_add_swing_idempotency_keys.sql
-- Dedupe repeated POSTs from Mac-Claude retries. 24h window.
-- Applied via Supabase MCP `apply_migration` or the Supabase SQL Editor.
-- NOT tracked in Alembic — matches the Plan 1/2 convention.

CREATE TABLE IF NOT EXISTS swing_idempotency_keys (
  key UUID PRIMARY KEY,
  endpoint TEXT NOT NULL,
  response_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS swing_idempotency_keys_created
  ON swing_idempotency_keys (created_at);

-- Manual cleanup (or schedule via pg_cron once available):
-- DELETE FROM swing_idempotency_keys WHERE created_at < NOW() - INTERVAL '24 hours';
```

- [ ] **Step 2: Apply the migration**

Instruct the operator (has Supabase MCP): run `mcp__supabase__apply_migration` with the file contents, OR paste into Supabase SQL Editor → Run.

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT 1 FROM information_schema.tables WHERE table_name='swing_idempotency_keys'\")
print('table exists' if cur.fetchone() else 'MISSING')
"
```

Expected: `table exists`.

- [ ] **Step 4: Commit**

```bash
git add docs/schema/017_add_swing_idempotency_keys.sql
git commit -m "feat(swing): add swing_idempotency_keys table SQL

24h dedupe for Mac-side POST retries. Applied via Supabase MCP, not Alembic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Auth + idempotency helpers (TDD)

**Files:**
- Create: `api/endpoints/swing_auth.py`
- Create: `tests/swing/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_auth.py
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
```

- [ ] **Step 2: Run — fail (ImportError)**

```bash
.venv/bin/python -m pytest tests/swing/test_auth.py -v
```

- [ ] **Step 3: Implement `swing_auth.py`**

```python
# api/endpoints/swing_auth.py
"""Auth dependency + idempotency helper for Mac-Claude → Railway writes.

- `require_swing_token`: FastAPI dependency validating `Authorization: Bearer ...`
   against env `SWING_API_TOKEN`. Applied to POST endpoints only.
- `idempotent(sb, key, endpoint, handler)`: if `key` is given and seen within
   24h, returns the stored response; otherwise runs `handler` and stores it.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from fastapi import Header, HTTPException


def require_swing_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SWING_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="SWING_API_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization[len("Bearer ") :] != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def idempotent(sb, key: str | None, endpoint: str, handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Dedupe by Idempotency-Key for 24h. No-op if key is None.

    On hit: returns stored response.
    On miss: runs handler, stores response, returns it.
    Exceptions propagate; nothing is stored on error.
    """
    if key is None:
        return handler()

    existing = sb.table("swing_idempotency_keys").select("response_json").eq("key", key).execute().data or []
    if existing:
        return existing[0]["response_json"]

    result = handler()
    sb.table("swing_idempotency_keys").insert({
        "key": key,
        "endpoint": endpoint,
        "response_json": result,
    }).execute()
    return result
```

- [ ] **Step 4: Run — pass**

```bash
.venv/bin/python -m pytest tests/swing/test_auth.py -v
```

Expected: 7 passing.

- [ ] **Step 5: Grep for anthropic imports**

```bash
grep -r "^import anthropic\|^from anthropic" api/ --include='*.py' | grep -v tests/
```

Expected: empty.

- [ ] **Step 6: Commit**

```bash
git add api/endpoints/swing_auth.py tests/swing/test_auth.py
git commit -m "feat(swing): add bearer-token auth + idempotency helpers

Dependency for write endpoints + 24h POST retry dedupe via swing_idempotency_keys.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Set `SWING_API_TOKEN` on Railway + write Mac token file

**Files:** none (env + filesystem only)

- [ ] **Step 1: Generate token**

```bash
TOKEN=$(.venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
echo "$TOKEN"
```

- [ ] **Step 2: Set on Railway**

```bash
railway variables --set SWING_API_TOKEN="$TOKEN"
# Verify:
railway variables | grep SWING_API_TOKEN
```

- [ ] **Step 3: Write to Mac token file**

```bash
mkdir -p ~/.config/trend-trading-mcp
printf '%s' "$TOKEN" > ~/.config/trend-trading-mcp/swing-api.token
chmod 600 ~/.config/trend-trading-mcp/swing-api.token
# Verify:
test -r ~/.config/trend-trading-mcp/swing-api.token && echo "readable" || echo "MISSING"
stat -f '%A' ~/.config/trend-trading-mcp/swing-api.token   # macOS: expect 600
```

- [ ] **Step 4: Trigger a Railway redeploy so the env var is live**

```bash
railway redeploy --yes
# Wait ~60s, then:
curl -sf https://<your-railway-domain>/healthz && echo "UP"
```

- [ ] **Step 5: No commit** (env + filesystem, no repo changes).

Record the Railway deploy SHA + timestamp in the plan-execution log.

---

## Task 5: Pydantic schemas for new endpoints

**Files:**
- Modify: `api/schemas/swing.py`

- [ ] **Step 1: Append to `api/schemas/swing.py`**

```python
# api/schemas/swing.py  — APPEND below Plan 1/2 models

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ThesisWriteRequest(BaseModel):
    layer: Literal["base", "deep"]
    text: str = Field(min_length=10, max_length=20_000)
    model: str                            # e.g. "claude-opus-4-7"
    sources: list[str] | None = None      # URLs/filenames referenced
    deepvue_panel: dict | None = None     # deep-layer only; base can pass None


class ThesisWriteResponse(BaseModel):
    idea_id: str
    layer: Literal["base", "deep"]
    updated_at: str


class EventWriteRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict | None = None
    summary: str | None = Field(default=None, max_length=2_000)


class EventWriteResponse(BaseModel):
    event_id: int
    idea_id: str
    occurred_at: str


class TickerBarEntry(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class TickerBarsResponse(BaseModel):
    ticker: str
    tf: Literal["daily", "weekly", "60m"]
    bars: list[TickerBarEntry]


class TickerFundamentalsResponse(BaseModel):
    ticker: str
    fundamentals: dict
    next_earnings_date: date | None = None
    beta: float | None = None
    avg_daily_dollar_volume: float | None = None


class TickerDetectResponse(BaseModel):
    ticker: str
    setups: list[dict]           # serialized SetupHit rows from Plan 2
    fundamentals: dict
    market_health: dict
    data_sufficient: bool        # false if yfinance returned <60 bars
    reason: str | None = None    # populated when data_sufficient=false
```

- [ ] **Step 2: Verify import**

```bash
.venv/bin/python -c "from api.schemas.swing import ThesisWriteRequest, TickerDetectResponse; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add api/schemas/swing.py
git commit -m "feat(swing): add Pydantic schemas for thesis/events/ticker endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `POST /api/swing/ideas/<id>/thesis` (TDD)

**Files:**
- Modify: `api/endpoints/swing.py`
- Create: `tests/swing/test_thesis_endpoint.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_thesis_endpoint.py
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
    # (But base_thesis remains None here, confirming separation.)
    assert row["base_thesis"] is None


def test_thesis_write_404_unknown_idea(client):
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

    # Second call with SAME key but DIFFERENT body: returns first response, doesn't overwrite.
    r2 = client.post(f"/api/swing/ideas/{seed_idea}/thesis", headers={**AUTH, "Idempotency-Key": key},
                     json={"layer": "base", "text": "SECOND version", "model": "claude-opus-4-7"})
    assert r2.status_code == 200
    row = fake_sb.table("swing_ideas").select("*").eq("id", seed_idea).execute().data[0]
    assert row["base_thesis"] == "first version"
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/python -m pytest tests/swing/test_thesis_endpoint.py -v
```

- [ ] **Step 3: Implement in `api/endpoints/swing.py`**

Add the route below existing Plan 2 ideas routes:

```python
# api/endpoints/swing.py  — APPEND
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from api.endpoints.swing_auth import require_swing_token, idempotent
from api.schemas.swing import ThesisWriteRequest, ThesisWriteResponse


@router.post("/ideas/{idea_id}/thesis", response_model=ThesisWriteResponse,
             dependencies=[Depends(require_swing_token)])
def write_thesis(
    idea_id: UUID,
    req: ThesisWriteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sb = _get_supabase()
    idea = sb.table("swing_ideas").select("id").eq("id", str(idea_id)).execute().data or []
    if not idea:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")

    def _do() -> dict:
        now = datetime.now(timezone.utc).isoformat()
        patch: dict = {}
        if req.layer == "base":
            patch = {
                "base_thesis": req.text,
                "base_thesis_at": now,
                "thesis_status": "ready",
            }
        else:  # deep
            patch = {
                "deep_thesis": req.text,
                "deep_thesis_at": now,
                "deep_thesis_sources": req.sources,
            }
        sb.table("swing_ideas").update(patch).eq("id", str(idea_id)).execute()
        # Also append a swing_events row so the timeline reflects thesis updates.
        sb.table("swing_events").insert({
            "idea_id": str(idea_id),
            "event_type": "thesis_updated",
            "occurred_at": now,
            "payload": {"layer": req.layer, "model": req.model},
            "summary": f"{req.layer} thesis updated",
        }).execute()
        return {"idea_id": str(idea_id), "layer": req.layer, "updated_at": now}

    return idempotent(sb, idempotency_key, f"/ideas/{idea_id}/thesis", _do)
```

- [ ] **Step 4: Run — pass**

```bash
.venv/bin/python -m pytest tests/swing/test_thesis_endpoint.py -v
```

Expected: 5 passing.

- [ ] **Step 5: Grep for anthropic imports**

```bash
grep -r "^import anthropic\|^from anthropic" api/ --include='*.py' | grep -v tests/
```

Expected: empty.

- [ ] **Step 6: Commit**

```bash
git add api/endpoints/swing.py tests/swing/test_thesis_endpoint.py
git commit -m "feat(swing): add POST /ideas/<id>/thesis for Mac-Claude writes

Bearer-auth'd. Writes base or deep thesis, appends thesis_updated event. Idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `POST /api/swing/ideas/<id>/events` (TDD)

**Files:**
- Modify: `api/endpoints/swing.py`
- Create: `tests/swing/test_events_endpoint.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_events_endpoint.py
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


def test_events_404_unknown_idea(client):
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
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/python -m pytest tests/swing/test_events_endpoint.py -v
```

- [ ] **Step 3: Implement**

Append to `api/endpoints/swing.py`:

```python
from api.schemas.swing import EventWriteRequest, EventWriteResponse


@router.post("/ideas/{idea_id}/events", response_model=EventWriteResponse,
             dependencies=[Depends(require_swing_token)])
def write_event(
    idea_id: UUID,
    req: EventWriteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sb = _get_supabase()
    if not sb.table("swing_ideas").select("id").eq("id", str(idea_id)).execute().data:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")

    def _do() -> dict:
        now = datetime.now(timezone.utc).isoformat()
        ret = sb.table("swing_events").insert({
            "idea_id": str(idea_id),
            "event_type": req.event_type,
            "occurred_at": now,
            "payload": req.payload,
            "summary": req.summary,
        }).execute()
        # FakeSupabaseClient returns .data as the inserted list; production Supabase returns rows with `id`.
        row = (ret.data or [{}])[0] if hasattr(ret, "data") else {}
        return {
            "event_id": row.get("id", 0),
            "idea_id": str(idea_id),
            "occurred_at": now,
        }

    return idempotent(sb, idempotency_key, f"/ideas/{idea_id}/events", _do)
```

- [ ] **Step 4: Run — pass**

Expected: 4 passing.

- [ ] **Step 5: Commit**

```bash
git add api/endpoints/swing.py tests/swing/test_events_endpoint.py
git commit -m "feat(swing): add POST /ideas/<id>/events for timeline writes

Bearer-auth'd, idempotent. Used by Mac-Claude skills to log notes and analysis events.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Ticker service + `GET /ticker/<T>/bars` + `GET /ticker/<T>/fundamentals` (TDD)

**Files:**
- Create: `api/endpoints/swing_ticker_service.py`
- Modify: `api/endpoints/swing.py`
- Create: `tests/swing/test_ticker_endpoints.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_ticker_endpoints.py
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from datetime import date

from api.main import app
from api.endpoints import swing as swing_endpoints
from api.endpoints import swing_ticker_service as svc


@pytest.fixture
def client():
    return TestClient(app)


def _fake_bars(days: int, tf: str = "daily") -> pd.DataFrame:
    dates = pd.date_range("2026-01-02", periods=days, freq="B")
    return pd.DataFrame({
        "date": dates, "open": 100.0, "high": 101.0, "low": 99.0,
        "close": 100.5, "volume": 1_000_000,
    })


def test_bars_returns_requested_lookback(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_bars", lambda t, tf, lookback: _fake_bars(lookback))
    r = client.get("/api/swing/ticker/NVDA/bars?tf=daily&lookback=30")
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"
    assert len(r.json()["bars"]) == 30


def test_bars_rejects_bad_tf(client):
    r = client.get("/api/swing/ticker/NVDA/bars?tf=1m&lookback=30")
    assert r.status_code == 422


def test_bars_rejects_unknown_ticker(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_bars", lambda *a, **k: pd.DataFrame())
    r = client.get("/api/swing/ticker/ZZZZZ/bars?tf=daily&lookback=30")
    assert r.status_code == 404


def test_fundamentals_returns_shape(client, monkeypatch):
    monkeypatch.setattr(svc, "fetch_fundamentals", lambda t: {
        "fundamentals": {"trailingPE": 30.0, "marketCap": 1e12},
        "next_earnings_date": date(2026, 5, 20),
        "beta": 1.6,
        "avg_daily_dollar_volume": 5e9,
    })
    r = client.get("/api/swing/ticker/NVDA/fundamentals")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["beta"] == 1.6
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/python -m pytest tests/swing/test_ticker_endpoints.py -v
```

- [ ] **Step 3: Implement `swing_ticker_service.py`**

```python
# api/endpoints/swing_ticker_service.py
"""Thin yfinance wrapper used by /api/swing/ticker/<T>/* endpoints.

Kept separate from swing.py so tests can monkey-patch these functions
without pulling yfinance into the import graph.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf


_TF_TO_YF: dict[str, tuple[str, str]] = {
    # (period_template, interval)  — period computed from lookback
    "daily":  ("d", "1d"),
    "weekly": ("d", "1wk"),
    "60m":    ("d", "60m"),
}


def fetch_bars(ticker: str, tf: str, lookback: int) -> pd.DataFrame:
    _, interval = _TF_TO_YF[tf]
    # Over-fetch a little to cover non-trading days.
    period_days = max(lookback * 2, 10)
    raw = yf.Ticker(ticker).history(period=f"{period_days}d", interval=interval, auto_adjust=False)
    if raw.empty:
        return raw
    df = raw.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
    df.columns = ["date", "open", "high", "low", "close", "volume"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.tail(lookback).reset_index(drop=True)


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    t = yf.Ticker(ticker)
    info: dict[str, Any] = getattr(t, "info", {}) or {}
    cal = getattr(t, "calendar", None)
    next_earn: date | None = None
    try:
        if cal is not None and "Earnings Date" in cal.index:   # yfinance >= 0.2
            next_earn = pd.to_datetime(cal.loc["Earnings Date"][0]).date()
    except Exception:
        next_earn = None
    adv = None
    try:
        hist = t.history(period="40d")
        if not hist.empty:
            adv = float((hist["Close"] * hist["Volume"]).tail(20).mean())
    except Exception:
        pass
    return {
        "fundamentals": info,
        "next_earnings_date": next_earn,
        "beta": info.get("beta"),
        "avg_daily_dollar_volume": adv,
    }
```

- [ ] **Step 4: Add routes to `api/endpoints/swing.py`**

```python
# api/endpoints/swing.py  — APPEND
from fastapi import Query
from api.endpoints import swing_ticker_service as svc
from api.schemas.swing import TickerBarsResponse, TickerBarEntry, TickerFundamentalsResponse


_TFS = {"daily", "weekly", "60m"}


@router.get("/ticker/{ticker}/bars", response_model=TickerBarsResponse)
def get_ticker_bars(
    ticker: str,
    tf: str = Query(..., pattern="^(daily|weekly|60m)$"),
    lookback: int = Query(90, ge=5, le=1000),
):
    df = svc.fetch_bars(ticker.upper(), tf, lookback)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No bars for {ticker}")
    return TickerBarsResponse(
        ticker=ticker.upper(),
        tf=tf,
        bars=[TickerBarEntry(**r) for r in df.to_dict(orient="records")],
    )


@router.get("/ticker/{ticker}/fundamentals", response_model=TickerFundamentalsResponse)
def get_ticker_fundamentals(ticker: str):
    data = svc.fetch_fundamentals(ticker.upper())
    return TickerFundamentalsResponse(ticker=ticker.upper(), **data)
```

- [ ] **Step 5: Run — pass**

Expected: 4 passing.

- [ ] **Step 6: Commit**

```bash
git add api/endpoints/swing_ticker_service.py api/endpoints/swing.py tests/swing/test_ticker_endpoints.py
git commit -m "feat(swing): add ticker bars + fundamentals read endpoints

Thin yfinance wrapper, used by Mac-Claude /swing-analyze and /swing-review skills.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `POST /api/swing/ticker/<T>/detect` (TDD)

**Files:**
- Modify: `api/endpoints/swing.py`
- Create: `tests/swing/test_ticker_detect_endpoint.py`

This reuses Plan 2's detector pipeline. Import the orchestrator function Plan 2 exposes (expected name: `run_all_detectors_for_ticker` in `api/indicators/swing/setups/__init__.py`). If Plan 2 named it differently, adjust the import and leave a comment with the actual name.

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_ticker_detect_endpoint.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.endpoints import swing as swing_endpoints


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SWING_API_TOKEN", "tk")
    return TestClient(app)


AUTH = {"Authorization": "Bearer tk"}


def test_detect_requires_auth(client):
    r = client.post("/api/swing/ticker/NVDA/detect", json={})
    assert r.status_code == 401


def test_detect_happy_path(client):
    fake_hits = [{"setup_kell": "wedge_pop", "cycle_stage": "wedge_pop", "raw_score": 7,
                  "entry_zone": [100.0, 101.0], "stop_price": 99.0, "first_target": 110.0}]
    fake_fund = {"fundamentals": {}, "next_earnings_date": None, "beta": 1.2, "avg_daily_dollar_volume": 2e9}
    with patch.object(swing_endpoints, "_run_detectors_for_ticker", return_value=fake_hits), \
         patch.object(swing_endpoints, "_ticker_health_snapshot",
                      return_value={"qqq_above_20ema": True, "cycle": "green"}):
        with patch("api.endpoints.swing_ticker_service.fetch_fundamentals", return_value=fake_fund):
            r = client.post("/api/swing/ticker/NVDA/detect", headers=AUTH, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["data_sufficient"] is True
    assert len(body["setups"]) == 1
    assert body["market_health"]["cycle"] == "green"


def test_detect_insufficient_data(client):
    with patch.object(swing_endpoints, "_run_detectors_for_ticker",
                      side_effect=swing_endpoints.InsufficientData("only 30 bars")):
        r = client.post("/api/swing/ticker/ZZZ/detect", headers=AUTH, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["data_sufficient"] is False
    assert body["setups"] == []
    assert "only 30 bars" in body["reason"]
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

Append to `api/endpoints/swing.py`:

```python
from api.schemas.swing import TickerDetectResponse


class InsufficientData(Exception):
    """Raised when a ticker has < 60 bars of history — not enough for Kell detectors."""


def _run_detectors_for_ticker(ticker: str) -> list[dict]:
    """Thin wrapper around Plan 2's detector pipeline.

    Plan 2 exposes a function that: fetches daily+weekly bars via yfinance,
    computes indicators, runs all 6 detectors, returns list[SetupHit].
    We import it lazily to keep the top of this module light.
    """
    # Adjust the import if Plan 2 used a different name:
    from api.indicators.swing.setups import run_all_detectors_for_ticker

    daily = svc.fetch_bars(ticker, "daily", lookback=250)
    if len(daily) < 60:
        raise InsufficientData(f"only {len(daily)} daily bars")
    hits = run_all_detectors_for_ticker(ticker, daily_bars=daily)
    # Serialize SetupHit → dict. Plan 2's SetupHit is a dataclass with `.asdict()` helper
    # or dataclasses.asdict works.
    import dataclasses
    return [dataclasses.asdict(h) if dataclasses.is_dataclass(h) else dict(h) for h in hits]


def _ticker_health_snapshot() -> dict:
    """Market health (QQQ vs 20-EMA). Plan 2 implements this; re-exported here."""
    from api.indicators.swing.market_health import compute_market_health
    return compute_market_health()


@router.post("/ticker/{ticker}/detect", response_model=TickerDetectResponse,
             dependencies=[Depends(require_swing_token)])
def detect_for_ticker(ticker: str):
    ticker = ticker.upper()
    try:
        setups = _run_detectors_for_ticker(ticker)
    except InsufficientData as e:
        fund = svc.fetch_fundamentals(ticker)
        return TickerDetectResponse(
            ticker=ticker, setups=[], fundamentals=fund.get("fundamentals") or {},
            market_health={}, data_sufficient=False, reason=str(e),
        )
    fund = svc.fetch_fundamentals(ticker)
    return TickerDetectResponse(
        ticker=ticker,
        setups=setups,
        fundamentals=fund.get("fundamentals") or {},
        market_health=_ticker_health_snapshot(),
        data_sufficient=True,
    )
```

- [ ] **Step 4: Run — pass**

Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add api/endpoints/swing.py tests/swing/test_ticker_detect_endpoint.py
git commit -m "feat(swing): add POST /ticker/<T>/detect for ad-hoc analysis

Runs Plan 2's detectors on any ticker; used by Mac-Claude /swing-analyze.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `.claude/skills/` — shared include + four slash commands

**Files:**
- Create: `.claude/skills/_swing-shared.md`
- Create: `.claude/skills/swing-analyze-pending.md`
- Create: `.claude/skills/swing-analyze.md`
- Create: `.claude/skills/swing-review.md`
- Create: `.claude/skills/swing-compare.md`

All four user-facing skills read the token and hit Railway. The shared file documents the conventions.

- [ ] **Step 1: Write `_swing-shared.md`**

```markdown
<!-- .claude/skills/_swing-shared.md -->
# Swing Skill — Shared Conventions

**Auth**: read the bearer token from `~/.config/trend-trading-mcp/swing-api.token`.
Send as `Authorization: Bearer <token>` on all POSTs. GETs are unauth'd.

**Base URL**: read from `RAILWAY_SWING_BASE` env (falls back to the deployed Railway domain — record in README). Example: `https://trend-trading-mcp.up.railway.app`.

**Idempotency**: for retry-safe writes, include `Idempotency-Key: <uuid>` with a stable UUID per logical operation.

**Model tag**: every thesis POST must include `model` matching the Claude model that generated the text. Source of truth: `$CLAUDE_MODEL` env set by Claude Code at invocation time; otherwise hard-code `claude-opus-4-7` (or whatever is current). Record in thesis metadata for later audit.

**Prerequisites to verify at each skill start** (spec §8 prereqs):
1. Token file exists + readable — fail fast with a clear error if missing.
2. `curl $BASE/healthz` returns 200 — if not, post a Slack message via the existing webhook and abort.
3. For `/swing-analyze-pending` specifically: Mac is awake and plugged in (battery check via `pmset -g batt`) — if on battery and < 50%, log a warning but proceed.

**Failure mode**: any HTTP non-2xx from Railway → print the response, Slack the error, exit with non-zero status. Do NOT retry silently. The next scheduled run will pick up the pending idea again.

**Never call the Anthropic API directly** — this is Claude Code on Max. Generation happens via the LLM already powering this session; we just write text to Railway via HTTP.
```

- [ ] **Step 2: Write `swing-analyze-pending.md` (scheduled 6:30am PT)**

```markdown
---
name: swing-analyze-pending
description: Generate base theses for all swing ideas with thesis_status='pending'. Scheduled 6:30am PT weekdays.
---

# /swing-analyze-pending

**Trigger**: `scheduled-tasks` MCP at 13:30 UTC (6:30am PT) weekdays, OR manual invocation.

**Budget**: ≤20 ideas per run. One paragraph each. Expect ≤10 Claude messages total.

**Procedure:**

1. Read `.claude/skills/_swing-shared.md` prerequisites; abort on any failure.

2. `curl -s "$BASE/api/swing/ideas?thesis_status=pending&limit=20"` (unauth GET). Parse JSON.

3. If `ideas` is empty: Slack `"No pending theses this morning."` and exit 0.

4. For each idea in the response (iterate, don't batch — keep failures isolated):
   a. `curl -s "$BASE/api/swing/ticker/$TICKER/fundamentals"` for extra color.
   b. Compose a **one-paragraph base thesis** (target 4–7 sentences, ≤400 words). Ground it in:
      - `setup_kell` / `cycle_stage` and what it means (reference `docs/kell/source-notes.md` terminology).
      - `detection_evidence` from the idea row (volume surge, RS, EMA positions).
      - `fundamentals` (rev growth YoY, margins, next earnings date).
      - `market_health` (QQQ cycle color).
      Do NOT speculate on news; this is a structural/fundamental read only.
   c. `curl -s -X POST "$BASE/api/swing/ideas/$IDEA_ID/thesis" \
         -H "Authorization: Bearer $TOKEN" \
         -H "Idempotency-Key: $(uuidgen)" \
         -H "Content-Type: application/json" \
         -d '{"layer":"base","text":"...","model":"claude-opus-4-7"}'`
   d. Check status; on non-2xx, log + continue to next idea (don't abort the batch).

5. Post a Slack summary: `"✅ Base theses written for N/M ideas"`.

**Output example for one thesis:**
> NVDA fires a Wedge Pop on declining volume after a three-week consolidation above the 10/20 EMAs. RS vs QQQ has turned positive over the last 10 sessions, and the reclaim bar printed 1.4× avg volume. Fundamentals remain the strongest in the cohort: +78% YoY Q revenue, gross margin holding above 74%, and guidance reiterated. Next earnings are 32 days out, giving a full trading window before event risk. With QQQ above its 20-EMA (green-light tape), this sets up as a primary pyramid candidate. Entry zone 102.00–103.50; stop under 99.20 (reclaim-bar low); first target at the prior swing high near 114.

**Never**: exceed ~400 words, invent news, recommend sizing beyond the auto-computed suggested_position_pct.
```

- [ ] **Step 3: Write `swing-analyze.md` (ad-hoc, any ticker)**

```markdown
---
name: swing-analyze
description: On-demand Kell+Saty setup analysis for any ticker. Usage `/swing-analyze <TICKER> [--save]`.
---

# /swing-analyze

**Trigger**: user types `/swing-analyze NVDA` (or `--save`) in chat.

**Procedure:**

1. Parse args: `TICKER` (required, uppercased), `--save` (optional).

2. `curl -s "$BASE/api/swing/ticker/$TICKER/bars?tf=daily&lookback=250"` — show a compact summary to the user (last 5 bars).

3. `curl -sf -X POST "$BASE/api/swing/ticker/$TICKER/detect" -H "Authorization: Bearer $TOKEN"` — get detector hits + fundamentals + market health.

4. If `data_sufficient=false`: tell user "Ticker X: insufficient data (reason)." and exit.

5. Render a thesis for the user in chat. Structure:
   - **Setup**: which Kell setup(s) fired (can be zero — if zero, say "no active swing setup, but here is the structural read").
   - **Cycle stage read**.
   - **Levels**: entry zone / stop / first target (from detectors, or discretionary if none).
   - **Fundamentals snapshot**: rev YoY, earnings date, beta.
   - **Market context**: QQQ cycle.
   - **Verdict**: pass / watch / enter.

6. If `--save` OR user confirms "save as watching":
   - Pick the highest-confluence setup (or if none, prompt for cycle_stage).
   - Currently Railway has no "create idea" endpoint for ad-hoc tickers (Plan 2 populates via the cron only). **For Plan 3, defer idea creation to Plan 4's upcoming POST /api/swing/ideas endpoint.** When `--save` is used and no endpoint exists yet, tell the user: "Save-as-watching needs Plan 4's idea-create endpoint — will persist the analysis as a chat note only."

**Note**: this skill does not call any Railway write endpoint in the MVP. It's read-only. Thesis lives in the chat transcript.

**Never**: create a `swing_ideas` row via direct SQL. Wait for Plan 4's ideas POST route.
```

- [ ] **Step 4: Write `swing-review.md`**

```markdown
---
name: swing-review
description: Pull an existing swing idea's detail + timeline + latest thesis. Usage `/swing-review <TICKER>`.
---

# /swing-review

**Procedure:**

1. Parse `TICKER`.
2. `curl -s "$BASE/api/swing/ideas?ticker=$TICKER&limit=5"` (Plan 2 ideas list filter). Show the user a numbered list (most recent first).
3. Let user pick one (or auto-pick #1 if only one active idea).
4. `curl -s "$BASE/api/swing/ideas/$IDEA_ID"` (Plan 2 single-idea endpoint).
5. Render a summary:
   - Header: ticker, status, cycle_stage, confluence, detection_age.
   - Base thesis (truncate to 600 chars, offer "Show full").
   - Deep thesis (if present).
   - Latest 5 events (from `ideas/<id>` response — Plan 2 includes them).
   - Risk flags.
6. Offer follow-up actions: "Add note" (POST /events), "View in browser" (print URL to `/swing-ideas/<id>`).

**Never**: silently regenerate the thesis. Use `/swing-analyze` for fresh analysis.
```

- [ ] **Step 5: Write `swing-compare.md`**

```markdown
---
name: swing-compare
description: Side-by-side setup comparison. Usage `/swing-compare T1,T2,...` (up to 4 tickers).
---

# /swing-compare

**Procedure:**

1. Parse comma-separated tickers (max 4).
2. For each: `curl -sf -X POST "$BASE/api/swing/ticker/$T/detect" -H "Authorization: Bearer $TOKEN"` in parallel.
3. Also fetch existing idea rows if they exist: `curl -s "$BASE/api/swing/ideas?ticker=$T"`.
4. Render a comparison table:

   | Ticker | Setup fired | Cycle stage | Entry | Stop | Rev YoY | Earnings | Verdict |
   |--------|-------------|-------------|-------|------|---------|----------|---------|
   | NVDA   | Wedge Pop   | wedge_pop   | 102–103.5 | 99.20 | +78% | 32d | Strong |
   | AMD    | none        | —           | —     | —    | +22% | 18d | Pass |

5. Recommend the strongest setup, or "none of these qualify — wait."

**Never**: pick favorites based on hunches. Use `confluence_score` + `data_sufficient` as tiebreakers.
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/_swing-shared.md .claude/skills/swing-analyze-pending.md .claude/skills/swing-analyze.md .claude/skills/swing-review.md .claude/skills/swing-compare.md
git commit -m "feat(swing): add Mac-Claude slash commands for thesis + ticker analysis

4 skills under .claude/skills/ + shared conventions file. Base thesis flow is scheduled; others are ad-hoc. No Anthropic SDK usage — runs on Max subscription via Claude Code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: `scheduled-tasks` MCP registration + bootstrap script

**Files:**
- Create: `scripts/swing/bootstrap-mac.sh`

- [ ] **Step 1: Write bootstrap script**

```bash
#!/usr/bin/env bash
# scripts/swing/bootstrap-mac.sh
# One-shot: wires the user's Mac into the swing system.
# Idempotent — safe to re-run.
set -euo pipefail

TOKEN_DIR="$HOME/.config/trend-trading-mcp"
TOKEN_FILE="$TOKEN_DIR/swing-api.token"

if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "✗ Token file missing at $TOKEN_FILE"
    echo "  Generate on Railway: railway variables | grep SWING_API_TOKEN"
    echo "  Then: mkdir -p $TOKEN_DIR && printf '%s' <token> > $TOKEN_FILE && chmod 600 $TOKEN_FILE"
    exit 1
fi
test "$(stat -f '%A' "$TOKEN_FILE")" = "600" || {
    echo "✗ Token file must be mode 600. Fix: chmod 600 $TOKEN_FILE"
    exit 1
}
echo "✓ Token file OK."

BASE="${RAILWAY_SWING_BASE:-https://trend-trading-mcp.up.railway.app}"
if ! curl -sf "$BASE/healthz" >/dev/null; then
    echo "✗ $BASE/healthz did not return 2xx. Check Railway deploy."
    exit 1
fi
echo "✓ Railway reachable at $BASE."

# Register the scheduled task via scheduled-tasks MCP.
# The MCP CLI invocation varies — typical form below; adjust after Task 1 prereqs verify behavior.
echo "To register the daily task, run this once in a Claude Code session:"
cat <<'EOF'

  Use scheduled-tasks MCP to create a task:
    name: "swing-analyze-pending"
    cron: "30 13 * * 1-5"        # 13:30 UTC = 6:30am PT (standard time); PT-DST shifts to 13:30 = 6:30 PDT
    prompt: "/swing-analyze-pending"

  Via tool call:
    mcp__scheduled-tasks__create_scheduled_task(
      name="swing-analyze-pending",
      cron="30 13 * * 1-5",
      prompt="/swing-analyze-pending"
    )

EOF

echo "✓ Bootstrap complete. Verify with: mcp__scheduled-tasks__list_scheduled_tasks"
```

- [ ] **Step 2: Make executable + dry-run**

```bash
chmod +x scripts/swing/bootstrap-mac.sh
./scripts/swing/bootstrap-mac.sh
```

Expected: "Token file OK", "Railway reachable", instructions for MCP registration.

- [ ] **Step 3: Register the scheduled task**

In a Claude Code session, invoke `scheduled-tasks` MCP:
```
mcp__scheduled-tasks__create_scheduled_task
  name: "swing-analyze-pending"
  cron: "30 13 * * 1-5"
  prompt: "/swing-analyze-pending"
```

Verify:
```
mcp__scheduled-tasks__list_scheduled_tasks
```

- [ ] **Step 4: Smoke test**

Trigger manually (same Claude Code session):
```
/swing-analyze-pending
```

Expected (assuming Plan 2's pipeline has run and there are pending ideas): one Slack message + N theses posted. If no pending ideas: "No pending theses this morning." + exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/swing/bootstrap-mac.sh
git commit -m "feat(swing): add Mac bootstrap script for Plan 3 scheduled task

One-shot verification of token + Railway reachability + scheduled-tasks registration instructions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Frontend types + single-idea hook

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/app/api/swing/ideas/[id]/route.ts`
- Create: `frontend/src/hooks/use-swing-idea-detail.ts`

- [ ] **Step 1: Append types**

```typescript
// frontend/src/lib/types.ts — APPEND

export type SwingThesisLayer = "base" | "deep"

export interface SwingThesis {
  text: string
  layer: SwingThesisLayer
  model: string
  updatedAt: string
  sources?: string[]
}

export interface SwingEvent {
  id: number
  ideaId: string
  eventType: string
  occurredAt: string
  payload?: Record<string, unknown> | null
  summary?: string | null
}

export interface SwingIdeaDetail {
  id: string
  ticker: string
  direction: "long" | "short"
  detectedAt: string
  cycleStage: string
  setupKell: string
  setupSaty: string | null
  confluenceScore: number
  entryZoneLow: number | null
  entryZoneHigh: number | null
  stopPrice: number
  firstTarget: number | null
  secondTarget: number | null
  status: string
  thesisStatus: "pending" | "ready"
  baseThesis: string | null
  baseThesisAt: string | null
  deepThesis: string | null
  deepThesisAt: string | null
  deepThesisSources: string[] | null
  nextEarningsDate: string | null
  riskFlags: Record<string, unknown>
  marketHealth: Record<string, unknown> | null
  events: SwingEvent[]        // Plan 2's /ideas/<id> response embeds events
}
```

- [ ] **Step 2: Write GET proxy for single idea**

```typescript
// frontend/src/app/api/swing/ideas/[id]/route.ts
import { NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const response = await railwayFetch(`/api/swing/ideas/${encodeURIComponent(id)}`)
    const data = await response.json()
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to fetch idea" },
      { status },
    )
  }
}
```

- [ ] **Step 3: Write hook**

```typescript
// frontend/src/hooks/use-swing-idea-detail.ts
import useSWR from "swr"
import type { SwingIdeaDetail } from "@/lib/types"

const fetcher = async (url: string): Promise<SwingIdeaDetail> => {
  const r = await fetch(url)
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error((body as { error?: string }).error || `Failed: ${r.status}`)
  }
  return r.json()
}

export function useSwingIdeaDetail(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SwingIdeaDetail>(
    id ? `/api/swing/ideas/${id}` : null,
    fetcher,
    { revalidateOnFocus: false, refreshInterval: 0 },
  )
  return { idea: data, error, isLoading, refresh: mutate }
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npm run typecheck
```

Expected: 0 errors. (If Plan 2 hasn't landed `GET /api/swing/ideas/<id>` yet, the proxy still compiles — it'll return whatever Plan 2 ships.)

- [ ] **Step 5: Commit**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
git add frontend/src/lib/types.ts frontend/src/app/api/swing/ideas/ frontend/src/hooks/use-swing-idea-detail.ts
git commit -m "feat(swing): add frontend types, single-idea proxy, and SWR hook

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: `/swing-ideas/[id]` detail page components

**Files:**
- Create: `frontend/src/components/swing/thesis-panel.tsx`
- Create: `frontend/src/components/swing/idea-header.tsx`
- Create: `frontend/src/components/swing/idea-timeline.tsx`
- Create: `frontend/src/app/swing-ideas/[id]/page.tsx`

- [ ] **Step 1: `thesis-panel.tsx`**

```tsx
// frontend/src/components/swing/thesis-panel.tsx
"use client"
import type { SwingIdeaDetail } from "@/lib/types"

export function ThesisPanel({ idea }: { idea: SwingIdeaDetail }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Thesis
      </h2>

      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium">Base</span>
            {idea.thesisStatus === "pending" && (
              <span className="text-xs rounded bg-amber-500/20 text-amber-700 dark:text-amber-300 px-1.5 py-0.5">
                pending
              </span>
            )}
            {idea.baseThesisAt && (
              <span className="text-xs text-muted-foreground">
                {new Date(idea.baseThesisAt).toLocaleString()}
              </span>
            )}
          </div>
          {idea.baseThesis ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{idea.baseThesis}</p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              Base thesis not yet generated. Runs at 6:30am PT on weekdays.
            </p>
          )}
        </div>

        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium">Deep</span>
            {idea.deepThesisAt && (
              <span className="text-xs text-muted-foreground">
                {new Date(idea.deepThesisAt).toLocaleString()}
              </span>
            )}
          </div>
          {idea.deepThesis ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{idea.deepThesis}</p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              Deep analysis (Deepvue + charts) runs at 2:30pm PT. (Plan 4.)
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: `idea-header.tsx`**

```tsx
// frontend/src/components/swing/idea-header.tsx
"use client"
import type { SwingIdeaDetail } from "@/lib/types"

export function IdeaHeader({ idea }: { idea: SwingIdeaDetail }) {
  return (
    <header className="sticky top-0 z-10 bg-background/90 backdrop-blur border-b border-border py-3">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold">{idea.ticker}</h1>
        <span className="text-sm rounded bg-secondary px-2 py-0.5">{idea.status}</span>
        <span className="text-sm text-muted-foreground">· {idea.cycleStage}</span>
        <span className="text-sm text-muted-foreground">
          · confluence {idea.confluenceScore}/10
        </span>
        <span className="text-xs text-muted-foreground ml-auto">
          detected {new Date(idea.detectedAt).toLocaleDateString()}
        </span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground flex gap-4">
        <span>stop ${idea.stopPrice.toFixed(2)}</span>
        {idea.firstTarget && <span>target ${idea.firstTarget.toFixed(2)}</span>}
        {idea.nextEarningsDate && <span>earnings {idea.nextEarningsDate}</span>}
      </div>
    </header>
  )
}
```

- [ ] **Step 3: `idea-timeline.tsx` (stub for Plan 4)**

```tsx
// frontend/src/components/swing/idea-timeline.tsx
"use client"
import type { SwingEvent } from "@/lib/types"

export function IdeaTimeline({ events }: { events: SwingEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Timeline
        </h2>
        <p className="text-sm text-muted-foreground italic">
          No events yet. Daily snapshots, stage transitions, and user notes will appear here.
        </p>
      </section>
    )
  }
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Timeline
      </h2>
      <ol className="space-y-2">
        {events.map((e) => (
          <li key={e.id} className="flex gap-3 text-sm">
            <span className="text-xs text-muted-foreground w-32 shrink-0">
              {new Date(e.occurredAt).toLocaleString()}
            </span>
            <span className="text-xs rounded bg-secondary px-1.5 py-0.5 h-fit">{e.eventType}</span>
            <span className="text-sm">{e.summary || ""}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
```

- [ ] **Step 4: `page.tsx` for `/swing-ideas/[id]`**

```tsx
// frontend/src/app/swing-ideas/[id]/page.tsx
"use client"
import { use } from "react"
import { useSwingIdeaDetail } from "@/hooks/use-swing-idea-detail"
import { IdeaHeader } from "@/components/swing/idea-header"
import { ThesisPanel } from "@/components/swing/thesis-panel"
import { IdeaTimeline } from "@/components/swing/idea-timeline"

export default function SwingIdeaDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { idea, error, isLoading } = useSwingIdeaDetail(id)

  if (isLoading) return <div className="p-6">Loading…</div>
  if (error) return <div className="p-6 text-destructive">Error: {error.message}</div>
  if (!idea) return <div className="p-6">Not found.</div>

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <IdeaHeader idea={idea} />
      <ThesisPanel idea={idea} />
      <IdeaTimeline events={idea.events ?? []} />
      {/* Plan 4 adds: ChartsGallery, FundamentalsPanel, ModelBookPromote */}
    </div>
  )
}
```

- [ ] **Step 5: Smoke test locally**

```bash
cd frontend && npm run dev
# Open http://localhost:3000/swing-ideas/<some-existing-idea-uuid>
```

Expected: header renders, thesis shows "pending" state if base_thesis is null, timeline shows event list.

- [ ] **Step 6: Commit**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
git add frontend/src/components/swing/thesis-panel.tsx frontend/src/components/swing/idea-header.tsx frontend/src/components/swing/idea-timeline.tsx frontend/src/app/swing-ideas/[id]/
git commit -m "feat(swing): add /swing-ideas/[id] detail page with thesis panel

Sticky header, thesis panel (base+deep), timeline stub. Plan 4 will extend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Active-list row expansion — show base thesis preview

**Files:**
- Modify: `frontend/src/components/swing/active-list.tsx` (Plan 2 creates this)

- [ ] **Step 1: Locate Plan 2's `active-list.tsx`**

```bash
ls frontend/src/components/swing/active-list.tsx && head -40 frontend/src/components/swing/active-list.tsx
```

If it doesn't exist yet, Plan 2 hasn't shipped. **Do not** create it from scratch — skip this task and flag it as blocked in the plan-execution log. This task depends strictly on Plan 2.

- [ ] **Step 2: Add a thesis preview in the expanded-row area**

Plan 2's `active-list.tsx` likely has an `ExpandedRow` or similar subcomponent. Add a block like:

```tsx
{idea.baseThesis ? (
  <p className="text-sm mt-2 line-clamp-3 text-muted-foreground">
    {idea.baseThesis}
  </p>
) : (
  <p className="text-xs mt-2 text-amber-600 italic">
    Base thesis pending (runs 6:30am PT)
  </p>
)}
<Link
  href={`/swing-ideas/${idea.id}`}
  className="text-xs text-primary hover:underline mt-1 inline-block"
>
  View full →
</Link>
```

Import `Link` from `next/link` at the top of the file if not already.

- [ ] **Step 3: Verify type compatibility**

The Plan 2 `SwingIdea` type may not yet include `baseThesis`. If so, Plan 2 should already include it (the spec §5.2 lists it); if missing, add optionally-typed access `(idea as SwingIdeaDetail).baseThesis ?? null`.

- [ ] **Step 4: Typecheck + visual smoke test**

```bash
cd frontend && npm run typecheck && npm run dev
```

- [ ] **Step 5: Commit**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
git add frontend/src/components/swing/active-list.tsx
git commit -m "feat(swing): show base thesis preview in Active/Watching expanded row

Pending state rendered when thesis not yet generated. Links to /swing-ideas/[id].

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: End-to-end smoke test

**Files:** none (manual verification)

- [ ] **Step 1: Run full backend test suite**

```bash
.venv/bin/python -m pytest tests/swing/ -v
```

Expected: all Plan 3 tests pass + Plan 1/2 tests still pass. Record test count.

- [ ] **Step 2: Final anthropic-import grep**

```bash
grep -r "^import anthropic\|^from anthropic" api/ --include='*.py' | grep -v tests/
grep -r "anthropic-sdk\|@anthropic-ai/sdk" api/ --include='*.py'
```

Expected: both empty. (This satisfies spec success criterion 9a.)

- [ ] **Step 3: Railway deploy + live endpoint sanity**

```bash
# Deploy if not already:
git push origin <plan-3-branch>
# Wait for Railway build.
# Then:
TOKEN=$(cat ~/.config/trend-trading-mcp/swing-api.token)
BASE="https://trend-trading-mcp.up.railway.app"

# Unauth GET still works:
curl -sf "$BASE/api/swing/ticker/NVDA/bars?tf=daily&lookback=30" | head -c 200

# Auth'd POST without token fails:
curl -s -X POST "$BASE/api/swing/ideas/00000000-0000-0000-0000-000000000000/events" \
  -H "Content-Type: application/json" -d '{"event_type":"user_note","summary":"x"}'
# Expected: 401

# With token + unknown idea:
curl -s -X POST "$BASE/api/swing/ideas/00000000-0000-0000-0000-000000000000/events" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"event_type":"user_note","summary":"x"}'
# Expected: 404
```

- [ ] **Step 4: Run `/swing-analyze NVDA` manually in Claude Code**

Expected: detector output, fundamentals, a thesis rendered to chat. No errors.

- [ ] **Step 5: Let the 6:30am PT cron fire tomorrow, then review**

Check Slack for the digest message. Check `/swing-ideas` Active tab: pending ideas should have become `thesis_status='ready'` with a preview visible.

- [ ] **Step 6: No commit** (sanity only).

---

## Definition of Done

- [ ] `swing_idempotency_keys` Supabase table exists (verified via `information_schema`).
- [ ] `SWING_API_TOKEN` set on Railway; readable token file at `~/.config/trend-trading-mcp/swing-api.token` with mode 600.
- [ ] All 5 new endpoints live: `POST /ideas/<id>/thesis`, `POST /ideas/<id>/events`, `POST /ticker/<T>/detect`, `GET /ticker/<T>/bars`, `GET /ticker/<T>/fundamentals`.
- [ ] Write endpoints return 401 without valid bearer; reads remain open.
- [ ] Idempotency key dedupes repeat POSTs within 24h (verified end-to-end with test).
- [ ] `.claude/skills/swing-analyze-pending.md` + 3 ad-hoc skills checked into repo.
- [ ] `scheduled-tasks` MCP registered for `/swing-analyze-pending` at 13:30 UTC weekdays.
- [ ] `/swing-ideas/[id]` page renders header + thesis panel + timeline stub for any existing idea.
- [ ] Active/Watching expanded row previews base thesis (text or "pending" state).
- [ ] `grep -r "anthropic" api/ --include='*.py' | grep -v tests/` returns empty.
- [ ] All `tests/swing/*` pass.
- [ ] One working 6:30am PT cron cycle observed: pending → ready transition, Slack digest posted.

---

## Out of Scope (deferred to Plan 4)

Explicitly **not** in Plan 3:

- **Deep analysis via Claude-in-Chrome on Deepvue** (`/swing-deep-analyze` skill, 2:30pm PT cron, chart screenshots, vision analysis). Plan 4 owns the browser-automation layer.
- **Exhaustion Extension detector** (runs in [C] post-market cron — Plan 2 or Plan 4, per Plan 2's split).
- **Weekly synthesis** (`/swing-weekly-synth` Sunday 5pm PT). Plan 4.
- **Model book** UI, promotion flow, `/swing-model-book-add` skill. Plan 4.
- **Chart upload endpoint** (`POST /ideas/<id>/charts` multipart). Plan 4 (needs Vercel Blob wiring).
- **Post-trade retrospective** auto-drafts on idea exit. Plan 4.
- **Theme clustering, narrative scoring, pre-earnings guidance** (spec §8 "Beyond mechanical detection"). Plan 4.
- **Create-idea-from-ad-hoc** (`POST /api/swing/ideas`) — spec §8 `/swing-analyze --save` depends on this. Plan 4 adds the endpoint; Plan 3's `/swing-analyze` is read/chat-only.
- **Chart gallery + annotated overlays** on `/swing-ideas/[id]`. Plan 4.
- **Snapshots write endpoint** (`POST /ideas/<id>/snapshots`). Plan 4 pairs this with the post-market Mac job.

---

## Open Questions to Resolve During Execution

1. **`scheduled-tasks` MCP closed-lid behavior.** Verify in Task 1. If it fails when lid is closed, fallback is `launchd` + `caffeinate -s`. Document findings in this file's Open Questions section and link the plan-execution log.

2. **Plan 2's detector orchestrator function name.** Task 9 assumes `run_all_detectors_for_ticker` in `api/indicators/swing/setups/__init__.py`. If Plan 2 used a different name (e.g. `run_detectors` or `detect_all`), update the import in `_run_detectors_for_ticker` — keep the rest of the endpoint intact.

3. **Plan 2's `GET /api/swing/ideas/<id>` response shape.** Task 12's `SwingIdeaDetail` type assumes Plan 2 embeds an `events` array. If Plan 2 returns events separately (e.g. at `/ideas/<id>/events`), split `use-swing-idea-detail.ts` into two SWR calls and compose the result.

4. **Plan 2's `SwingIdea` row type in `active-list.tsx`.** Task 14 assumes `baseThesis` is present. If Plan 2 omitted it, either PR it in or use a cast.

5. **`yf.Ticker.calendar` shape drift.** Task 8's `fetch_fundamentals` uses the yfinance `.calendar` DataFrame. If yfinance rev-bumped during execution and the shape changed, patch the try/except to handle both.

6. **Rate-limit budget on Max.** Spec §8 prereq 4. Measure after week 1: if > 30 messages / 5hr window, reduce `/swing-analyze-pending` batch size from 20 → 10.

7. **Claude model tag in thesis POSTs.** `.claude/skills/_swing-shared.md` says "hard-code `claude-opus-4-7`." Once Claude Code exposes `$CLAUDE_MODEL` reliably, switch the skills to read it. Not worth blocking Plan 3 on.

8. **DST transitions in cron.** `"30 13 * * 1-5"` means 13:30 UTC year-round → 6:30 PT (standard) or 5:30 PDT. If the user wants lock-to-local, schedule via a different trigger (spec §14 has this listed as an open question). MVP ships UTC.

---
