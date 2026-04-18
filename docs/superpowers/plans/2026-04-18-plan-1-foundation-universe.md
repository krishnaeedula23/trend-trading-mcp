# Plan 1 — Foundation: DB Schema + Universe Management

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create all 7 swing-trading tables and deliver a working `/swing-ideas` page whose **Universe tab** lets the user upload Deepvue CSVs, add/remove tickers manually, view universe history, and have a backend-generated fallback ready for the pipeline.

**Architecture:** One Alembic migration provisions all 7 tables upfront (subsequent plans consume the schema without migration work). Universe management is the first end-to-end slice: Supabase-backed REST endpoints, Next.js proxy routes, SWR hooks, and a tabbed `/swing-ideas` page with only the Universe tab live (Active/Watching/Exited/Model Book/Weekly show "Coming Soon" placeholders until later plans fill them in). Backend universe generator is a 4-stage filter pipeline (price+liquidity → trend+base → fundamentals → RS) running on a de-duped Russell 3000 ∪ Nasdaq Composite base list.

**Tech Stack:** Python 3.12, FastAPI, Alembic, Supabase Python client, yfinance, pandas, pytest. Next.js 16 (App Router), React 19, Tailwind 4, shadcn/ui, SWR pattern via custom hooks, Sonner toasts.

**Reference:** Spec at [docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md](../specs/2026-04-18-kell-saty-swing-system-design.md). Kell source notes at [docs/kell/source-notes.md](../../kell/source-notes.md).

---

## File Structure (created/modified by this plan)

**Backend — new:**
- `alembic/versions/016_add_swing_tables.py` — migration for all 7 swing tables
- `api/indicators/swing/__init__.py` — swing module marker
- `api/indicators/swing/universe/__init__.py`
- `api/indicators/swing/universe/base_tickers.json` — Russell 3000 ∪ Nasdaq Composite seed list
- `api/indicators/swing/universe/filters.py` — 4-stage filter functions
- `api/indicators/swing/universe/generator.py` — orchestrates filter stages
- `api/indicators/swing/universe/resolver.py` — Deepvue → backend fallback logic
- `api/schemas/swing.py` — Pydantic request/response models for /api/swing/*
- `api/endpoints/swing.py` — all /api/swing/* routes (universe endpoints in this plan; others stubbed)

**Backend — tests:**
- `tests/swing/__init__.py`
- `tests/swing/test_universe_filters.py`
- `tests/swing/test_universe_generator.py`
- `tests/swing/test_universe_resolver.py`
- `tests/swing/test_universe_endpoints.py`
- `tests/fixtures/swing_fixtures.py`

**Frontend — new:**
- `frontend/src/lib/swing-types.ts` — TS types for swing data
- `frontend/src/app/api/swing/universe/route.ts` — GET active universe, POST add ticker
- `frontend/src/app/api/swing/universe/upload/route.ts` — multipart CSV upload proxy
- `frontend/src/app/api/swing/universe/[ticker]/route.ts` — DELETE soft-remove ticker
- `frontend/src/app/api/swing/universe/history/route.ts` — GET upload history
- `frontend/src/hooks/use-swing-universe.ts` — SWR hook
- `frontend/src/app/swing-ideas/page.tsx` — tabbed shell
- `frontend/src/components/swing/universe-manager.tsx` — Universe tab body
- `frontend/src/components/swing/universe-upload-modal.tsx` — CSV upload dialog
- `frontend/src/components/swing/universe-history-panel.tsx` — history view

**Frontend — modified:**
- `frontend/src/components/layout/sidebar.tsx` — add Swing Ideas nav item
- `frontend/src/lib/types.ts` — OR add swing types here instead of new file if that's the existing convention (decide in Task 11)

---

## Task 1: Module scaffolding + base tickers JSON

**Files:**
- Create: `api/indicators/swing/__init__.py`
- Create: `api/indicators/swing/universe/__init__.py`
- Create: `api/indicators/swing/universe/base_tickers.json`

- [ ] **Step 1: Create empty module markers**

```bash
mkdir -p api/indicators/swing/universe
touch api/indicators/swing/__init__.py
touch api/indicators/swing/universe/__init__.py
```

- [ ] **Step 2: Seed base tickers JSON**

Fetch a deduped list of Russell 3000 + Nasdaq Composite tickers. For MVP we can use a static list sourced from iShares/Invesco. Manually curate or use a script to pull from public sources.

For now, create a minimal stub with a representative sample (~200 tickers) that covers sectors the user cares about. Full list can be expanded once verified.

Write to `api/indicators/swing/universe/base_tickers.json`:

```json
{
  "version": "1.0",
  "updated": "2026-04-18",
  "sources": ["Russell 3000", "Nasdaq Composite"],
  "tickers": [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "CRWD", "SMCI",
    "PLTR", "NET", "DDOG", "SNOW", "MDB", "ZS", "OKTA", "PANW", "FTNT", "S",
    "LLY", "UNH", "ABBV", "MRK", "TMO", "NVO", "VRTX", "ISRG", "DHR", "GILD",
    "JPM", "V", "MA", "BAC", "WFC", "C", "GS", "MS", "AXP", "SCHW",
    "COST", "WMT", "HD", "LOW", "TGT", "NKE", "SBUX", "MCD", "DIS", "NFLX",
    "XOM", "CVX", "SLB", "EOG", "OXY", "PSX", "VLO", "MRO", "COP", "PXD",
    "AMD", "INTC", "QCOM", "MU", "AMAT", "LRCX", "KLAC", "ARM", "MRVL", "ON",
    "TSM", "ASML", "BABA", "JD", "PDD", "MELI", "SHOP", "SE", "CRWV", "APP",
    "UBER", "LYFT", "DASH", "ABNB", "BKNG", "RBLX", "DKNG", "PINS", "SNAP", "RDDT",
    "CAT", "DE", "GE", "BA", "LMT", "RTX", "NOC", "HON", "MMM", "EMR",
    "PYPL", "SQ", "COIN", "HOOD", "MSTR", "AFRM", "SOFI", "UPST", "LMND",
    "ENPH", "FSLR", "SEDG", "RUN", "BE", "PLUG", "NEE", "DUK", "SO", "AEP",
    "NBIS", "IOT", "SFM", "SG", "SBLK", "ALAB", "CELH", "HIMS", "ASTS", "RKLB",
    "JOBY", "ACHR", "BLDE", "CLSK", "MARA", "RIOT", "CIFR", "BITF", "HUT", "WULF",
    "DUOL", "KC", "GRAB", "CORZ", "TEM", "APLD", "SMTC", "CRDO"
  ]
}
```

Expand to ~3500 tickers during a follow-up maintenance task before this plan ships. For Plan 1's verification, ~200 is sufficient.

- [ ] **Step 3: Verify JSON is loadable**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
venv/bin/python -c "import json; d = json.load(open('api/indicators/swing/universe/base_tickers.json')); print(f'Loaded {len(d[\"tickers\"])} tickers')"
```

Expected: `Loaded ~200 tickers` (or whatever count).

- [ ] **Step 4: Commit**

```bash
git add api/indicators/swing/
git commit -m "feat(swing): scaffold swing module with base tickers JSON"
```

---

## Task 2: Alembic migration for all 7 swing tables

**Files:**
- Create: `alembic/versions/016_add_swing_tables.py`

- [ ] **Step 1: Identify and (if needed) consolidate current head revision(s)**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
venv/bin/alembic heads
```

The repo has accumulated merge revisions (`08e3945a0c93_merge_heads`, `9374a5c9b679_merge_heads_for_testing`, `abf9b9afb134_merge_multiple_heads`, etc.), so `alembic heads` may print **multiple heads**.

**If multiple heads appear:**

```bash
venv/bin/alembic merge -m "merge heads before swing tables" <head1> <head2> ...
venv/bin/alembic heads   # verify single head now
```

Record the single head as `<CURRENT_HEAD>` for the swing migration's `down_revision`. If merge revision was needed, commit it separately before Task 2 Step 2:

```bash
git add alembic/versions/<new_merge_revision>.py
git commit -m "chore(alembic): merge heads before swing migration"
```

- [ ] **Step 1b: Verify Postgres version + pgcrypto extension**

The swing schema uses `num_nonnulls()` (Postgres 15+) and `gen_random_uuid()` (requires `pgcrypto` extension or Postgres 13+ built-in `gen_random_uuid`).

```bash
venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT version()')
print(cur.fetchone()[0])
cur.execute(\"SELECT extname FROM pg_extension WHERE extname='pgcrypto'\")
print('pgcrypto:', 'yes' if cur.fetchone() else 'NOT INSTALLED')
"
```

Expected: Postgres 15+ AND `pgcrypto: yes`. If pgcrypto is missing, add `CREATE EXTENSION IF NOT EXISTS pgcrypto;` as the first line of the migration's `upgrade()`. If Postgres < 15, replace the `num_nonnulls` CHECK constraint with explicit `(idea_id IS NOT NULL)::int + (event_id IS NOT NULL)::int + (model_book_id IS NOT NULL)::int = 1`.

- [ ] **Step 2: Write the migration file**

Create `alembic/versions/016_add_swing_tables.py` with full DDL for all 7 tables from the spec. Use `down_revision = "<CURRENT_HEAD>"` from step 1.

```python
"""Add swing trading tables

Revision ID: 016_add_swing_tables
Revises: <CURRENT_HEAD>
Create Date: 2026-04-18 12:00:00.000000

Creates the schema for the Kell+Saty unified swing trading system:
- swing_universe: active tickers (Deepvue CSV + backend-generated)
- swing_ideas: detected setups with cycle-stage state machine
- swing_idea_stage_transitions: Kell cycle stage history per idea
- swing_idea_snapshots: daily/weekly rollups per idea
- swing_events: timeline of everything that happens to an idea
- swing_charts: chart images (Vercel Blob refs) attached to ideas/events/model-book
- swing_model_book: curated exemplary setups for pattern recognition
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "016_add_swing_tables"
down_revision = "<CURRENT_HEAD>"  # replace with actual head from step 1
branch_labels = None
depends_on = None


def upgrade() -> None:
    # swing_universe
    op.create_table(
        "swing_universe",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extras", postgresql.JSONB, nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX swing_universe_active_ticker_uniq "
        "ON swing_universe (ticker) WHERE removed_at IS NULL"
    )
    op.create_index("ix_swing_universe_batch_id", "swing_universe", ["batch_id"])

    # swing_ideas
    op.create_table(
        "swing_ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("direction", sa.Text, nullable=False, server_default="long"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cycle_stage", sa.Text, nullable=False),
        sa.Column("setup_kell", sa.Text, nullable=False),
        sa.Column("setup_saty", sa.Text, nullable=True),
        sa.Column("confluence_score", sa.Integer, nullable=False),
        sa.Column("entry_zone_low", sa.Numeric, nullable=True),
        sa.Column("entry_zone_high", sa.Numeric, nullable=True),
        sa.Column("stop_price", sa.Numeric, nullable=False),
        sa.Column("first_target", sa.Numeric, nullable=True),
        sa.Column("second_target", sa.Numeric, nullable=True),
        sa.Column("suggested_position_pct", sa.Numeric, nullable=True),
        sa.Column("suggested_risk_bips", sa.Integer, nullable=True),
        sa.Column("fundamentals", postgresql.JSONB, nullable=True),
        sa.Column("next_earnings_date", sa.Date, nullable=True),
        sa.Column("beta", sa.Numeric, nullable=True),
        sa.Column("avg_daily_dollar_volume", sa.Numeric, nullable=True),
        sa.Column("base_thesis", sa.Text, nullable=True),
        sa.Column("base_thesis_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thesis_status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("deep_thesis", sa.Text, nullable=True),
        sa.Column("deep_thesis_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deep_thesis_sources", postgresql.JSONB, nullable=True),
        sa.Column("market_health", postgresql.JSONB, nullable=True),
        sa.Column("risk_flags", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text, nullable=False, server_default="watching"),
        sa.Column("watching_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_reason", sa.Text, nullable=True),
        sa.Column("user_notes", sa.Text, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX swing_ideas_active_ticker_stage_uniq "
        "ON swing_ideas (ticker, cycle_stage) "
        "WHERE status NOT IN ('exited', 'invalidated')"
    )
    op.create_index("ix_swing_ideas_status_detected", "swing_ideas", ["status", sa.text("detected_at DESC")])
    op.create_index("ix_swing_ideas_ticker", "swing_ideas", ["ticker"])
    op.execute(
        "CREATE INDEX ix_swing_ideas_thesis_pending "
        "ON swing_ideas (thesis_status) WHERE thesis_status = 'pending'"
    )

    # swing_idea_stage_transitions
    op.create_table(
        "swing_idea_stage_transitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_ideas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.Text, nullable=True),
        sa.Column("to_stage", sa.Text, nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("daily_close", sa.Numeric, nullable=True),
        sa.Column("snapshot", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_swing_stage_trans_idea_time", "swing_idea_stage_transitions", ["idea_id", "transitioned_at"])

    # swing_idea_snapshots
    op.create_table(
        "swing_idea_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_ideas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("snapshot_type", sa.Text, nullable=False),
        sa.Column("daily_close", sa.Numeric, nullable=True),
        sa.Column("daily_high", sa.Numeric, nullable=True),
        sa.Column("daily_low", sa.Numeric, nullable=True),
        sa.Column("daily_volume", sa.BigInteger, nullable=True),
        sa.Column("ema_10", sa.Numeric, nullable=True),
        sa.Column("ema_20", sa.Numeric, nullable=True),
        sa.Column("sma_50", sa.Numeric, nullable=True),
        sa.Column("sma_200", sa.Numeric, nullable=True),
        sa.Column("weekly_ema_10", sa.Numeric, nullable=True),
        sa.Column("rs_vs_qqq_20d", sa.Numeric, nullable=True),
        sa.Column("phase_osc_value", sa.Numeric, nullable=True),
        sa.Column("kell_stage", sa.Text, nullable=True),
        sa.Column("saty_setups_active", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("claude_analysis", sa.Text, nullable=True),
        sa.Column("claude_model", sa.Text, nullable=True),
        sa.Column("analysis_sources", postgresql.JSONB, nullable=True),
        sa.Column("deepvue_panel", postgresql.JSONB, nullable=True),
        sa.Column("chart_daily_url", sa.Text, nullable=True),
        sa.Column("chart_weekly_url", sa.Text, nullable=True),
        sa.Column("chart_60m_url", sa.Text, nullable=True),
        sa.UniqueConstraint("idea_id", "snapshot_date", "snapshot_type", name="uq_swing_snap_idea_date_type"),
    )
    op.create_index("ix_swing_snap_idea_date", "swing_idea_snapshots", ["idea_id", sa.text("snapshot_date DESC")])
    op.create_index("ix_swing_snap_date_type", "swing_idea_snapshots", [sa.text("snapshot_date DESC"), "snapshot_type"])

    # swing_events
    op.create_table(
        "swing_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_ideas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
    )
    op.create_index("ix_swing_events_idea_time", "swing_events", ["idea_id", sa.text("occurred_at DESC")])

    # swing_model_book
    op.create_table(
        "swing_model_book",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("setup_kell", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text, nullable=False),
        sa.Column("entry_date", sa.Date, nullable=True),
        sa.Column("exit_date", sa.Date, nullable=True),
        sa.Column("r_multiple", sa.Numeric, nullable=True),
        sa.Column("source_idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_ideas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ticker_fundamentals", postgresql.JSONB, nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("key_takeaways", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # swing_charts
    op.create_table(
        "swing_charts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_ideas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("swing_events.id", ondelete="CASCADE"), nullable=True),
        sa.Column("model_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("swing_model_book.id", ondelete="CASCADE"), nullable=True),
        sa.Column("image_url", sa.Text, nullable=False),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("timeframe", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("annotations", postgresql.JSONB, nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "num_nonnulls(idea_id, event_id, model_book_id) = 1",
            name="swing_charts_one_owner",
        ),
    )
    op.create_index("ix_swing_charts_idea", "swing_charts", ["idea_id"])
    op.create_index("ix_swing_charts_model_book", "swing_charts", ["model_book_id"])


def downgrade() -> None:
    op.drop_table("swing_charts")
    op.drop_table("swing_model_book")
    op.drop_table("swing_events")
    op.drop_table("swing_idea_snapshots")
    op.drop_table("swing_idea_stage_transitions")
    op.drop_table("swing_ideas")
    op.drop_table("swing_universe")
```

- [ ] **Step 3: Dry-run the migration (offline SQL)**

```bash
venv/bin/alembic upgrade 016_add_swing_tables --sql > /tmp/migration.sql
head -80 /tmp/migration.sql
```

Expected: valid SQL starts with `BEGIN;` and contains `CREATE TABLE swing_universe`. No syntax errors.

- [ ] **Step 4: Apply migration against a local test DB**

```bash
# Against local test database (DATABASE_URL must be set to test DB)
venv/bin/alembic upgrade head
venv/bin/alembic current
```

Expected: `alembic current` prints `016_add_swing_tables (head)`.

- [ ] **Step 5: Verify tables exist**

```bash
venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'swing_%' ORDER BY tablename\")
for row in cur.fetchall():
    print(row[0])
"
```

Expected: 7 rows printed — `swing_charts, swing_events, swing_idea_snapshots, swing_idea_stage_transitions, swing_ideas, swing_model_book, swing_universe`.

- [ ] **Step 6: Verify partial unique indexes + check constraint**

```bash
venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT indexname FROM pg_indexes WHERE tablename LIKE 'swing_%' AND indexname LIKE '%uniq%'\")
for row in cur.fetchall(): print(row[0])
"
```

Expected: `swing_universe_active_ticker_uniq` and `swing_ideas_active_ticker_stage_uniq` listed.

- [ ] **Step 7: Test downgrade**

```bash
venv/bin/alembic downgrade -1
venv/bin/alembic upgrade head
```

Expected: downgrade drops all 7 tables cleanly; upgrade recreates them.

- [ ] **Step 8: Commit**

```bash
git add alembic/versions/016_add_swing_tables.py
git commit -m "feat(swing): add Alembic migration for 7 swing tables"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `api/schemas/swing.py`

- [ ] **Step 1: Check schemas location convention**

```bash
ls api/schemas/ 2>/dev/null || find api -name "schemas" -type d -maxdepth 3
```

If `api/schemas/` doesn't exist, place the file at whatever path matches existing Pydantic models in this repo (e.g., same file as endpoint, or a `models/` directory). Adjust all subsequent file paths accordingly.

- [ ] **Step 2: Write Pydantic models for universe endpoints**

```python
# api/schemas/swing.py
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UniverseTicker(BaseModel):
    ticker: str
    source: Literal["deepvue-csv", "manual", "backend-generated"]
    batch_id: UUID
    added_at: datetime
    extras: dict[str, Any] | None = None


class UniverseListResponse(BaseModel):
    tickers: list[UniverseTicker]
    source_summary: dict[str, int]   # {"deepvue-csv": 152, "manual": 3}
    active_count: int
    latest_batch_at: datetime | None


class UniverseAddSingleRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)

    @field_validator("ticker")
    @classmethod
    def uppercase_and_strip(cls, v: str) -> str:
        return v.strip().upper()


class UniverseUploadResponse(BaseModel):
    batch_id: UUID
    mode: Literal["replace", "add"]
    tickers_added: int
    tickers_removed: int
    total_active: int


class UniverseHistoryEntry(BaseModel):
    batch_id: UUID
    source: str
    uploaded_at: datetime
    ticker_count: int


class UniverseHistoryResponse(BaseModel):
    batches: list[UniverseHistoryEntry]
```

- [ ] **Step 3: Verify import works**

```bash
venv/bin/python -c "from api.schemas.swing import UniverseListResponse; print(UniverseListResponse.model_fields.keys())"
```

Expected: prints the field names.

- [ ] **Step 4: Commit**

```bash
git add api/schemas/swing.py
git commit -m "feat(swing): add Pydantic schemas for universe endpoints"
```

---

## Task 4: Test fixtures for Supabase

**Files:**
- Create: `tests/swing/__init__.py`
- Create: `tests/fixtures/swing_fixtures.py`

- [ ] **Step 1: Create test module**

```bash
mkdir -p tests/swing
touch tests/swing/__init__.py
```

- [ ] **Step 2: Write Supabase mock fixture**

Read the existing `tests/conftest.py` to see how the market_monitor tests mock Supabase; match that pattern. If no existing Supabase mock, create `tests/fixtures/swing_fixtures.py`:

```python
# tests/fixtures/swing_fixtures.py
from typing import Any
from unittest.mock import MagicMock

import pytest


class FakeSupabaseTable:
    """In-memory stand-in for supabase_client.table() returning rows."""

    def __init__(self, initial_rows: list[dict[str, Any]] | None = None):
        self.rows: list[dict[str, Any]] = list(initial_rows or [])
        self._where: list[tuple[str, Any, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self._where.append((col, "eq", val))
        return self

    def is_(self, col, val):
        self._where.append((col, "is", val))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, rows):
        if isinstance(rows, dict):
            rows = [rows]
        self.rows.extend(rows)
        return MagicMock(execute=lambda: MagicMock(data=rows))

    def update(self, patch):
        matched = self._apply_where()
        for r in matched:
            r.update(patch)
        return MagicMock(execute=lambda: MagicMock(data=matched))

    def upsert(self, rows, on_conflict=None):
        return self.insert(rows)

    def delete(self):
        matched = self._apply_where()
        for r in matched:
            self.rows.remove(r)
        return MagicMock(execute=lambda: MagicMock(data=matched))

    def execute(self):
        rows = self._apply_where()
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit:
            rows = rows[: self._limit]
        return MagicMock(data=rows)

    def _apply_where(self) -> list[dict[str, Any]]:
        def match(row):
            for col, op, val in self._where:
                if op == "eq" and row.get(col) != val:
                    return False
                if op == "is" and row.get(col) is not val:
                    return False
            return True
        return [r for r in self.rows if match(r)]


class FakeSupabaseClient:
    def __init__(self):
        self.tables: dict[str, FakeSupabaseTable] = {}

    def table(self, name: str) -> FakeSupabaseTable:
        return self.tables.setdefault(name, FakeSupabaseTable())


@pytest.fixture
def fake_supabase():
    return FakeSupabaseClient()
```

- [ ] **Step 3: Verify fixture imports**

```bash
venv/bin/pytest tests/swing/ --collect-only 2>&1 | head -20
```

Expected: no import errors.

- [ ] **Step 4: Commit**

```bash
git add tests/swing/ tests/fixtures/swing_fixtures.py
git commit -m "test(swing): add in-memory Supabase fixture"
```

---

## Task 5: Universe filter stages (TDD)

**Files:**
- Create: `api/indicators/swing/universe/filters.py`
- Create: `tests/swing/test_universe_filters.py`

- [ ] **Step 1: Write failing tests for Stage 1 (price + liquidity)**

```python
# tests/swing/test_universe_filters.py
import pandas as pd
import pytest

from api.indicators.swing.universe.filters import (
    stage1_price_liquidity,
    stage2_trend_base,
    stage3_fundamentals,
    stage4_relative_strength,
)


def _bars(ticker: str, price: float, volume: int = 1_000_000, days: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-03-01", periods=days, freq="B")
    return pd.DataFrame({
        "ticker": ticker,
        "date": dates,
        "close": price,
        "volume": volume,
    })


def test_stage1_passes_high_price_high_volume():
    df = _bars("AAPL", price=200.0, volume=10_000_000)   # $2B/day volume
    assert stage1_price_liquidity(df)


def test_stage1_fails_low_price():
    df = _bars("PENNY", price=3.0, volume=10_000_000)
    assert not stage1_price_liquidity(df)


def test_stage1_fails_low_dollar_volume():
    df = _bars("ILLIQ", price=200.0, volume=50_000)   # $10M/day
    assert not stage1_price_liquidity(df)


def test_stage1_fails_price_too_high():
    df = _bars("BRK", price=5_000.0, volume=100_000)
    assert not stage1_price_liquidity(df)
```

- [ ] **Step 2: Run tests — expect fail (import error)**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py::test_stage1_passes_high_price_high_volume -v
```

Expected: ImportError on `filters`.

- [ ] **Step 3: Implement Stage 1**

```python
# api/indicators/swing/universe/filters.py
"""Universe filter pipeline — 4 stages applied cheapest-first.

Stage 1: price + liquidity (price-only data, fast)
Stage 2: trend + base proxy (price-only, fast)
Stage 3: fundamentals (yfinance quarterly financials, slow — only for Stage 1+2 passers)
Stage 4: relative strength vs QQQ (price-only, fast)

Each stage takes a DataFrame of bars for one ticker and returns bool (pass/fail).
The orchestrator (generator.py) applies stages in sequence.
"""
from __future__ import annotations

import pandas as pd

MIN_PRICE = 50.0
MAX_PRICE = 1_000.0
MIN_DOLLAR_VOLUME_20D = 20_000_000   # Kell: $20M min daily dollar volume
MAX_BASE_RANGE_PCT = 0.15            # 5-8 week base proxy
MIN_REV_GROWTH_YOY = 0.30            # Kell says 40%; relaxed to 30% (yfinance noise)
MIN_RS_VS_QQQ_63D = 0.0              # must outperform


def stage1_price_liquidity(bars: pd.DataFrame) -> bool:
    """Stage 1: price in [50, 1000] + avg 20d dollar volume >= $20M."""
    if bars.empty:
        return False
    last_close = bars["close"].iloc[-1]
    if not (MIN_PRICE <= last_close <= MAX_PRICE):
        return False
    last_20 = bars.tail(20)
    if len(last_20) < 20:
        return False
    dollar_volume = (last_20["close"] * last_20["volume"]).mean()
    return dollar_volume >= MIN_DOLLAR_VOLUME_20D
```

- [ ] **Step 4: Run Stage 1 tests — expect pass**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py -v -k stage1
```

Expected: 4 passing.

- [ ] **Step 5: Write failing tests for Stage 2 (trend + base)**

```python
def test_stage2_passes_above_200sma_tight_range():
    # 30 days of close ~200 with small variation → tight base
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = [100.0] * 180 + [200.0] * 40    # long below-200 history, then consolidating at 200
    df = pd.DataFrame({"date": dates, "close": closes, "volume": 1_000_000})
    assert stage2_trend_base(df)


def test_stage2_fails_below_200sma():
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = [200.0] * 180 + [100.0] * 40    # now below 200-SMA
    df = pd.DataFrame({"date": dates, "close": closes, "volume": 1_000_000})
    assert not stage2_trend_base(df)


def test_stage2_fails_wide_range_no_base():
    dates = pd.date_range("2026-03-01", periods=220, freq="B")
    closes = list(range(100, 320))           # monotonic rally — no base
    df = pd.DataFrame({"date": dates[-220:], "close": closes[-220:], "volume": 1_000_000})
    # Range over last 30 bars: (319-289)/305 ≈ 10% — this actually passes. Let's make it fail:
    closes2 = list(range(100, 300)) + [400.0] * 20   # huge spike in last 20
    df2 = pd.DataFrame({"date": dates, "close": closes2, "volume": 1_000_000})
    assert not stage2_trend_base(df2)
```

- [ ] **Step 6: Run — fail**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py -v -k stage2
```

Expected: NameError on `stage2_trend_base`.

- [ ] **Step 7: Implement Stage 2**

```python
def stage2_trend_base(bars: pd.DataFrame) -> bool:
    """Stage 2: close > SMA-200 AND last-30-bar range / mid-price < 15%."""
    if len(bars) < 200:
        return False
    sma_200 = bars["close"].tail(200).mean()
    last_close = bars["close"].iloc[-1]
    if last_close <= sma_200:
        return False
    last_30 = bars["close"].tail(30)
    if len(last_30) < 30:
        return False
    hi, lo = last_30.max(), last_30.min()
    mid = (hi + lo) / 2
    if mid <= 0:
        return False
    return (hi - lo) / mid < MAX_BASE_RANGE_PCT
```

- [ ] **Step 8: Run Stage 2 tests — pass**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py -v -k stage2
```

Expected: 3 passing.

- [ ] **Step 9: Write failing tests for Stage 3 (fundamentals)**

Stage 3 takes a fundamentals dict (from yfinance) not a bars DataFrame — matches the actual call pattern since fundamentals are fetched separately from bars.

```python
def test_stage3_passes_accelerating_growth():
    fundamentals = {
        "quarterly_revenue_yoy": [0.45, 0.38, 0.30, 0.22],   # newest first
    }
    assert stage3_fundamentals(fundamentals)


def test_stage3_fails_below_threshold():
    fundamentals = {"quarterly_revenue_yoy": [0.20, 0.18, 0.15]}
    assert not stage3_fundamentals(fundamentals)


def test_stage3_fails_decelerating():
    fundamentals = {"quarterly_revenue_yoy": [0.30, 0.45, 0.50]}   # decelerating
    assert not stage3_fundamentals(fundamentals)


def test_stage3_fails_no_data():
    fundamentals = {}
    assert not stage3_fundamentals(fundamentals)
```

- [ ] **Step 10: Run — fail**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py -v -k stage3
```

- [ ] **Step 11: Implement Stage 3**

```python
def stage3_fundamentals(fundamentals: dict) -> bool:
    """Stage 3: latest Q rev growth >= 30% AND accelerating from prior quarter.

    Expects `quarterly_revenue_yoy` list ordered newest-first.
    """
    rev = fundamentals.get("quarterly_revenue_yoy")
    if not rev or len(rev) < 2:
        return False
    latest, prior = rev[0], rev[1]
    if latest is None or prior is None:
        return False
    if latest < MIN_REV_GROWTH_YOY:
        return False
    return latest > prior
```

- [ ] **Step 12: Run — pass**

- [ ] **Step 13: Write failing tests for Stage 4 (RS)**

```python
def test_stage4_passes_outperforms_qqq_63d():
    dates = pd.date_range("2026-01-01", periods=70, freq="B")
    ticker = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.5 for i in range(70)]})
    qqq = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.1 for i in range(70)]})
    assert stage4_relative_strength(ticker, qqq)


def test_stage4_fails_underperforms_qqq():
    dates = pd.date_range("2026-01-01", periods=70, freq="B")
    ticker = pd.DataFrame({"date": dates, "close": [100.0 - i * 0.1 for i in range(70)]})
    qqq = pd.DataFrame({"date": dates, "close": [100.0 + i * 0.5 for i in range(70)]})
    assert not stage4_relative_strength(ticker, qqq)
```

- [ ] **Step 14: Run — fail**

- [ ] **Step 15: Implement Stage 4**

```python
def stage4_relative_strength(ticker_bars: pd.DataFrame, qqq_bars: pd.DataFrame) -> bool:
    """Stage 4: ticker 63d return > QQQ 63d return."""
    if len(ticker_bars) < 63 or len(qqq_bars) < 63:
        return False
    def _ret(df: pd.DataFrame) -> float:
        start = df["close"].iloc[-63]
        end = df["close"].iloc[-1]
        return (end - start) / start if start > 0 else -1.0
    return _ret(ticker_bars) > _ret(qqq_bars) + MIN_RS_VS_QQQ_63D
```

- [ ] **Step 16: Run all filter tests**

```bash
venv/bin/pytest tests/swing/test_universe_filters.py -v
```

Expected: all passing.

- [ ] **Step 17: Commit**

```bash
git add api/indicators/swing/universe/filters.py tests/swing/test_universe_filters.py
git commit -m "feat(swing): add 4-stage universe filter pipeline with tests"
```

---

## Task 6: Universe generator (orchestrates filter stages)

**Files:**
- Create: `api/indicators/swing/universe/generator.py`
- Create: `tests/swing/test_universe_generator.py`

- [ ] **Step 1: Write failing test for happy path**

```python
# tests/swing/test_universe_generator.py
from unittest.mock import patch

from api.indicators.swing.universe.generator import generate_backend_universe


@patch("api.indicators.swing.universe.generator._fetch_bars_bulk")
@patch("api.indicators.swing.universe.generator._fetch_fundamentals")
def test_generator_returns_passers(mock_funds, mock_bars):
    import pandas as pd
    # AAPL passes all 4 stages; PENNY fails stage 1
    dates = pd.date_range("2025-10-01", periods=220, freq="B")
    mock_bars.side_effect = lambda tickers: {
        "AAPL": pd.DataFrame({"date": dates, "close": [150.0 + i * 0.1 for i in range(220)], "volume": 10_000_000}),
        "PENNY": pd.DataFrame({"date": dates, "close": [3.0] * 220, "volume": 1000}),
        "QQQ":   pd.DataFrame({"date": dates, "close": [400.0 + i * 0.02 for i in range(220)], "volume": 5_000_000}),
    }
    mock_funds.side_effect = lambda t: {
        "AAPL": {"quarterly_revenue_yoy": [0.45, 0.38, 0.30]},
        "PENNY": {"quarterly_revenue_yoy": [0.05, 0.04]},
    }[t]

    result = generate_backend_universe(tickers=["AAPL", "PENNY"])

    assert "AAPL" in result["passers"]
    assert "PENNY" not in result["passers"]
    assert result["passers"]["AAPL"]["fundamentals"] == {"quarterly_revenue_yoy": [0.45, 0.38, 0.30]}
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement generator**

```python
# api/indicators/swing/universe/generator.py
"""Backend universe generator — applies 4 filter stages over a base ticker list.

Called weekly from the Sunday cron when Deepvue-sourced universe is > 7 days stale.
Results are persisted via universe/resolver.py save_backend_universe().

Runtime: ~10-15 min for ~3500 base tickers because Stage 3 requires a yfinance
fundamentals call per Stage 1+2 passer (~200-400 calls, rate-limited).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from api.indicators.swing.universe.filters import (
    stage1_price_liquidity,
    stage2_trend_base,
    stage3_fundamentals,
    stage4_relative_strength,
)

logger = logging.getLogger(__name__)

BASE_TICKERS_PATH = Path(__file__).parent / "base_tickers.json"


def _load_base_tickers() -> list[str]:
    with BASE_TICKERS_PATH.open() as f:
        return json.load(f)["tickers"]


def _fetch_bars_bulk(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Bulk-fetch daily bars via yfinance. Returns {ticker: DataFrame} including QQQ."""
    import yfinance as yf
    all_tickers = list(set(tickers) | {"QQQ"})
    raw = yf.download(all_tickers, period="1y", group_by="ticker", progress=False, auto_adjust=True)
    result: dict[str, pd.DataFrame] = {}
    for t in all_tickers:
        try:
            sub = raw[t].dropna().reset_index().rename(columns={"Date": "date", "Close": "close", "Volume": "volume"})
            result[t] = sub[["date", "close", "volume"]]
        except Exception as e:
            logger.warning("Failed to unpack bars for %s: %s", t, e)
    return result


def _fetch_fundamentals(ticker: str) -> dict:
    """Fetch quarterly revenue growth via yfinance. Returns dict with quarterly_revenue_yoy list."""
    import yfinance as yf
    try:
        tk = yf.Ticker(ticker)
        fin = tk.quarterly_financials
        if fin is None or fin.empty:
            return {}
        if "Total Revenue" not in fin.index:
            return {}
        rev = fin.loc["Total Revenue"].dropna()
        if len(rev) < 5:
            return {}
        yoy = []
        for i in range(len(rev) - 4):
            curr = rev.iloc[i]
            prior = rev.iloc[i + 4]
            if prior and prior > 0:
                yoy.append(float((curr - prior) / prior))
        return {"quarterly_revenue_yoy": yoy}
    except Exception as e:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, e)
        return {}


def generate_backend_universe(
    tickers: list[str] | None = None,
) -> dict:
    """Run the 4-stage filter pipeline. Returns {"passers": {ticker: {fundamentals}}, "stats": {...}}."""
    if tickers is None:
        tickers = _load_base_tickers()

    logger.info("Starting universe generation for %d base tickers", len(tickers))
    bars = _fetch_bars_bulk(tickers)
    qqq = bars.get("QQQ")
    if qqq is None or qqq.empty:
        raise RuntimeError("QQQ bars unavailable — cannot compute RS")

    # Stage 1 + 2 (price-only)
    stage12_pass: list[str] = []
    for t in tickers:
        b = bars.get(t)
        if b is None or not stage1_price_liquidity(b):
            continue
        if not stage2_trend_base(b):
            continue
        stage12_pass.append(t)
    logger.info("Stage 1+2: %d / %d passed", len(stage12_pass), len(tickers))

    # Stage 3 (fundamentals — only for stage-1+2 passers)
    stage3_pass: dict[str, dict] = {}
    for t in stage12_pass:
        f = _fetch_fundamentals(t)
        if f and stage3_fundamentals(f):
            stage3_pass[t] = f
    logger.info("Stage 3: %d passed", len(stage3_pass))

    # Stage 4 (RS vs QQQ)
    passers: dict[str, dict] = {}
    for t, fund in stage3_pass.items():
        if stage4_relative_strength(bars[t], qqq):
            passers[t] = {"fundamentals": fund}
    logger.info("Stage 4: %d passed — final universe size %d", len(passers), len(passers))

    return {
        "passers": passers,
        "stats": {
            "base_count": len(tickers),
            "stage12_count": len(stage12_pass),
            "stage3_count": len(stage3_pass),
            "final_count": len(passers),
        },
    }
```

- [ ] **Step 4: Run generator test — pass**

```bash
venv/bin/pytest tests/swing/test_universe_generator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/indicators/swing/universe/generator.py tests/swing/test_universe_generator.py
git commit -m "feat(swing): add backend universe generator orchestrating 4 filter stages"
```

---

## Task 7: Universe resolver (Deepvue → backend fallback)

**Files:**
- Create: `api/indicators/swing/universe/resolver.py`
- Create: `tests/swing/test_universe_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_universe_resolver.py
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api.indicators.swing.universe.resolver import (
    resolve_universe,
    save_universe_batch,
)
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def test_resolve_uses_fresh_deepvue():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    batch = str(uuid4())
    sb.table("swing_universe").insert([
        {"id": 1, "ticker": "AAPL", "source": "deepvue-csv", "batch_id": batch,
         "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None, "extras": {}},
        {"id": 2, "ticker": "NVDA", "source": "deepvue-csv", "batch_id": batch,
         "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None, "extras": {}},
    ])
    result = resolve_universe(sb)
    assert result.source == "deepvue"
    assert set(result.tickers) == {"AAPL", "NVDA"}


def test_resolve_falls_back_to_backend_when_deepvue_stale():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(days=10)).isoformat()
    fresh = (now - timedelta(days=2)).isoformat()
    sb.table("swing_universe").insert([
        {"id": 1, "ticker": "AAPL", "source": "deepvue-csv", "batch_id": str(uuid4()),
         "added_at": stale, "removed_at": None, "extras": {}},
        {"id": 2, "ticker": "MSFT", "source": "backend-generated", "batch_id": str(uuid4()),
         "added_at": fresh, "removed_at": None, "extras": {}},
    ])
    result = resolve_universe(sb)
    assert result.source == "backend-stale-deepvue"
    assert "MSFT" in result.tickers
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement resolver**

```python
# api/indicators/swing/universe/resolver.py
"""Resolve the active universe: Deepvue CSV first, backend-generated fallback.

Freshness window: 7 days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4


FRESHNESS_DAYS = 7


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


@dataclass
class ResolvedUniverse:
    tickers: list[str]
    source: str               # 'deepvue' | 'backend-stale-deepvue' | 'backend-fresh' | 'empty'
    latest_upload: datetime | None
    extras_by_ticker: dict[str, dict]


def _latest_by_source(sb: SupabaseLike, source: str) -> list[dict]:
    rows = (
        sb.table("swing_universe")
        .select("*")
        .eq("source", source)
        .is_("removed_at", None)
        .order("added_at", desc=True)
        .execute()
        .data
    )
    return rows or []


def resolve_universe(sb: SupabaseLike) -> ResolvedUniverse:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESHNESS_DAYS)

    deepvue_rows = _latest_by_source(sb, "deepvue-csv") + _latest_by_source(sb, "manual")
    if deepvue_rows:
        latest = max(_parse_ts(r["added_at"]) for r in deepvue_rows)
        if latest >= cutoff:
            return ResolvedUniverse(
                tickers=[r["ticker"] for r in deepvue_rows],
                source="deepvue",
                latest_upload=latest,
                extras_by_ticker={r["ticker"]: (r.get("extras") or {}) for r in deepvue_rows},
            )

    backend_rows = _latest_by_source(sb, "backend-generated")
    if backend_rows:
        latest = max(_parse_ts(r["added_at"]) for r in backend_rows)
        if latest >= cutoff:
            return ResolvedUniverse(
                tickers=[r["ticker"] for r in backend_rows],
                source="backend-stale-deepvue",
                latest_upload=latest,
                extras_by_ticker={r["ticker"]: (r.get("extras") or {}) for r in backend_rows},
            )

    return ResolvedUniverse(tickers=[], source="empty", latest_upload=None, extras_by_ticker={})


def save_universe_batch(
    sb: SupabaseLike,
    tickers_with_extras: dict[str, dict],
    source: str,
    mode: str = "replace",
) -> UUID:
    """Insert new batch. If mode='replace', soft-delete all prior active rows of this source."""
    batch_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    if mode == "replace":
        sb.table("swing_universe").update({"removed_at": now}).eq("source", source).is_("removed_at", None).execute()

    rows = [
        {
            "ticker": t,
            "source": source,
            "batch_id": str(batch_id),
            "added_at": now,
            "removed_at": None,
            "extras": extras,
        }
        for t, extras in tickers_with_extras.items()
    ]
    if rows:
        sb.table("swing_universe").insert(rows).execute()

    return batch_id


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
```

- [ ] **Step 4: Run resolver tests — pass**

- [ ] **Step 5: Commit**

```bash
git add api/indicators/swing/universe/resolver.py tests/swing/test_universe_resolver.py
git commit -m "feat(swing): add universe resolver with Deepvue/backend fallback"
```

---

## Task 8: Universe endpoints (GET, upload, add, delete, history)

**Files:**
- Create: `api/endpoints/swing.py`
- Modify: `api/main.py` — register the new router
- Create: `tests/swing/test_universe_endpoints.py`

- [ ] **Step 1: Study the repo's Supabase pattern**

```bash
grep -n "from supabase\|_get_supabase\|create_client" api/endpoints/market_monitor.py | head -10
```

**Repo convention** (confirmed via `api/endpoints/market_monitor.py` lines 26, 41-47):
- Module-level `_get_supabase() -> Client` helper caches a singleton from `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars
- Endpoints call `sb = _get_supabase()` **inline**, not via FastAPI `Depends`
- **Do not introduce `Depends` or a new `api/dependencies.py`** — stay consistent with the existing pattern

For tests, override by monkey-patching the module-level `_get_supabase` function.

- [ ] **Step 2: Write failing endpoint test (GET universe)**

Because the repo doesn't use `Depends`, override Supabase via monkey-patching the module-level `_get_supabase` function. Verify `tests/conftest.py` exists and whether any shared `client`/`app` fixture already exists — if not, we create a local one here:

```python
# tests/swing/test_universe_endpoints.py
import pytest
from fastapi.testclient import TestClient

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


def test_get_universe_empty(client: TestClient):
    r = client.get("/api/swing/universe")
    assert r.status_code == 200
    data = r.json()
    assert data["active_count"] == 0
    assert data["tickers"] == []
```

If `tests/conftest.py` already exports a `client` fixture, remove the local one and add only the `fake_sb` monkey-patch.

- [ ] **Step 3: Run — fail (404)**

- [ ] **Step 4: Implement endpoints**

```python
# api/endpoints/swing.py
"""Swing trading endpoints — universe management in this plan; detection/analysis in later plans."""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from supabase import Client, create_client

from api.indicators.swing.universe.resolver import (
    resolve_universe,
    save_universe_batch,
)
from api.schemas.swing import (
    UniverseAddSingleRequest,
    UniverseHistoryEntry,
    UniverseHistoryResponse,
    UniverseListResponse,
    UniverseTicker,
    UniverseUploadResponse,
)

router = APIRouter(prefix="/api/swing", tags=["swing"])

_supabase: Client | None = None


def _get_supabase() -> Client:
    """Module-level singleton — matches market_monitor.py pattern.
    Tests override by monkey-patching this function."""
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


@router.get("/universe", response_model=UniverseListResponse)
def get_universe():
    sb = _get_supabase()
    resolved = resolve_universe(sb)
    all_active = (
        sb.table("swing_universe").select("*").is_("removed_at", None).order("added_at", desc=True).execute().data
        or []
    )
    source_summary: dict[str, int] = {}
    for r in all_active:
        source_summary[r["source"]] = source_summary.get(r["source"], 0) + 1
    return UniverseListResponse(
        tickers=[
            UniverseTicker(
                ticker=r["ticker"],
                source=r["source"],
                batch_id=r["batch_id"],
                added_at=r["added_at"],
                extras=r.get("extras"),
            )
            for r in all_active
        ],
        source_summary=source_summary,
        active_count=len(all_active),
        latest_batch_at=resolved.latest_upload,
    )


@router.post("/universe", response_model=UniverseTicker)
def add_single_ticker(req: UniverseAddSingleRequest):
    sb = _get_supabase()
    existing = (
        sb.table("swing_universe")
        .select("*")
        .eq("ticker", req.ticker)
        .is_("removed_at", None)
        .execute()
        .data
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{req.ticker} already in active universe")

    batch_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "ticker": req.ticker,
        "source": "manual",
        "batch_id": str(batch_id),
        "added_at": now,
        "removed_at": None,
        "extras": {},
    }
    sb.table("swing_universe").insert(row).execute()
    return UniverseTicker(**row)


@router.post("/universe/upload", response_model=UniverseUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    mode: str = Form(...),
):
    sb = _get_supabase()
    if mode not in ("replace", "add"):
        raise HTTPException(status_code=400, detail="mode must be 'replace' or 'add'")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Expected .csv file")

    body = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(body))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    ticker_col = next((c for c in reader.fieldnames if c.lower() in ("ticker", "symbol")), None)
    if ticker_col is None:
        raise HTTPException(status_code=400, detail="CSV must contain a 'ticker' or 'symbol' column")

    tickers_with_extras: dict[str, dict] = {}
    for row in reader:
        t = (row.get(ticker_col) or "").strip().upper()
        if not t:
            continue
        extras = {k: v for k, v in row.items() if k != ticker_col and v not in ("", None)}
        tickers_with_extras[t] = extras
    if not tickers_with_extras:
        raise HTTPException(status_code=400, detail="CSV had no usable tickers")

    removed_before = 0
    if mode == "replace":
        existing = (
            sb.table("swing_universe").select("id").eq("source", "deepvue-csv").is_("removed_at", None).execute().data or []
        )
        removed_before = len(existing)

    batch_id = save_universe_batch(sb, tickers_with_extras, source="deepvue-csv", mode=mode)
    active_count = len(sb.table("swing_universe").select("id").is_("removed_at", None).execute().data or [])

    return UniverseUploadResponse(
        batch_id=batch_id,
        mode=mode,
        tickers_added=len(tickers_with_extras),
        tickers_removed=removed_before,
        total_active=active_count,
    )


@router.delete("/universe/{ticker}")
def remove_ticker(ticker: str):
    sb = _get_supabase()
    ticker = ticker.upper()
    existing = (
        sb.table("swing_universe").select("*").eq("ticker", ticker).is_("removed_at", None).execute().data or []
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"{ticker} not in active universe")
    now = datetime.now(timezone.utc).isoformat()
    sb.table("swing_universe").update({"removed_at": now}).eq("ticker", ticker).is_("removed_at", None).execute()
    return {"removed": ticker, "removed_at": now}


@router.get("/universe/history", response_model=UniverseHistoryResponse)
def get_universe_history():
    sb = _get_supabase()
    rows = sb.table("swing_universe").select("batch_id, source, added_at").order("added_at", desc=True).execute().data or []
    batches: dict[str, UniverseHistoryEntry] = {}
    for r in rows:
        bid = r["batch_id"]
        if bid not in batches:
            batches[bid] = UniverseHistoryEntry(batch_id=bid, source=r["source"], uploaded_at=r["added_at"], ticker_count=1)
        else:
            batches[bid].ticker_count += 1
    return UniverseHistoryResponse(batches=list(batches.values())[:50])
```

- [ ] **Step 5: Register router in `api/main.py`**

```python
# api/main.py — add:
from api.endpoints import swing
app.include_router(swing.router)
```

- [ ] **Step 6: Write failing tests for each endpoint, then iterate to green**

TDD loop per endpoint — write the test, run to confirm failure, add implementation or fix until passing. Minimum required tests:

```python
def test_add_single_ticker_success(client, fake_sb):
    r = client.post("/api/swing/universe", json={"ticker": "nvda"})
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"   # uppercased
    assert r.json()["source"] == "manual"


def test_add_single_ticker_conflict(client, fake_sb):
    client.post("/api/swing/universe", json={"ticker": "NVDA"})
    r = client.post("/api/swing/universe", json={"ticker": "NVDA"})
    assert r.status_code == 409


def test_upload_csv_add_mode(client, fake_sb):
    csv_body = "ticker,revenue_growth\nAAPL,0.45\nNVDA,0.78\n"
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", csv_body, "text/csv")},
        data={"mode": "add"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tickers_added"] == 2
    assert body["tickers_removed"] == 0
    assert body["mode"] == "add"
    # Extras preserved
    listing = client.get("/api/swing/universe").json()
    aapl = next(t for t in listing["tickers"] if t["ticker"] == "AAPL")
    assert aapl["extras"]["revenue_growth"] == "0.45"


def test_upload_csv_replace_mode(client, fake_sb):
    csv1 = "ticker\nAAPL\nNVDA\nMSFT\n"
    csv2 = "ticker\nNVDA\nCRWD\n"
    client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv1, "text/csv")}, data={"mode": "add"})
    r = client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv2, "text/csv")}, data={"mode": "replace"})
    assert r.status_code == 200
    assert r.json()["tickers_removed"] == 3   # 3 deepvue-csv rows soft-deleted
    assert r.json()["tickers_added"] == 2
    listing = client.get("/api/swing/universe").json()
    assert {t["ticker"] for t in listing["tickers"]} == {"NVDA", "CRWD"}


def test_upload_csv_missing_ticker_column(client, fake_sb):
    bad = "name,value\nFoo,1\n"
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", bad, "text/csv")},
        data={"mode": "add"},
    )
    assert r.status_code == 400
    assert "ticker" in r.json()["detail"].lower() or "symbol" in r.json()["detail"].lower()


def test_upload_csv_non_csv_file(client, fake_sb):
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.txt", "AAPL", "text/plain")},
        data={"mode": "add"},
    )
    assert r.status_code == 400


def test_upload_csv_invalid_mode(client, fake_sb):
    r = client.post(
        "/api/swing/universe/upload",
        files={"file": ("u.csv", "ticker\nAAPL\n", "text/csv")},
        data={"mode": "wipe"},
    )
    assert r.status_code == 400


def test_remove_ticker_success(client, fake_sb):
    client.post("/api/swing/universe", json={"ticker": "AAPL"})
    r = client.delete("/api/swing/universe/AAPL")
    assert r.status_code == 200
    listing = client.get("/api/swing/universe").json()
    assert listing["active_count"] == 0


def test_remove_ticker_not_found(client, fake_sb):
    r = client.delete("/api/swing/universe/XYZXYZ")
    assert r.status_code == 404


def test_history_groups_by_batch(client, fake_sb):
    csv_body = "ticker\nAAPL\nNVDA\n"
    client.post("/api/swing/universe/upload", files={"file": ("u.csv", csv_body, "text/csv")}, data={"mode": "add"})
    r = client.get("/api/swing/universe/history")
    assert r.status_code == 200
    batches = r.json()["batches"]
    # One batch containing 2 tickers
    assert any(b["ticker_count"] == 2 and b["source"] == "deepvue-csv" for b in batches)
```

Run each test first, confirm it fails, then implement/fix to pass. Batch commits per endpoint.

- [ ] **Step 7: Run full endpoint test suite**

```bash
venv/bin/pytest tests/swing/test_universe_endpoints.py -v
```

Expected: all passing.

- [ ] **Step 8: Smoke-test against real backend**

```bash
# in one shell
venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8080
# in another shell
curl http://localhost:8080/api/swing/universe
curl -X POST http://localhost:8080/api/swing/universe -H "Content-Type: application/json" -d '{"ticker":"AAPL"}'
curl http://localhost:8080/api/swing/universe
curl -X DELETE http://localhost:8080/api/swing/universe/AAPL
```

Expected: list, add, re-list (shows AAPL), delete all return sensible JSON.

- [ ] **Step 9: Commit**

```bash
git add api/endpoints/swing.py api/main.py tests/swing/test_universe_endpoints.py
git commit -m "feat(swing): add universe management endpoints (CRUD + CSV upload + history)"
```

---

## Task 9: Frontend TypeScript types

**Files:**
- Modify: `frontend/src/lib/types.ts` (append) OR create `frontend/src/lib/swing-types.ts`

- [ ] **Step 1: Decide location — follow existing convention**

```bash
grep -c "Momentum\|Idea\|Watchlist" frontend/src/lib/types.ts
```

If existing types aggregate in `types.ts`, append there. Otherwise create `swing-types.ts`. This plan assumes appending to `types.ts` (matches Momentum Scanner pattern).

- [ ] **Step 2: Append swing types**

```typescript
// frontend/src/lib/types.ts (append at end)

// ---------------------------------------------------------------------------
// Swing Trading — Universe (Plan 1)
// ---------------------------------------------------------------------------

export type SwingUniverseSource = "deepvue-csv" | "manual" | "backend-generated"

export interface SwingUniverseTicker {
  ticker: string
  source: SwingUniverseSource
  batch_id: string
  added_at: string
  extras: Record<string, unknown> | null
}

export interface SwingUniverseListResponse {
  tickers: SwingUniverseTicker[]
  source_summary: Record<SwingUniverseSource, number>
  active_count: number
  latest_batch_at: string | null
}

export interface SwingUniverseUploadResponse {
  batch_id: string
  mode: "replace" | "add"
  tickers_added: number
  tickers_removed: number
  total_active: number
}

export interface SwingUniverseHistoryEntry {
  batch_id: string
  source: string
  uploaded_at: string
  ticker_count: number
}
```

- [ ] **Step 3: Verify types compile**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(swing): add TypeScript types for universe management"
```

---

## Task 10: Frontend API proxy routes

**Files:**
- Create: `frontend/src/app/api/swing/universe/route.ts`
- Create: `frontend/src/app/api/swing/universe/upload/route.ts`
- Create: `frontend/src/app/api/swing/universe/[ticker]/route.ts`
- Create: `frontend/src/app/api/swing/universe/history/route.ts`

- [ ] **Step 1: Check existing proxy pattern**

```bash
head -25 frontend/src/app/api/screener/momentum-scan/route.ts
```

Use the identical `railwayFetch()` pattern.

- [ ] **Step 2: Create GET / POST single route**

```typescript
// frontend/src/app/api/swing/universe/route.ts
import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export async function GET() {
  try {
    const response = await railwayFetch("/api/swing/universe")
    const data = await response.json()
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const response = await railwayFetch("/api/swing/universe", body)
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status })
  }
}
```

- [ ] **Step 3: Create CSV upload route (multipart passthrough)**

The existing `railwayFetch` (`frontend/src/lib/railway.ts`) is POST-JSON-only and reads from `RAILWAY_API_URL`. For multipart, we bypass it and reuse the same env var + base-URL logic:

```typescript
// frontend/src/app/api/swing/universe/upload/route.ts
import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const url = `${getBaseUrl()}/api/swing/universe/upload`
    const response = await fetch(url, { method: "POST", body: formData })
    const data = await response.json().catch(() => ({ error: "invalid response" }))
    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status: 502 })
  }
}
```

- [ ] **Step 4: Create DELETE by ticker route**

`railwayFetch` hardcodes `method: "POST"`, so DELETE cannot go through it without extending the library. For this one operation we inline the fetch against the same base URL (matches the upload route pattern above):

```typescript
// frontend/src/app/api/swing/universe/[ticker]/route.ts
import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  try {
    const url = `${getBaseUrl()}/api/swing/universe/${encodeURIComponent(ticker)}`
    const response = await fetch(url, { method: "DELETE" })
    const data = await response.json().catch(() => ({ error: "invalid response" }))
    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status: 502 })
  }
}
```

*(Follow-up note, not part of this plan: extending `railwayFetch` to accept a `method` arg is nice-to-have but non-blocking. Defer until a second endpoint needs DELETE.)*

- [ ] **Step 5: Create history route**

```typescript
// frontend/src/app/api/swing/universe/history/route.ts
import { NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export async function GET() {
  try {
    const response = await railwayFetch("/api/swing/universe/history")
    const data = await response.json()
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status })
  }
}
```

- [ ] **Step 6: Verify build**

```bash
cd frontend && npm run build
```

Expected: all 4 routes compile. No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/api/swing/
git commit -m "feat(swing): add Next.js API proxy routes for universe management"
```

---

## Task 11: `useSwingUniverse` hook

**Files:**
- Create: `frontend/src/hooks/use-swing-universe.ts`

- [ ] **Step 1: Study existing hook pattern**

```bash
head -60 frontend/src/hooks/use-momentum-scan.ts
```

Match the pattern: SWR-style, sessionStorage persistence optional, manual trigger + refetch.

- [ ] **Step 2: Implement hook**

```typescript
// frontend/src/hooks/use-swing-universe.ts
"use client"

import { useCallback, useEffect, useState } from "react"
import type {
  SwingUniverseListResponse,
  SwingUniverseTicker,
  SwingUniverseUploadResponse,
} from "@/lib/types"

interface UseSwingUniverseReturn {
  tickers: SwingUniverseTicker[]
  sourceSummary: Record<string, number>
  activeCount: number
  latestBatchAt: string | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  addTicker: (ticker: string) => Promise<void>
  removeTicker: (ticker: string) => Promise<void>
  uploadCsv: (file: File, mode: "replace" | "add") => Promise<SwingUniverseUploadResponse>
}

export function useSwingUniverse(): UseSwingUniverseReturn {
  const [tickers, setTickers] = useState<SwingUniverseTicker[]>([])
  const [sourceSummary, setSourceSummary] = useState<Record<string, number>>({})
  const [activeCount, setActiveCount] = useState(0)
  const [latestBatchAt, setLatestBatchAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/swing/universe", { cache: "no-store" })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: SwingUniverseListResponse = await res.json()
      setTickers(data.tickers)
      setSourceSummary(data.source_summary)
      setActiveCount(data.active_count)
      setLatestBatchAt(data.latest_batch_at)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load universe")
    } finally {
      setLoading(false)
    }
  }, [])

  const addTicker = useCallback(async (ticker: string) => {
    const res = await fetch("/api/swing/universe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    await refresh()
  }, [refresh])

  const removeTicker = useCallback(async (ticker: string) => {
    const res = await fetch(`/api/swing/universe/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    await refresh()
  }, [refresh])

  const uploadCsv = useCallback(async (file: File, mode: "replace" | "add"): Promise<SwingUniverseUploadResponse> => {
    const form = new FormData()
    form.append("file", file)
    form.append("mode", mode)
    const res = await fetch("/api/swing/universe/upload", { method: "POST", body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    const data: SwingUniverseUploadResponse = await res.json()
    await refresh()
    return data
  }, [refresh])

  useEffect(() => { void refresh() }, [refresh])

  return { tickers, sourceSummary, activeCount, latestBatchAt, loading, error, refresh, addTicker, removeTicker, uploadCsv }
}
```

- [ ] **Step 3: Verify compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-swing-universe.ts
git commit -m "feat(swing): add useSwingUniverse hook"
```

---

## Task 12: Universe manager components

**Files:**
- Create: `frontend/src/components/swing/universe-manager.tsx`
- Create: `frontend/src/components/swing/universe-upload-modal.tsx`
- Create: `frontend/src/components/swing/universe-history-panel.tsx`

- [ ] **Step 0: Install missing shadcn components**

Verify which shadcn UI primitives already exist in `frontend/src/components/ui/`:

```bash
ls frontend/src/components/ui/ | grep -iE "radio|dialog|label|skeleton|badge"
```

If `radio-group.tsx` is absent, install it:

```bash
cd frontend && npx shadcn@latest add radio-group
```

Verify `@radix-ui/react-radio-group` is added to `frontend/package.json`, then commit:

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/components/ui/radio-group.tsx
git commit -m "chore: install shadcn radio-group for swing universe upload"
```

Same check for `dialog.tsx`, `label.tsx`, `skeleton.tsx`, `badge.tsx` — install any missing.

- [ ] **Step 1: Implement UniverseUploadModal**

```typescript
// frontend/src/components/swing/universe-upload-modal.tsx
"use client"

import { useState } from "react"
import { Upload, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

interface Props {
  onUpload: (file: File, mode: "replace" | "add") => Promise<{ tickers_added: number; tickers_removed: number; total_active: number }>
}

export function UniverseUploadModal({ onUpload }: Props) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<"replace" | "add">("add")
  const [busy, setBusy] = useState(false)

  async function handleUpload() {
    if (!file) return
    setBusy(true)
    try {
      const r = await onUpload(file, mode)
      toast.success(`Added ${r.tickers_added}, removed ${r.tickers_removed}. Active: ${r.total_active}`)
      setOpen(false)
      setFile(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-8 text-xs"><Upload className="mr-1.5 size-3.5" /> Upload CSV</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Upload Deepvue Universe</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">CSV file</Label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-xs"
            />
            {file && <p className="text-[10px] text-muted-foreground">{file.name} ({file.size} bytes)</p>}
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Mode</Label>
            <RadioGroup value={mode} onValueChange={(v) => setMode(v as "replace" | "add")}>
              <div className="flex items-center gap-2"><RadioGroupItem value="add" id="add" /><Label htmlFor="add" className="text-xs">Add (merge with existing)</Label></div>
              <div className="flex items-center gap-2"><RadioGroupItem value="replace" id="replace" /><Label htmlFor="replace" className="text-xs">Replace (soft-delete old deepvue rows)</Label></div>
            </RadioGroup>
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
            <Button size="sm" onClick={handleUpload} disabled={!file || busy}>
              {busy ? <><Loader2 className="mr-1.5 size-3 animate-spin" /> Uploading</> : "Upload"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Implement UniverseHistoryPanel**

```typescript
// frontend/src/components/swing/universe-history-panel.tsx
"use client"

import { useEffect, useState } from "react"
import type { SwingUniverseHistoryEntry } from "@/lib/types"

export function UniverseHistoryPanel() {
  const [batches, setBatches] = useState<SwingUniverseHistoryEntry[]>([])
  useEffect(() => {
    void fetch("/api/swing/universe/history", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setBatches(d.batches || []))
      .catch(() => setBatches([]))
  }, [])
  if (batches.length === 0) return <p className="text-xs text-muted-foreground">No batches yet.</p>
  return (
    <div className="space-y-1.5">
      {batches.map((b) => (
        <div key={b.batch_id} className="flex justify-between text-xs border-b border-border/30 pb-1">
          <span className="font-mono">{new Date(b.uploaded_at).toLocaleString()}</span>
          <span>{b.source}</span>
          <span>{b.ticker_count} tickers</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Implement UniverseManager (main component)**

```typescript
// frontend/src/components/swing/universe-manager.tsx
"use client"

import { useState } from "react"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { UniverseUploadModal } from "./universe-upload-modal"
import { UniverseHistoryPanel } from "./universe-history-panel"
import { useSwingUniverse } from "@/hooks/use-swing-universe"

export function UniverseManager() {
  const { tickers, sourceSummary, activeCount, latestBatchAt, loading, error, refresh, addTicker, removeTicker, uploadCsv } = useSwingUniverse()
  const [newTicker, setNewTicker] = useState("")
  const [filter, setFilter] = useState("")
  const [showHistory, setShowHistory] = useState(false)

  const filtered = tickers.filter((t) => !filter || t.ticker.includes(filter.toUpperCase()))

  async function handleAdd() {
    const t = newTicker.trim().toUpperCase()
    if (!t) return
    try { await addTicker(t); setNewTicker(""); toast.success(`Added ${t}`) }
    catch (e) { toast.error(e instanceof Error ? e.message : "Add failed") }
  }

  async function handleRemove(ticker: string) {
    try { await removeTicker(ticker); toast.success(`Removed ${ticker}`) }
    catch (e) { toast.error(e instanceof Error ? e.message : "Remove failed") }
  }

  const freshness = latestBatchAt ? Math.floor((Date.now() - new Date(latestBatchAt).getTime()) / (1000 * 60 * 60 * 24)) : null
  const freshnessLabel = freshness === null ? "no uploads yet" : freshness <= 7 ? `✓ ${freshness}d ago` : `⚠ ${freshness}d ago (stale)`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium">Universe — {activeCount} active tickers</p>
          <p className="text-[10px] text-muted-foreground">Latest upload: {freshnessLabel}</p>
        </div>
        <div className="flex gap-1.5">
          <Button size="sm" variant="ghost" className="h-8" onClick={refresh} disabled={loading}>
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <UniverseUploadModal onUpload={uploadCsv} />
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setShowHistory((s) => !s)}>
            History
          </Button>
        </div>
      </div>

      {/* Source badges */}
      <div className="flex gap-1.5 flex-wrap">
        {Object.entries(sourceSummary).map(([src, n]) => (
          <Badge key={src} variant="outline" className="text-[10px]">{src}: {n}</Badge>
        ))}
      </div>

      {showHistory && (
        <div className="rounded border border-border/40 p-3 bg-card/30">
          <UniverseHistoryPanel />
        </div>
      )}

      {/* Add ticker + filter */}
      <div className="flex gap-2">
        <Input value={newTicker} onChange={(e) => setNewTicker(e.target.value)} placeholder="Add ticker..." className="h-8 text-xs w-32" onKeyDown={(e) => { if (e.key === "Enter") void handleAdd() }} />
        <Button size="sm" className="h-8" onClick={handleAdd} disabled={!newTicker.trim()}><Plus className="size-3.5" /></Button>
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter..." className="h-8 text-xs flex-1" />
      </div>

      {/* Error */}
      {error && <p className="text-xs text-red-400">{error}</p>}

      {/* Ticker list */}
      {loading && tickers.length === 0 ? (
        <div className="space-y-1"><Skeleton className="h-6" /><Skeleton className="h-6" /><Skeleton className="h-6" /></div>
      ) : (
        <div className="rounded border border-border/40 divide-y divide-border/30">
          {filtered.length === 0 ? (
            <p className="text-xs text-muted-foreground p-4 text-center">No tickers.</p>
          ) : filtered.slice(0, 500).map((t) => (
            <div key={t.ticker} className="flex items-center justify-between px-3 py-1.5 text-xs">
              <div className="flex gap-3 items-center">
                <span className="font-mono font-medium">{t.ticker}</span>
                <Badge variant="outline" className="text-[9px]">{t.source}</Badge>
              </div>
              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => handleRemove(t.ticker)}>
                <Trash2 className="size-3" />
              </Button>
            </div>
          ))}
          {filtered.length > 500 && <p className="text-[10px] text-muted-foreground p-2 text-center">+{filtered.length - 500} more (filter to narrow)</p>}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verify compile**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/swing/
git commit -m "feat(swing): add universe manager components (list, upload modal, history panel)"
```

---

## Task 13: `/swing-ideas` page shell with tabs

**Files:**
- Create: `frontend/src/app/swing-ideas/page.tsx`

- [ ] **Step 1: Implement tabbed page**

```typescript
// frontend/src/app/swing-ideas/page.tsx
"use client"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UniverseManager } from "@/components/swing/universe-manager"

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-8 text-center">
      <p className="text-sm text-muted-foreground">{name} — coming in a later plan</p>
    </div>
  )
}

export default function SwingIdeasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Swing Ideas</h1>
        <p className="text-xs text-muted-foreground">Kell + Saty unified swing setups — detection, analysis, tracking</p>
      </div>

      <Tabs defaultValue="universe" className="space-y-4">
        <TabsList>
          <TabsTrigger value="active" disabled>Active <Badge variant="outline" className="ml-1 text-[9px]">Plan 2</Badge></TabsTrigger>
          <TabsTrigger value="watching" disabled>Watching <Badge variant="outline" className="ml-1 text-[9px]">Plan 2</Badge></TabsTrigger>
          <TabsTrigger value="exited" disabled>Exited <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
          <TabsTrigger value="universe">Universe</TabsTrigger>
          <TabsTrigger value="model-book" disabled>Model Book <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
          <TabsTrigger value="weekly" disabled>Weekly <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
        </TabsList>

        <TabsContent value="active"><ComingSoon name="Active ideas" /></TabsContent>
        <TabsContent value="watching"><ComingSoon name="Watching" /></TabsContent>
        <TabsContent value="exited"><ComingSoon name="Exited" /></TabsContent>
        <TabsContent value="universe"><UniverseManager /></TabsContent>
        <TabsContent value="model-book"><ComingSoon name="Model Book" /></TabsContent>
        <TabsContent value="weekly"><ComingSoon name="Weekly Synthesis" /></TabsContent>
      </Tabs>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: `/swing-ideas` appears in route list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/swing-ideas/
git commit -m "feat(swing): add /swing-ideas page shell with Universe tab"
```

---

## Task 14: Add Swing Ideas to sidebar

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx`

- [ ] **Step 1: Inspect existing nav config**

```bash
grep -n "Screener\|Ideas\|navItems" frontend/src/components/layout/sidebar.tsx | head -10
```

- [ ] **Step 2: Add Swing Ideas between Screener and Ideas**

```typescript
// inside navItems array:
  { label: "Swing Ideas", href: "/swing-ideas", icon: Activity, badge: "New" },
```

Import `Activity` from `lucide-react` if not already imported.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx
git commit -m "feat(swing): add Swing Ideas to sidebar nav"
```

---

## Task 15: End-to-end manual verification

- [ ] **Step 1: Start backend**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8080
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Click through the UI**

Navigate to `http://localhost:3000/swing-ideas`. Verify:
1. Six tabs render — Universe active, others disabled with "Plan 2/4" badges.
2. Universe tab: `0 active tickers` initially. Source badges empty. No error.
3. Type `AAPL` in add-ticker field, press Enter → `Added AAPL` toast; list updates to 1 active; `manual: 1` badge appears.
4. Click History button → history panel shows one entry with today's date and 1 ticker.
5. Create a test CSV:
   ```
   ticker,revenue_growth
   NVDA,0.78
   CRWD,0.39
   ```
   Upload with mode=Add → toast shows `Added 2, removed 0. Active: 3`.
6. Filter: type `NV` → only NVDA shown.
7. Click trash on NVDA → `Removed NVDA` toast; count drops to 2.
8. Refresh page → state persists from DB.
9. Upload same CSV again with mode=Replace → `Added 2, removed 2. Active: 3` (AAPL survives because it's `source=manual`, CSV replace only touches `deepvue-csv` rows).

- [ ] **Step 4: Verify database state**

```bash
venv/bin/python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT ticker, source, removed_at FROM swing_universe ORDER BY added_at DESC LIMIT 20\")
for row in cur.fetchall(): print(row)
"
```

Expected: rows match the expected state from step 3.

- [ ] **Step 5: Run full test suite**

```bash
venv/bin/pytest tests/swing/ -v
cd frontend && npx tsc --noEmit && npm run lint
```

Expected: all backend tests pass; no TS/lint errors.

- [ ] **Step 6: Final commit if needed**

```bash
git add -A
git status
git commit -m "chore(swing): Plan 1 verification pass" || true
```

---

## Task 16: Push

- [ ] **Step 1: Push branch (do NOT push to main without user approval)**

```bash
git log --oneline -20
# Confirm only Plan 1 commits
```

- [ ] **Step 2: Wait for user review before pushing**

Surface to the user: "Plan 1 complete. N commits on branch `<branch>`. Ready to push to `main`?"

Push only after explicit approval:
```bash
git push origin main
```

---

## Definition of Done for Plan 1

- ✅ All 7 swing tables exist in DB with partial unique indexes, check constraints, and FK relationships from the spec.
- ✅ Universe can be managed via `/swing-ideas/Universe` tab: upload CSV, add ticker, remove ticker, view history.
- ✅ Replace vs. Add modes for CSV upload behave correctly.
- ✅ Source badges show `deepvue-csv`, `manual`, `backend-generated` counts.
- ✅ Fresh/stale indicator displays "Xd ago" with warning glyph if > 7 days.
- ✅ Backend generator is callable (but not yet scheduled — Plan 4 schedules it via `weekend-refresh` cron).
- ✅ Resolver returns appropriate source label (`deepvue`, `backend-stale-deepvue`, `backend-fresh`, or `empty`).
- ✅ All tests pass (backend pytest + frontend tsc + lint).
- ✅ End-to-end smoke test through the browser works.
- ✅ No breaking changes to existing `/ideas`, `/screener`, `/scan`, `/trade-plan` pages.

---

## Open Questions to Resolve During Execution

1. **Auth on `/api/swing/universe/*` endpoints.** Spec Section 8 introduces `SWING_API_TOKEN` bearer auth for **Mac → Railway writes** (thesis, snapshots, events). Universe CRUD in Plan 1 flows **user → Next.js proxy → Railway**, which is a different path. Existing endpoints like `/api/breadth/*` and `/api/screener/*` appear unauthenticated today, so Plan 1 follows that pattern and leaves swing endpoints unauthenticated. If security becomes a concern before Plan 3 ships, wrap all `/api/swing/*` routes with the same bearer-token middleware introduced in Plan 3.

2. **Base tickers list size.** Plan ships a ~130-ticker stub. Plan 4's Sunday backend refresh will produce a weak universe if the base list isn't expanded. Add a follow-up task (not blocking Plan 1) to populate `base_tickers.json` from a Russell 3000 ∪ Nasdaq Composite source (e.g., iShares IWV + QQQ holdings CSVs).

3. **Unique-index behavior in tests.** `FakeSupabaseClient.insert` doesn't enforce partial unique indexes. Conflict behavior (`test_add_single_ticker_conflict`) relies on the endpoint's explicit existence check, not the DB constraint. Real Postgres validation happens only in Task 15 manual E2E. Acceptable for Plan 1.

---

## Out of Scope (deferred to Plan 2+)

- Detectors (Wedge Pop, EMA Crossback, etc.) — Plan 2
- Cron dispatcher + Vercel cron consolidation — Plan 2
- Slack digest posting — Plan 2
- Active / Watching / Exited list views + idea detail page — Plans 2 & 4
- Thesis generation + Claude Code skills — Plan 3
- Deep analysis + weekly synthesis + model book + charts — Plan 4
