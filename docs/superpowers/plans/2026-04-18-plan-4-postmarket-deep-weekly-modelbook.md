# Plan 4 — Post-Market + Deep Analysis + Weekly + Model Book Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Reference Plans 1-3 for conventions (singleton Supabase client, `FakeSupabaseClient`, TDD, bearer-token auth, detector contract, pipeline dispatcher).

**Goal:** Close the swing-trading loop by delivering: (1) post-market pipeline with Exhaustion-Extension warnings, (2) Sunday weekend-refresh cron, (3) Mac-side Claude deep analysis with Deepvue screenshots, (4) Sunday weekly synthesis, (5) chart storage/gallery, (6) Model Book CRUD + promotion flow, (7) completed `/swing-ideas` tabs (Exited, Weekly, Model Book), and (8) the full idea-detail page with timeline, actions, and charts.

**Architecture:** Extends Plan 2's `daily-dispatcher` to call a new `/api/swing/pipeline/postmarket` endpoint at 21:00 UTC; adds a second Vercel cron `weekend-refresh` at 23:30 UTC Sunday that triggers `/api/swing/pipeline/universe-refresh`. Claude-side skills (`/swing-deep-analyze`, `/swing-weekly-synth`) use `scheduled-tasks` MCP to fire on the Mac, precheck Chrome+Deepvue+Claude-in-Chrome, capture charts, upload to Vercel Blob via Next.js proxy routes, and POST analysis to Railway endpoints with bearer-token auth from Plan 3. Frontend completes `/swing-ideas` with Active/Watching/Exited/Weekly/Model Book tabs and fills out `/swing-ideas/[id]` with timeline, events, charts, and actions.

**Tech Stack:** Python 3.12, FastAPI, pandas, pytest (backend). Next.js 16 App Router, React 19, Tailwind 4, shadcn/ui, SWR, Sonner (frontend). `@vercel/blob` for chart storage. Claude-in-Chrome MCP + `scheduled-tasks` MCP on Mac. Slack Web API via existing multi-channel router.

**Reference:**
- Spec: [docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md](../specs/2026-04-18-kell-saty-swing-system-design.md) — §6.5 Exhaustion Extension, §8 Claude on Mac layer, §9 [C]/[D]/[E]/[F] pipelines, §10 frontend.
- Kell source: [docs/kell/source-notes.md](../../kell/source-notes.md) — §11 Exhaustion Extension rules.
- Plan 1: [docs/superpowers/plans/2026-04-18-plan-1-foundation-universe.md](./2026-04-18-plan-1-foundation-universe.md) — conventions (`_get_supabase()`, `FakeSupabaseClient`, migration 016, `/swing-ideas` shell).
- Plan 2: [docs/superpowers/plans/2026-04-18-plan-2-detection-pipeline.md](./2026-04-18-plan-2-detection-pipeline.md) — detectors, `daily-dispatcher`, common indicator helpers under `api/indicators/common/`.
- Plan 3: [docs/superpowers/plans/2026-04-18-plan-3-claude-analysis-layer.md](./2026-04-18-plan-3-claude-analysis-layer.md) — bearer-token auth, thesis/events endpoints, idea detail shell, `/swing-analyze-pending` pattern. **If Plan 3 is not yet merged at execution time, assume it delivers: `POST /api/swing/ideas/<id>/thesis`, `POST /api/swing/ideas/<id>/events`, auth header `Authorization: Bearer $SWING_API_TOKEN`, skill-template conventions in `.claude/skills/`.**

---

## File Structure (created/modified by this plan)

**Backend — new:**
- `api/indicators/swing/setups/exhaustion_extension.py` — warning-only detector for active ideas
- `api/indicators/swing/pipeline/postmarket.py` — post-market snapshot + exhaustion scan + stop-check
- `api/indicators/swing/pipeline/universe_refresh.py` — Sunday wrapper around Plan 1's `generate_backend_universe()`
- `api/indicators/swing/pipeline/weekly_retrospective.py` — helper for retrospective + theme clustering inputs (consumed by Mac)
- `api/endpoints/swing_postmarket.py` — `POST /api/swing/pipeline/postmarket`, `POST /api/swing/pipeline/universe-refresh`
- `api/endpoints/swing_snapshots.py` — `POST /api/swing/ideas/<id>/snapshots` (both Railway-native and Mac-populated updates)
- `api/endpoints/swing_charts.py` — chart multipart upload + listing + attaching to events/model-book
- `api/endpoints/swing_model_book.py` — list/get/create/patch/delete
- `api/endpoints/swing_blob.py` — `POST /api/swing/blob/upload-token` (returns a short-lived Blob upload URL)

**Backend — tests:**
- `tests/swing/test_exhaustion_extension.py`
- `tests/swing/test_postmarket_pipeline.py`
- `tests/swing/test_universe_refresh_endpoint.py`
- `tests/swing/test_snapshots_endpoint.py`
- `tests/swing/test_charts_endpoint.py`
- `tests/swing/test_model_book_endpoint.py`

**Backend — modified:**
- `api/indicators/swing/pipeline/dispatcher.py` (from Plan 2) — wire 21:00 UTC branch to call `run_swing_postmarket_snapshot()`
- `api/schemas/swing.py` — Pydantic request/response models for snapshots, charts, model book, postmarket result
- `api/main.py` — register new routers (swing_postmarket, swing_snapshots, swing_charts, swing_model_book, swing_blob)
- `api/indicators/swing/pipeline/slack.py` (from Plan 2) — add `post_postmarket_digest()` + `post_weekend_refresh_digest()` helpers

**Frontend — new (cron handlers):**
- `frontend/src/app/api/cron/weekend-refresh/route.ts` — Sunday 23:30 UTC cron → Railway universe-refresh endpoint
- `frontend/vercel.json` — add the `weekend-refresh` cron entry (second cron, joining `daily-dispatcher` from Plan 2)

**Frontend — new (proxy routes):**
- `frontend/src/app/api/swing/ideas/[id]/snapshots/route.ts` — GET list, POST append (Mac-side)
- `frontend/src/app/api/swing/ideas/[id]/events/route.ts` — GET list, POST append
- `frontend/src/app/api/swing/ideas/[id]/charts/route.ts` — GET list, POST multipart → Vercel Blob → Railway
- `frontend/src/app/api/swing/events/[id]/charts/route.ts` — attach chart to event
- `frontend/src/app/api/swing/model-book/charts/route.ts` — attach chart to model-book entry
- `frontend/src/app/api/swing/model-book/route.ts` — GET list, POST create
- `frontend/src/app/api/swing/model-book/[id]/route.ts` — GET, PATCH, DELETE
- `frontend/src/app/api/swing/weekly/route.ts` — GET weekly syntheses archive

**Frontend — new (pages, components, hooks):**
- `frontend/src/app/swing-ideas/model-book/[id]/page.tsx` — model-book detail page
- `frontend/src/components/swing/exited-list.tsx`
- `frontend/src/components/swing/weekly-list.tsx`
- `frontend/src/components/swing/model-book-grid.tsx`
- `frontend/src/components/swing/model-book-card.tsx`
- `frontend/src/components/swing/model-book-form.tsx` — create/edit narrative+takeaways
- `frontend/src/components/swing/idea-timeline.tsx` — event feed
- `frontend/src/components/swing/chart-gallery.tsx` — tabs daily/weekly/60m/uploads/annotated + lightbox
- `frontend/src/components/swing/chart-upload-dropzone.tsx` — drag-and-drop
- `frontend/src/components/swing/idea-actions.tsx` — Add Note / Upload Chart / Record Trade / Mark Invalidated / Promote to Model Book buttons
- `frontend/src/components/swing/note-dialog.tsx`
- `frontend/src/components/swing/invalidate-dialog.tsx`
- `frontend/src/components/swing/promote-model-book-dialog.tsx`
- `frontend/src/hooks/use-swing-events.ts`
- `frontend/src/hooks/use-swing-snapshots.ts`
- `frontend/src/hooks/use-swing-charts.ts`
- `frontend/src/hooks/use-swing-model-book.ts`
- `frontend/src/hooks/use-swing-weekly.ts`

**Frontend — modified:**
- `frontend/src/app/swing-ideas/page.tsx` (from Plan 1) — replace "Coming Soon" placeholders for Exited, Weekly, Model Book tabs
- `frontend/src/app/swing-ideas/[id]/page.tsx` (from Plan 3) — add Timeline, Charts, Fundamentals, Actions sections
- `frontend/src/lib/swing-types.ts` (from Plan 1) — add `SwingEvent`, `SwingSnapshot`, `SwingChart`, `SwingModelBookEntry`, `SwingWeekly` types
- `frontend/package.json` — add `@vercel/blob` dependency

**Mac-side (Claude Code skills) — new:**
- `.claude/skills/swing-deep-analyze.md` — 2:30pm PT, top-10 active ideas via Claude-in-Chrome on Deepvue
- `.claude/skills/swing-weekly-synth.md` — Sunday 5pm PT weekly synthesis
- `.claude/skills/swing-model-book-add.md` — manual historical model-book entry

---

## Cross-cutting conventions (Plan 4)

1. **Supabase access**: reuse the module-level `_get_supabase()` singleton pattern from Plan 1. Each new endpoints module gets its own `_get_supabase()` helper (copy-paste is fine — matches Plan 2/3). Tests monkey-patch the module's `_get_supabase`.
2. **Bearer token**: every write endpoint added in Plan 4 is protected by Plan 3's `require_swing_token()` dependency. Read endpoints (GET) are open for Next.js proxy — the proxy itself doesn't forward bearer tokens.
3. **Idempotency**: writes that may be retried (snapshot upsert, event append, postmarket run) accept an optional `Idempotency-Key` header. 24h TTL handled by a small Supabase `swing_idempotency` row or by using the natural key `UNIQUE(idea_id, snapshot_date, snapshot_type)` (for snapshots) — prefer natural keys where possible.
4. **Python env**: all commands use `.venv/bin/python`. Tests run with `.venv/bin/python -m pytest tests/swing/ -v`.
5. **TDD**: every task writes a failing test first, implements, then commits. One commit per task unless a task explicitly has multiple sub-commits.
6. **No Claude SDK on Railway**: before committing each backend task, confirm `grep -R "^from anthropic\|^import anthropic" api/ | grep -v tests/ | wc -l` returns `0`.
7. **Computer-use is on-demand**: the `/swing-deep-analyze` skill must fail **gracefully** (Slack message + abort) if Chrome is not running, Deepvue tab is not open, or Claude-in-Chrome MCP is not connected. Never silently retry.
8. **Vercel Blob**: use `@vercel/blob` client-side `put()` with a server-generated token from `POST /api/swing/blob/upload-token`. Env var `BLOB_READ_WRITE_TOKEN` on Vercel (Next.js side). The Python Railway side never talks to Blob directly — it only receives URLs.
9. **Cron count**: we finish Plan 4 with **exactly 2 Vercel crons** — `daily-dispatcher` (Plan 2) and `weekend-refresh` (this plan). If a third cron is considered, revisit the consolidation tradeoff in spec §9.
10. **Slack routing**: post-market + weekend-refresh digests route to `#swing-alerts` via existing multi-channel router (same channel Plan 2 uses for pre-market).
11. **Time zones**: all cron/dispatcher logic uses UTC. The hour-branch in `daily-dispatcher` is `hour == 21` for post-market.
12. **Chart table FK rule**: from Plan 1 migration, `swing_charts` has a CHECK constraint `num_nonnulls(idea_id, event_id, model_book_id) = 1`. Endpoints must enforce this before INSERT (return 400 on violation).

---

## Task 1: Exhaustion Extension detector (warning-only) — TDD

**Why first**: post-market pipeline (Task 3) depends on this detector.

**Files:**
- Create: `api/indicators/swing/setups/exhaustion_extension.py`
- Create: `tests/swing/test_exhaustion_extension.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_exhaustion_extension.py
import pandas as pd
import pytest

from api.indicators.swing.setups.exhaustion_extension import (
    detect_exhaustion_extension,
    ExhaustionFlag,
)


def _bars(closes, volumes=None, highs=None, lows=None, opens=None):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": opens or [c * 0.995 for c in closes],
        "high": highs or [c * 1.01 for c in closes],
        "low": lows or [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes or [1_000_000] * n,
    })


def test_no_warning_when_price_normal():
    # Price glued to its 10-EMA, normal volume → no triggers
    closes = [100.0 + i * 0.1 for i in range(60)]
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=20)
    assert flags == ExhaustionFlag(kell_2nd_extension=False, climax_bar=False,
                                    far_above_10ema=False, weekly_air=False)


def test_kell_2nd_extension_triggers():
    # Two separate pokes > 1 ATR above 10-EMA since base breakout (idx 20)
    closes = [100.0] * 20 + [115.0, 108.0, 104.0, 102.0] + [103.0] * 10 + [120.0] + [104.0] * 25
    df = _bars(closes, volumes=[1_000_000] * 60)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=20)
    assert flags.kell_2nd_extension is True


def test_climax_bar_triggers_on_volume_and_upper_wick():
    closes = [100.0] * 40 + [100.0 + i for i in range(20)]     # trending up
    volumes = [1_000_000] * 59 + [3_000_000]                    # 3x surge on last bar
    highs = [c * 1.01 for c in closes[:59]] + [closes[-1] * 1.05]  # big upper wick
    lows = [c * 0.99 for c in closes[:59]] + [closes[-1] * 0.995]
    df = _bars(closes, volumes=volumes, highs=highs, lows=lows)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=40)
    assert flags.climax_bar is True


def test_heuristic_far_above_10ema():
    closes = [100.0] * 50 + [200.0]                            # massive gap above any 10-EMA
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=10)
    assert flags.far_above_10ema is True


def test_missing_base_breakout_idx_skips_kell_count():
    # When there's no recorded base breakout, Kell 2nd-extension is not counted,
    # but heuristics still run.
    closes = [100.0 + i * 0.1 for i in range(60)]
    df = _bars(closes)
    flags = detect_exhaustion_extension(df, last_base_breakout_idx=None)
    assert flags.kell_2nd_extension is False
```

- [ ] **Step 2: Run — expect ImportError**

```bash
.venv/bin/python -m pytest tests/swing/test_exhaustion_extension.py -v
```

- [ ] **Step 3: Implement the detector**

```python
# api/indicators/swing/setups/exhaustion_extension.py
"""Exhaustion Extension detector — warning-only, runs in post-market pipeline.

Unlike the 5 detection-oriented setups in Plan 2, this does not create new ideas.
It flags risk on existing active ideas (status in 'watching'|'triggered'|'adding'|'trailing').

Triggers (spec §6.5, Kell source-notes §11):
  - Kell-direct: >= 2 extensions from 10-EMA since last base breakout (primary)
  - Kell-direct: climax volume (>= 2x avg 20d) + upper wick > 50% of day's range
  - Heuristic: close > 2 ATRs above 10-EMA
  - Heuristic: weekly close > 15% above 10-WSMA (caller feeds weekly df separately)

`last_base_breakout_idx` is the 0-based row index in `df` of the most recent
Base-n-Break detection (from `swing_events` history) — or None if none recorded.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from api.indicators.common.moving_averages import ema
from api.indicators.common.atr import atr


EXTENSION_ATR_THRESHOLD = 1.0      # "an extension" = close > 10-EMA + 1 ATR
FAR_ABOVE_ATR_MULT = 2.0           # heuristic: > 2 ATR above 10-EMA
CLIMAX_VOL_MULT = 2.0              # >= 2x avg 20d volume
CLIMAX_WICK_FRAC = 0.50            # upper wick > 50% of day's range
WEEKLY_AIR_PCT = 0.15              # close > 15% above weekly 10-SMA


@dataclass
class ExhaustionFlag:
    kell_2nd_extension: bool = False
    climax_bar: bool = False
    far_above_10ema: bool = False
    weekly_air: bool = False

    def any(self) -> bool:
        return any([self.kell_2nd_extension, self.climax_bar,
                    self.far_above_10ema, self.weekly_air])


def detect_exhaustion_extension(
    daily: pd.DataFrame,
    last_base_breakout_idx: int | None,
    weekly: pd.DataFrame | None = None,
) -> ExhaustionFlag:
    """Evaluate exhaustion triggers on the most recent daily bar.

    `daily` must have columns: open, high, low, close, volume (date index or column).
    """
    flag = ExhaustionFlag()
    if daily is None or len(daily) < 20:
        return flag

    ema10 = ema(daily["close"], 10)
    atr14 = atr(daily["high"], daily["low"], daily["close"], 14)
    last_close = float(daily["close"].iloc[-1])
    last_ema = float(ema10.iloc[-1])
    last_atr = float(atr14.iloc[-1])

    # Heuristic: far above 10-EMA (always check)
    if last_atr > 0 and (last_close - last_ema) > FAR_ABOVE_ATR_MULT * last_atr:
        flag.far_above_10ema = True

    # Climax bar: volume + upper wick
    last_vol = float(daily["volume"].iloc[-1])
    avg_vol = float(daily["volume"].tail(20).mean())
    last_high = float(daily["high"].iloc[-1])
    last_low = float(daily["low"].iloc[-1])
    rng = last_high - last_low
    if rng > 0 and avg_vol > 0:
        upper_wick = last_high - max(last_close, float(daily["open"].iloc[-1]))
        if last_vol >= CLIMAX_VOL_MULT * avg_vol and upper_wick / rng >= CLIMAX_WICK_FRAC:
            flag.climax_bar = True

    # Kell 2nd+ extension: count closes that poked > 1 ATR above 10-EMA since breakout
    if last_base_breakout_idx is not None and last_base_breakout_idx < len(daily) - 1:
        post = daily.iloc[last_base_breakout_idx + 1:]
        post_ema = ema10.iloc[last_base_breakout_idx + 1:]
        post_atr = atr14.iloc[last_base_breakout_idx + 1:]
        extension_count = 0
        in_extension = False
        for close_i, ema_i, atr_i in zip(post["close"], post_ema, post_atr):
            if atr_i <= 0:
                continue
            is_ext = (close_i - ema_i) > EXTENSION_ATR_THRESHOLD * atr_i
            if is_ext and not in_extension:
                extension_count += 1
                in_extension = True
            elif not is_ext:
                in_extension = False
        if extension_count >= 2:
            flag.kell_2nd_extension = True

    # Weekly Air (heuristic)
    if weekly is not None and len(weekly) >= 10:
        wsma10 = weekly["close"].tail(10).mean()
        last_weekly_close = float(weekly["close"].iloc[-1])
        if wsma10 > 0 and (last_weekly_close - wsma10) / wsma10 > WEEKLY_AIR_PCT:
            flag.weekly_air = True

    return flag
```

- [ ] **Step 4: Run — expect pass**

```bash
.venv/bin/python -m pytest tests/swing/test_exhaustion_extension.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/indicators/swing/setups/exhaustion_extension.py tests/swing/test_exhaustion_extension.py
git commit -m "feat(swing): add exhaustion extension warning detector"
```

---

## Task 2: Pydantic schemas for postmarket / snapshots / charts / model book

**Files:**
- Modify: `api/schemas/swing.py`

- [ ] **Step 1: Append new models**

```python
# api/schemas/swing.py — append

from datetime import date
from typing import Literal


class SnapshotCreateRequest(BaseModel):
    snapshot_date: date
    snapshot_type: Literal["daily", "weekly"] = "daily"
    # Railway-populated (optional on Mac-side POST; required on Railway-internal upsert)
    daily_close: float | None = None
    daily_high: float | None = None
    daily_low: float | None = None
    daily_volume: int | None = None
    ema_10: float | None = None
    ema_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    weekly_ema_10: float | None = None
    rs_vs_qqq_20d: float | None = None
    phase_osc_value: float | None = None
    kell_stage: str | None = None
    saty_setups_active: list[str] | None = None
    # Mac-populated
    claude_analysis: str | None = None
    claude_model: str | None = None
    analysis_sources: dict[str, Any] | None = None
    deepvue_panel: dict[str, Any] | None = None
    chart_daily_url: str | None = None
    chart_weekly_url: str | None = None
    chart_60m_url: str | None = None


class SnapshotResponse(SnapshotCreateRequest):
    id: int
    idea_id: UUID


class EventCreateRequest(BaseModel):
    event_type: Literal[
        "stage_transition", "thesis_updated", "setup_fired", "invalidation",
        "earnings", "exhaustion_warning", "user_note", "chart_uploaded",
        "trade_recorded", "promoted_to_model_book",
    ]
    payload: dict[str, Any] | None = None
    summary: str | None = None


class EventResponse(BaseModel):
    id: int
    idea_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any] | None
    summary: str | None


class ChartCreateRequest(BaseModel):
    image_url: str
    thumbnail_url: str | None = None
    timeframe: Literal["daily", "weekly", "60m", "annotated"]
    source: Literal["deepvue-auto", "tradingview-upload", "user-markup", "claude-annotated"]
    annotations: dict[str, Any] | None = None
    caption: str | None = None
    # Exactly one must be set (enforced server-side and by DB CHECK):
    idea_id: UUID | None = None
    event_id: int | None = None
    model_book_id: UUID | None = None


class ChartResponse(ChartCreateRequest):
    id: UUID
    captured_at: datetime


class ModelBookCreateRequest(BaseModel):
    title: str
    ticker: str
    setup_kell: str
    outcome: Literal["winner", "loser", "example", "missed"]
    entry_date: date | None = None
    exit_date: date | None = None
    r_multiple: float | None = None
    source_idea_id: UUID | None = None
    ticker_fundamentals: dict[str, Any] | None = None
    narrative: str | None = None
    key_takeaways: list[str] | None = None
    tags: list[str] | None = None


class ModelBookPatchRequest(BaseModel):
    narrative: str | None = None
    key_takeaways: list[str] | None = None
    tags: list[str] | None = None
    outcome: Literal["winner", "loser", "example", "missed"] | None = None


class ModelBookResponse(ModelBookCreateRequest):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PostmarketRunResponse(BaseModel):
    ran_at: datetime
    active_ideas_processed: int
    stage_transitions: int
    exhaustion_warnings: int
    stop_violations: int
    snapshots_written: int


class UniverseRefreshResponse(BaseModel):
    ran_at: datetime
    skipped: bool
    skip_reason: str | None = None
    base_count: int | None = None
    final_count: int | None = None
    batch_id: UUID | None = None
```

- [ ] **Step 2: Verify import**

```bash
.venv/bin/python -c "from api.schemas.swing import PostmarketRunResponse, SnapshotCreateRequest, ChartCreateRequest, ModelBookCreateRequest; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add api/schemas/swing.py
git commit -m "feat(swing): add Pydantic schemas for postmarket, snapshots, charts, model book"
```

---

## Task 3: Post-market pipeline core — `run_swing_postmarket_snapshot()`

**Files:**
- Create: `api/indicators/swing/pipeline/postmarket.py`
- Create: `tests/swing/test_postmarket_pipeline.py`

The pipeline iterates active ideas (`status NOT IN ('exited','invalidated')`), fetches today's daily bar, recomputes indicators, checks for stage transitions (using the same stage-detection logic Plan 2 uses in pre-market — import and reuse), checks stop violation, runs exhaustion detector, upserts snapshot rows, writes events, posts Slack digest.

- [ ] **Step 1: Write failing test (happy path — one idea, no transitions, no exhaustion)**

```python
# tests/swing/test_postmarket_pipeline.py
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from api.indicators.swing.pipeline import postmarket as pm
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def _idea(id_="aaaa-1", ticker="NVDA", status="triggered", stop_price=100.0, stage="base_n_break"):
    return {
        "id": id_, "ticker": ticker, "status": status, "cycle_stage": stage,
        "stop_price": stop_price, "entry_zone_low": 110.0, "entry_zone_high": 112.0,
        "first_target": 130.0, "second_target": 150.0,
        "setup_kell": "base_n_break", "direction": "long",
        "risk_flags": {},
    }


def _bars(closes, volumes=None):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": [c * 0.995 for c in closes],
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes or [1_000_000] * n,
    })


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_writes_snapshot_and_no_exhaustion(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    mock_bars.return_value = _bars([100.0 + i * 0.1 for i in range(60)])

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.active_ideas_processed == 1
    assert result.stop_violations == 0
    assert result.exhaustion_warnings == 0
    assert result.snapshots_written == 1
    snaps = sb.table("swing_idea_snapshots").rows
    assert len(snaps) == 1
    assert snaps[0]["idea_id"] == "aaaa-1"


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_detects_stop_violation(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea(stop_price=150.0)])  # stop well above price
    mock_bars.return_value = _bars([100.0] * 60)               # close = 100, stop = 150

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.stop_violations == 1
    ideas = sb.table("swing_ideas").rows
    assert ideas[0]["status"] == "invalidated"
    assert ideas[0]["invalidated_reason"].startswith("stop")
    events = sb.table("swing_events").rows
    assert any(e["event_type"] == "invalidation" for e in events)


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_writes_exhaustion_warning(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    # Construct bars that trigger far_above_10ema
    mock_bars.return_value = _bars([100.0] * 50 + [200.0])

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.exhaustion_warnings == 1
    ideas = sb.table("swing_ideas").rows
    assert ideas[0]["risk_flags"].get("far_above_10ema") is True
    events = sb.table("swing_events").rows
    assert any(e["event_type"] == "exhaustion_warning" for e in events)


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_is_idempotent(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    mock_bars.return_value = _bars([100.0 + i * 0.1 for i in range(60)])

    pm.run_swing_postmarket_snapshot(sb)
    pm.run_swing_postmarket_snapshot(sb)   # second run same day

    snaps = sb.table("swing_idea_snapshots").rows
    assert len(snaps) == 1                 # unique (idea_id, snapshot_date, snapshot_type)
```

- [ ] **Step 2: Run — fail (ImportError)**

- [ ] **Step 3: Implement pipeline**

```python
# api/indicators/swing/pipeline/postmarket.py
"""Post-market snapshot pipeline.

Called by Plan 2's daily-dispatcher at 21:00 UTC. For each active swing idea:
  1. Fetch today's daily bar (yfinance, cached with other active tickers in one call)
  2. Recompute indicators from the fresh close
  3. Check cycle-stage transitions (reuse Plan 2's stage-detection helper)
  4. Check stop violations → status='invalidated'
  5. Run exhaustion_extension detector → set risk_flags + append event
  6. Upsert snapshot row (natural key (idea_id, snapshot_date, snapshot_type))
  7. Post Slack digest

Idempotent: re-running the same day is a no-op on snapshots (UNIQUE constraint)
and re-computes risk_flags without duplicating events (we dedupe by event_type+date).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

import pandas as pd

from api.indicators.common.moving_averages import ema, sma
from api.indicators.common.atr import atr
from api.indicators.swing.setups.exhaustion_extension import detect_exhaustion_extension

logger = logging.getLogger(__name__)


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


@dataclass
class PostmarketResult:
    ran_at: datetime
    active_ideas_processed: int
    stage_transitions: int
    exhaustion_warnings: int
    stop_violations: int
    snapshots_written: int


def _fetch_daily_bars(ticker: str) -> pd.DataFrame | None:
    """Fetch ~1 year of daily bars for a single ticker via yfinance."""
    import yfinance as yf
    try:
        raw = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return None
        df = raw.reset_index().rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning("Failed to fetch bars for %s: %s", ticker, e)
        return None


def _post_slack_digest(summary: dict) -> None:
    """Thin wrapper so tests can monkey-patch."""
    from api.indicators.swing.pipeline.slack import post_postmarket_digest
    post_postmarket_digest(summary)


def _last_base_breakout_idx(sb: SupabaseLike, idea_id: str, df: pd.DataFrame) -> int | None:
    """Find the index in df where this idea's last base_n_break fired (from events)."""
    events = (
        sb.table("swing_events").select("*").eq("idea_id", idea_id)
        .eq("event_type", "setup_fired").execute().data or []
    )
    for e in reversed(events):
        payload = e.get("payload") or {}
        if payload.get("setup_kell") == "base_n_break":
            # match by date
            occurred = e.get("occurred_at")
            if not occurred:
                continue
            target_date = pd.to_datetime(occurred).date()
            matches = df.index[df["date"].apply(lambda d: pd.to_datetime(d).date()) == target_date]
            if len(matches) > 0:
                return int(matches[0])
    return None


def run_swing_postmarket_snapshot(sb: SupabaseLike) -> PostmarketResult:
    now = datetime.now(timezone.utc)
    today = now.date()

    active = (
        sb.table("swing_ideas").select("*")
        .execute().data or []
    )
    active = [i for i in active if i["status"] not in ("exited", "invalidated")]

    stage_transitions = 0
    exhaustion_warnings = 0
    stop_violations = 0
    snapshots_written = 0

    for idea in active:
        ticker = idea["ticker"]
        df = _fetch_daily_bars(ticker)
        if df is None or df.empty:
            logger.warning("No bars for %s; skipping", ticker)
            continue

        last_close = float(df["close"].iloc[-1])

        # 1. Stop violation
        if last_close < float(idea["stop_price"]):
            sb.table("swing_ideas").update({
                "status": "invalidated",
                "invalidated_at": now.isoformat(),
                "invalidated_reason": f"stop violation: close {last_close:.2f} < stop {idea['stop_price']:.2f}",
            }).eq("id", idea["id"]).execute()
            sb.table("swing_events").insert({
                "idea_id": idea["id"],
                "event_type": "invalidation",
                "occurred_at": now.isoformat(),
                "summary": f"Stop violated at {last_close:.2f}",
                "payload": {"close": last_close, "stop": idea["stop_price"]},
            }).execute()
            stop_violations += 1
            # Do not continue to exhaustion — idea is dead.
            continue

        # 2. Exhaustion detector
        breakout_idx = _last_base_breakout_idx(sb, idea["id"], df)
        flag = detect_exhaustion_extension(df, last_base_breakout_idx=breakout_idx)
        if flag.any():
            # Merge into existing risk_flags
            current_flags = idea.get("risk_flags") or {}
            new_flags = {
                **current_flags,
                "kell_2nd_extension": flag.kell_2nd_extension,
                "climax_bar": flag.climax_bar,
                "far_above_10ema": flag.far_above_10ema,
                "weekly_air": flag.weekly_air,
                "last_flagged_at": now.isoformat(),
            }
            patch = {"risk_flags": new_flags}
            # Move to trailing if currently triggered/adding
            if idea["status"] in ("triggered", "adding"):
                patch["status"] = "trailing"
            sb.table("swing_ideas").update(patch).eq("id", idea["id"]).execute()

            # Dedupe: one exhaustion_warning event per idea per date
            existing = sb.table("swing_events").select("*").eq("idea_id", idea["id"]).eq("event_type", "exhaustion_warning").execute().data or []
            already_today = any(
                pd.to_datetime(e.get("occurred_at")).date() == today for e in existing if e.get("occurred_at")
            )
            if not already_today:
                sb.table("swing_events").insert({
                    "idea_id": idea["id"],
                    "event_type": "exhaustion_warning",
                    "occurred_at": now.isoformat(),
                    "summary": _summarize_flag(flag),
                    "payload": {
                        "kell_2nd_extension": flag.kell_2nd_extension,
                        "climax_bar": flag.climax_bar,
                        "far_above_10ema": flag.far_above_10ema,
                        "weekly_air": flag.weekly_air,
                    },
                }).execute()
            exhaustion_warnings += 1

        # 3. Upsert snapshot (natural key: idea_id + snapshot_date + 'daily')
        ema10 = float(ema(df["close"], 10).iloc[-1])
        ema20 = float(ema(df["close"], 20).iloc[-1])
        sma50 = float(sma(df["close"], 50).iloc[-1]) if len(df) >= 50 else None
        sma200 = float(sma(df["close"], 200).iloc[-1]) if len(df) >= 200 else None

        existing_snap = sb.table("swing_idea_snapshots").select("*").eq("idea_id", idea["id"]).eq("snapshot_date", today.isoformat()).eq("snapshot_type", "daily").execute().data or []
        snap_row = {
            "idea_id": idea["id"],
            "snapshot_date": today.isoformat(),
            "snapshot_type": "daily",
            "daily_close": last_close,
            "daily_high": float(df["high"].iloc[-1]),
            "daily_low": float(df["low"].iloc[-1]),
            "daily_volume": int(df["volume"].iloc[-1]),
            "ema_10": ema10,
            "ema_20": ema20,
            "sma_50": sma50,
            "sma_200": sma200,
            "kell_stage": idea.get("cycle_stage"),
        }
        if existing_snap:
            sb.table("swing_idea_snapshots").update(snap_row).eq("idea_id", idea["id"]).eq("snapshot_date", today.isoformat()).eq("snapshot_type", "daily").execute()
        else:
            sb.table("swing_idea_snapshots").insert(snap_row).execute()
            snapshots_written += 1

    _post_slack_digest({
        "active_ideas": len(active),
        "stage_transitions": stage_transitions,
        "exhaustion_warnings": exhaustion_warnings,
        "stop_violations": stop_violations,
    })

    return PostmarketResult(
        ran_at=now,
        active_ideas_processed=len(active),
        stage_transitions=stage_transitions,
        exhaustion_warnings=exhaustion_warnings,
        stop_violations=stop_violations,
        snapshots_written=snapshots_written,
    )


def _summarize_flag(flag) -> str:
    parts = []
    if flag.kell_2nd_extension: parts.append("2nd extension from 10-EMA")
    if flag.climax_bar: parts.append("climax bar")
    if flag.far_above_10ema: parts.append("far above 10-EMA (H)")
    if flag.weekly_air: parts.append("weekly Air (H)")
    return "Exhaustion warning: " + ", ".join(parts)
```

- [ ] **Step 4: Run — expect pass**

```bash
.venv/bin/python -m pytest tests/swing/test_postmarket_pipeline.py -v
```

- [ ] **Step 5: Verify no Anthropic imports leaked**

```bash
grep -R "^from anthropic\|^import anthropic" api/indicators/swing/ | grep -v tests/
```

Expected: empty.

- [ ] **Step 6: Commit**

```bash
git add api/indicators/swing/pipeline/postmarket.py tests/swing/test_postmarket_pipeline.py
git commit -m "feat(swing): add post-market pipeline with exhaustion + stop-check + snapshots"
```

---

## Task 4: Slack digest — `post_postmarket_digest()` + `post_weekend_refresh_digest()`

**Files:**
- Modify: `api/indicators/swing/pipeline/slack.py` (Plan 2)

- [ ] **Step 1: Append helpers**

```python
# api/indicators/swing/pipeline/slack.py — append

def post_postmarket_digest(summary: dict) -> None:
    """Post the 2pm PT digest to #swing-alerts."""
    from api.services.slack_router import send_to_channel  # existing multi-channel router

    lines = [
        ":closed_book: *Swing Post-Market Digest*",
        f"Active ideas processed: {summary.get('active_ideas', 0)}",
    ]
    if summary.get("stage_transitions"):
        lines.append(f":arrows_counterclockwise: Stage transitions: {summary['stage_transitions']}")
    if summary.get("exhaustion_warnings"):
        lines.append(f":warning: Exhaustion warnings: {summary['exhaustion_warnings']}")
    if summary.get("stop_violations"):
        lines.append(f":octagonal_sign: Stop violations (invalidated): {summary['stop_violations']}")
    lines.append(":mag: Deep analysis kicking off at 2:30pm PT on user's Mac")
    send_to_channel("swing-alerts", "\n".join(lines))


def post_weekend_refresh_digest(result) -> None:
    """Post the Sunday 4:30pm PT universe-refresh digest to #swing-alerts."""
    from api.services.slack_router import send_to_channel

    if result.skipped:
        msg = f":arrows_counterclockwise: Skipped universe refresh: {result.skip_reason}"
    else:
        msg = (f":arrows_counterclockwise: *Backend universe refreshed*\n"
               f"Base: {result.base_count}  →  Final: {result.final_count}")
    send_to_channel("swing-alerts", msg)
```

- [ ] **Step 2: Quick smoke test**

```bash
.venv/bin/python -c "from api.indicators.swing.pipeline.slack import post_postmarket_digest, post_weekend_refresh_digest; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add api/indicators/swing/pipeline/slack.py
git commit -m "feat(swing): add post-market + weekend-refresh Slack digest helpers"
```

---

## Task 5: Postmarket Railway endpoint + wire dispatcher

**Files:**
- Create: `api/endpoints/swing_postmarket.py`
- Modify: `api/indicators/swing/pipeline/dispatcher.py` (Plan 2)
- Modify: `api/main.py`
- Create: `tests/swing/test_postmarket_endpoint.py`

- [ ] **Step 1: Write endpoint test**

```python
# tests/swing/test_postmarket_endpoint.py
from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch("api.endpoints.swing_postmarket._get_supabase")
@patch("api.endpoints.swing_postmarket.run_swing_postmarket_snapshot")
def test_postmarket_endpoint_requires_bearer(mock_run, mock_sb):
    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket")
    assert r.status_code in (401, 403)


@patch.dict("os.environ", {"SWING_API_TOKEN": "secret"})
@patch("api.endpoints.swing_postmarket._get_supabase")
@patch("api.endpoints.swing_postmarket.run_swing_postmarket_snapshot")
def test_postmarket_endpoint_runs_pipeline(mock_run, mock_sb):
    from datetime import datetime, timezone
    from api.indicators.swing.pipeline.postmarket import PostmarketResult

    mock_sb.return_value = FakeSupabaseClient()
    mock_run.return_value = PostmarketResult(
        ran_at=datetime.now(timezone.utc),
        active_ideas_processed=3, stage_transitions=1,
        exhaustion_warnings=1, stop_violations=0, snapshots_written=3,
    )

    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["active_ideas_processed"] == 3
    assert body["snapshots_written"] == 3
```

- [ ] **Step 2: Implement endpoint**

```python
# api/endpoints/swing_postmarket.py
"""Post-market and universe-refresh Railway endpoints.

POST /api/swing/pipeline/postmarket      (bearer-protected; called by daily-dispatcher at 21:00 UTC)
POST /api/swing/pipeline/universe-refresh (bearer-protected; called by weekend-refresh at 23:30 UTC Sun)
"""
from __future__ import annotations

import functools
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.auth.swing_token import require_swing_token   # from Plan 3
from api.indicators.swing.pipeline.postmarket import run_swing_postmarket_snapshot
from api.indicators.swing.pipeline.universe_refresh import run_swing_universe_refresh
from api.schemas.swing import PostmarketRunResponse, UniverseRefreshResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/swing/pipeline", tags=["swing-pipeline"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post("/postmarket", response_model=PostmarketRunResponse)
def trigger_postmarket(_token: str = Depends(require_swing_token)) -> PostmarketRunResponse:
    sb = _get_supabase()
    result = run_swing_postmarket_snapshot(sb)
    return PostmarketRunResponse(
        ran_at=result.ran_at,
        active_ideas_processed=result.active_ideas_processed,
        stage_transitions=result.stage_transitions,
        exhaustion_warnings=result.exhaustion_warnings,
        stop_violations=result.stop_violations,
        snapshots_written=result.snapshots_written,
    )


@router.post("/universe-refresh", response_model=UniverseRefreshResponse)
def trigger_universe_refresh(_token: str = Depends(require_swing_token)) -> UniverseRefreshResponse:
    sb = _get_supabase()
    result = run_swing_universe_refresh(sb)
    return UniverseRefreshResponse(**result)
```

- [ ] **Step 3: Register router in `api/main.py`**

```python
# api/main.py — add with other routers
from api.endpoints.swing_postmarket import router as swing_pipeline_router
app.include_router(swing_pipeline_router)
```

- [ ] **Step 4: Wire dispatcher to call postmarket at 21:00 UTC**

Locate Plan 2's dispatcher (`api/indicators/swing/pipeline/dispatcher.py` or wherever Plan 2 placed it — name is `run_dispatcher(hour)` or similar). Extend the 21:00 branch:

```python
# api/indicators/swing/pipeline/dispatcher.py — around the hour branching

def run_dispatcher(hour: int, sb=None) -> dict:
    sb = sb or _get_supabase()
    if hour == 13:
        return {"swing_premarket": run_swing_premarket_detection(sb),
                "daily_screeners": run_daily_screeners(sb)}
    elif hour == 21:
        return {"swing_postmarket": run_swing_postmarket_snapshot(sb),
                "market_monitor": run_market_monitor(sb)}
    raise ValueError(f"Unexpected hour: {hour}")
```

If Plan 2 didn't yet add the 21 branch, add it now. If Plan 2's naming differs, adapt to match.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/swing/test_postmarket_endpoint.py -v
```

- [ ] **Step 6: Commit**

```bash
git add api/endpoints/swing_postmarket.py api/main.py api/indicators/swing/pipeline/dispatcher.py tests/swing/test_postmarket_endpoint.py
git commit -m "feat(swing): add postmarket endpoint and wire dispatcher @ 21:00 UTC"
```

---

## Task 6: Universe-refresh helper + weekend-refresh Vercel cron

**Files:**
- Create: `api/indicators/swing/pipeline/universe_refresh.py`
- Create: `frontend/src/app/api/cron/weekend-refresh/route.ts`
- Modify: `frontend/vercel.json`
- Create: `tests/swing/test_universe_refresh_endpoint.py`

- [ ] **Step 1: Write failing test**

```python
# tests/swing/test_universe_refresh_endpoint.py
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from api.indicators.swing.pipeline.universe_refresh import run_swing_universe_refresh
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def test_skip_when_deepvue_is_fresh():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    sb.table("swing_universe").insert([{
        "id": 1, "ticker": "NVDA", "source": "deepvue-csv", "batch_id": str(uuid4()),
        "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None,
    }])
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is True
    assert "deepvue" in result["skip_reason"].lower()


@patch("api.indicators.swing.pipeline.universe_refresh.generate_backend_universe")
def test_runs_generator_when_universe_stale(mock_gen):
    sb = FakeSupabaseClient()
    mock_gen.return_value = {
        "passers": {"AAPL": {"fundamentals": {"quarterly_revenue_yoy": [0.45]}}},
        "stats": {"base_count": 100, "stage12_count": 50, "stage3_count": 10, "final_count": 1},
    }
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is False
    assert result["final_count"] == 1
    rows = sb.table("swing_universe").rows
    assert any(r["ticker"] == "AAPL" and r["source"] == "backend-generated" for r in rows)
```

- [ ] **Step 2: Implement wrapper**

```python
# api/indicators/swing/pipeline/universe_refresh.py
"""Sunday universe-refresh wrapper.

Skips if the latest Deepvue CSV upload is < 7 days old; otherwise calls
Plan 1's generate_backend_universe() and persists via save_universe_batch().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from api.indicators.swing.universe.generator import generate_backend_universe
from api.indicators.swing.universe.resolver import save_universe_batch

logger = logging.getLogger(__name__)

FRESHNESS_DAYS = 7


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


def run_swing_universe_refresh(sb: SupabaseLike) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESHNESS_DAYS)

    deepvue_rows = (
        sb.table("swing_universe").select("*")
        .eq("source", "deepvue-csv").is_("removed_at", None)
        .order("added_at", desc=True).limit(1).execute().data or []
    )
    if deepvue_rows:
        latest = deepvue_rows[0]["added_at"]
        latest_dt = latest if isinstance(latest, datetime) else datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
        if latest_dt >= cutoff:
            result = {
                "ran_at": now.isoformat(),
                "skipped": True,
                "skip_reason": f"deepvue-csv upload is {(now - latest_dt).days}d old",
                "base_count": None, "final_count": None, "batch_id": None,
            }
            _post_slack(result)
            return result

    gen = generate_backend_universe()
    tickers_with_extras = {
        t: {"fundamentals": info.get("fundamentals", {})}
        for t, info in gen["passers"].items()
    }
    batch_id = save_universe_batch(sb, tickers_with_extras, source="backend-generated", mode="replace")

    result = {
        "ran_at": now.isoformat(),
        "skipped": False,
        "skip_reason": None,
        "base_count": gen["stats"]["base_count"],
        "final_count": gen["stats"]["final_count"],
        "batch_id": str(batch_id),
    }
    _post_slack(result)
    return result


def _post_slack(result: dict) -> None:
    try:
        from types import SimpleNamespace
        from api.indicators.swing.pipeline.slack import post_weekend_refresh_digest
        post_weekend_refresh_digest(SimpleNamespace(**result))
    except Exception as e:
        logger.warning("Slack digest failed (non-fatal): %s", e)
```

- [ ] **Step 3: Run — expect pass**

```bash
.venv/bin/python -m pytest tests/swing/test_universe_refresh_endpoint.py -v
```

- [ ] **Step 4: Add Next.js cron handler**

```typescript
// frontend/src/app/api/cron/weekend-refresh/route.ts
/**
 * Vercel cron: Sundays 23:30 UTC (= 4:30pm PT winter / 3:30pm PT summer).
 * Runs BEFORE /swing-weekly-synth (5pm PT on Mac) so weekly synth sees
 * a refreshed backend-generated universe when Deepvue is stale.
 */
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 300;   // universe generator can take minutes

export async function GET(req: Request) {
  const cronSecret = req.headers.get("authorization");
  if (cronSecret !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const railwayUrl = process.env.RAILWAY_API_URL!;
  const swingToken = process.env.SWING_API_TOKEN!;

  const r = await fetch(`${railwayUrl}/api/swing/pipeline/universe-refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${swingToken}` },
  });
  const body = await r.json();
  return NextResponse.json({ ok: r.ok, upstream: body });
}
```

- [ ] **Step 5: Register the cron in `frontend/vercel.json`**

```jsonc
{
  "crons": [
    { "path": "/api/cron/daily-dispatcher", "schedule": "0 13,21 * * 1-5" },
    { "path": "/api/cron/weekend-refresh", "schedule": "30 23 * * 0" }
  ]
}
```

Verify: exactly 2 entries in the array (Hobby plan limit).

- [ ] **Step 6: Commit**

```bash
git add api/indicators/swing/pipeline/universe_refresh.py \
        frontend/src/app/api/cron/weekend-refresh/route.ts \
        frontend/vercel.json \
        tests/swing/test_universe_refresh_endpoint.py
git commit -m "feat(swing): add weekend-refresh cron + universe-refresh endpoint"
```

---

## Task 7: Vercel Blob integration + upload-token endpoint (frontend)

Charts upload from Next.js client → Vercel Blob (client-direct-upload with server token) → Railway receives just the final URL.

**Files:**
- Modify: `frontend/package.json` — add `@vercel/blob`
- Create: `frontend/src/app/api/swing/blob/upload-token/route.ts`

- [ ] **Step 1: Add dependency**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp/frontend
npm install @vercel/blob
```

- [ ] **Step 2: Add upload-token route**

```typescript
// frontend/src/app/api/swing/blob/upload-token/route.ts
/**
 * Returns a one-shot client upload token for Vercel Blob.
 * Called by the chart-upload-dropzone component before PUTting the file.
 */
import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const body = (await request.json()) as HandleUploadBody;
  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        // restrict to .png/.jpg/.webp under /swing-charts/
        if (!pathname.startsWith("swing-charts/")) {
          throw new Error("Invalid pathname");
        }
        return {
          allowedContentTypes: ["image/png", "image/jpeg", "image/webp"],
          tokenPayload: JSON.stringify({}),
        };
      },
      onUploadCompleted: async ({ blob }) => {
        // Nothing server-side here — the client component posts the URL to Railway
        // after the PUT resolves.
        console.log("Blob uploaded:", blob.url);
      },
    });
    return NextResponse.json(jsonResponse);
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/api/swing/blob/
git commit -m "feat(swing): add Vercel Blob client-upload token endpoint"
```

---

## Task 8: Charts endpoint (backend) — list + POST URL record

Charts table enforces "exactly one of idea_id/event_id/model_book_id" via DB CHECK. Endpoint validates server-side too.

**Files:**
- Create: `api/endpoints/swing_charts.py`
- Create: `tests/swing/test_charts_endpoint.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing test**

```python
# tests/swing/test_charts_endpoint.py
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
        {"id": str(uuid4()), "idea_id": idea_id, "image_url": "a.png", "timeframe": "daily", "source": "deepvue-auto"},
        {"id": str(uuid4()), "idea_id": idea_id, "image_url": "b.png", "timeframe": "weekly", "source": "deepvue-auto"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get(f"/api/swing/ideas/{idea_id}/charts")
    assert r.status_code == 200
    assert len(r.json()) == 2
```

- [ ] **Step 2: Implement endpoints**

```python
# api/endpoints/swing_charts.py
"""Swing chart endpoints — record chart URLs, list by idea/event/model-book.

The actual image bytes live in Vercel Blob. The Next.js client uploads there
directly, then POSTs the resulting URL here.
"""
from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client, create_client

from api.auth.swing_token import require_swing_token
from api.schemas.swing import ChartCreateRequest, ChartResponse

router = APIRouter(tags=["swing-charts"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post("/api/swing/charts", response_model=ChartResponse, status_code=201)
def create_chart(req: ChartCreateRequest, _token: str = Depends(require_swing_token)) -> ChartResponse:
    owners = [req.idea_id, req.event_id, req.model_book_id]
    if sum(1 for o in owners if o is not None) != 1:
        raise HTTPException(400, "Exactly one of idea_id, event_id, model_book_id must be set")
    sb = _get_supabase()
    row = {
        "id": str(uuid4()),
        "idea_id": str(req.idea_id) if req.idea_id else None,
        "event_id": req.event_id,
        "model_book_id": str(req.model_book_id) if req.model_book_id else None,
        "image_url": req.image_url,
        "thumbnail_url": req.thumbnail_url,
        "timeframe": req.timeframe,
        "source": req.source,
        "annotations": req.annotations,
        "caption": req.caption,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.table("swing_charts").insert(row).execute()

    # Append a chart_uploaded event on the idea (if attached to an idea)
    if req.idea_id:
        sb.table("swing_events").insert({
            "idea_id": str(req.idea_id),
            "event_type": "chart_uploaded",
            "occurred_at": row["captured_at"],
            "summary": f"Chart uploaded ({req.timeframe}, {req.source})",
            "payload": {"chart_id": row["id"], "image_url": req.image_url},
        }).execute()

    return ChartResponse(**row)


@router.get("/api/swing/ideas/{idea_id}/charts", response_model=list[ChartResponse])
def list_idea_charts(idea_id: UUID) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("idea_id", str(idea_id)).order("captured_at", desc=True).execute().data or []
    return [ChartResponse(**r) for r in rows]


@router.get("/api/swing/events/{event_id}/charts", response_model=list[ChartResponse])
def list_event_charts(event_id: int) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("event_id", event_id).execute().data or []
    return [ChartResponse(**r) for r in rows]


@router.get("/api/swing/model-book/{model_book_id}/charts", response_model=list[ChartResponse])
def list_model_book_charts(model_book_id: UUID) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("model_book_id", str(model_book_id)).execute().data or []
    return [ChartResponse(**r) for r in rows]
```

- [ ] **Step 3: Register router**

```python
# api/main.py
from api.endpoints.swing_charts import router as swing_charts_router
app.include_router(swing_charts_router)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/swing/test_charts_endpoint.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/endpoints/swing_charts.py api/main.py tests/swing/test_charts_endpoint.py
git commit -m "feat(swing): add charts CRUD endpoint with one-owner enforcement"
```

---

## Task 9: Snapshots endpoint — GET list + POST Mac-populated analysis

**Files:**
- Create: `api/endpoints/swing_snapshots.py`
- Create: `tests/swing/test_snapshots_endpoint.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing test**

```python
# tests/swing/test_snapshots_endpoint.py
from datetime import date
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.endpoints.swing_snapshots._get_supabase")
def test_mac_can_attach_claude_analysis_to_existing_snapshot(mock_sb):
    idea_id = str(uuid4())
    sb = FakeSupabaseClient()
    sb.table("swing_idea_snapshots").insert([{
        "id": 1, "idea_id": idea_id, "snapshot_date": "2026-04-18",
        "snapshot_type": "daily", "daily_close": 100.0,
    }])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.post(f"/api/swing/ideas/{idea_id}/snapshots", json={
        "snapshot_date": "2026-04-18",
        "snapshot_type": "daily",
        "claude_analysis": "Constructive setup; waiting for volume confirmation.",
        "claude_model": "claude-opus-4-7",
        "chart_daily_url": "https://blob.vercel/d.png",
    }, headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    row = sb.table("swing_idea_snapshots").rows[0]
    assert row["claude_analysis"].startswith("Constructive")
    assert row["daily_close"] == 100.0  # preserved


@patch("api.endpoints.swing_snapshots._get_supabase")
def test_get_snapshots_by_idea(mock_sb):
    idea_id = str(uuid4())
    sb = FakeSupabaseClient()
    sb.table("swing_idea_snapshots").insert([
        {"id": 1, "idea_id": idea_id, "snapshot_date": "2026-04-15", "snapshot_type": "daily"},
        {"id": 2, "idea_id": idea_id, "snapshot_date": "2026-04-16", "snapshot_type": "daily"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get(f"/api/swing/ideas/{idea_id}/snapshots")
    assert r.status_code == 200
    assert len(r.json()) == 2
```

- [ ] **Step 2: Implement**

```python
# api/endpoints/swing_snapshots.py
"""Snapshots endpoint.

GET list by idea_id (open — consumed by frontend proxy)
POST upsert by natural key (idea_id, snapshot_date, snapshot_type).
Used both by Mac-Claude (to attach claude_analysis + chart URLs) and,
in emergencies, to hand-patch a snapshot.
"""
from __future__ import annotations

import functools
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.auth.swing_token import require_swing_token
from api.schemas.swing import SnapshotCreateRequest, SnapshotResponse

router = APIRouter(tags=["swing-snapshots"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.get("/api/swing/ideas/{idea_id}/snapshots", response_model=list[SnapshotResponse])
def list_snapshots(idea_id: UUID) -> list[SnapshotResponse]:
    sb = _get_supabase()
    rows = (sb.table("swing_idea_snapshots").select("*")
            .eq("idea_id", str(idea_id)).order("snapshot_date", desc=True)
            .execute().data or [])
    return [SnapshotResponse(**r) for r in rows]


@router.post("/api/swing/ideas/{idea_id}/snapshots", response_model=SnapshotResponse)
def upsert_snapshot(
    idea_id: UUID, req: SnapshotCreateRequest, _token: str = Depends(require_swing_token),
) -> SnapshotResponse:
    sb = _get_supabase()
    # Look up existing snapshot by natural key
    existing = (sb.table("swing_idea_snapshots").select("*")
                .eq("idea_id", str(idea_id))
                .eq("snapshot_date", req.snapshot_date.isoformat())
                .eq("snapshot_type", req.snapshot_type).execute().data or [])
    patch = {k: v for k, v in req.model_dump().items() if v is not None and k not in ("snapshot_date", "snapshot_type")}
    if existing:
        row = existing[0]
        row.update(patch)
        sb.table("swing_idea_snapshots").update(patch).eq("id", row["id"]).execute()
        return SnapshotResponse(**row)
    # Insert fresh
    row = {
        "idea_id": str(idea_id),
        "snapshot_date": req.snapshot_date.isoformat(),
        "snapshot_type": req.snapshot_type,
        **patch,
    }
    inserted = sb.table("swing_idea_snapshots").insert(row).execute()
    return SnapshotResponse(**(inserted.data[0] if hasattr(inserted, "data") else row))
```

- [ ] **Step 3: Register router**

```python
# api/main.py
from api.endpoints.swing_snapshots import router as swing_snapshots_router
app.include_router(swing_snapshots_router)
```

- [ ] **Step 4: Run tests + commit**

```bash
.venv/bin/python -m pytest tests/swing/test_snapshots_endpoint.py -v
git add api/endpoints/swing_snapshots.py api/main.py tests/swing/test_snapshots_endpoint.py
git commit -m "feat(swing): add snapshots GET + POST endpoint (Mac-side writes claude_analysis)"
```

---

## Task 10: Model Book endpoint — CRUD

**Files:**
- Create: `api/endpoints/swing_model_book.py`
- Create: `tests/swing/test_model_book_endpoint.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/swing/test_model_book_endpoint.py
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
```

- [ ] **Step 2: Implement**

```python
# api/endpoints/swing_model_book.py
from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.auth.swing_token import require_swing_token
from api.schemas.swing import ModelBookCreateRequest, ModelBookPatchRequest, ModelBookResponse

router = APIRouter(prefix="/api/swing/model-book", tags=["swing-model-book"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.get("", response_model=list[ModelBookResponse])
def list_entries(
    setup_kell: Optional[str] = None,
    outcome: Optional[str] = None,
    ticker: Optional[str] = None,
) -> list[ModelBookResponse]:
    sb = _get_supabase()
    q = sb.table("swing_model_book").select("*")
    if setup_kell: q = q.eq("setup_kell", setup_kell)
    if outcome: q = q.eq("outcome", outcome)
    if ticker: q = q.eq("ticker", ticker.upper())
    rows = q.order("created_at", desc=True).execute().data or []
    return [ModelBookResponse(**r) for r in rows]


@router.get("/{entry_id}", response_model=ModelBookResponse)
def get_entry(entry_id: UUID) -> ModelBookResponse:
    sb = _get_supabase()
    rows = sb.table("swing_model_book").select("*").eq("id", str(entry_id)).execute().data or []
    if not rows:
        raise HTTPException(404)
    return ModelBookResponse(**rows[0])


@router.post("", response_model=ModelBookResponse, status_code=201)
def create_entry(
    req: ModelBookCreateRequest, _token: str = Depends(require_swing_token),
) -> ModelBookResponse:
    sb = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid4()),
        **req.model_dump(mode="json"),
        "created_at": now,
        "updated_at": now,
    }
    sb.table("swing_model_book").insert(row).execute()

    # If promoted from an idea, append event
    if req.source_idea_id:
        sb.table("swing_events").insert({
            "idea_id": str(req.source_idea_id),
            "event_type": "promoted_to_model_book",
            "occurred_at": now,
            "summary": f"Added to Model Book: {req.title}",
            "payload": {"model_book_id": row["id"]},
        }).execute()

    return ModelBookResponse(**row)


@router.patch("/{entry_id}", response_model=ModelBookResponse)
def patch_entry(
    entry_id: UUID, req: ModelBookPatchRequest, _token: str = Depends(require_swing_token),
) -> ModelBookResponse:
    sb = _get_supabase()
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = sb.table("swing_model_book").update(patch).eq("id", str(entry_id)).execute().data or []
    if not rows:
        raise HTTPException(404)
    return ModelBookResponse(**rows[0])


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: UUID, _token: str = Depends(require_swing_token)) -> None:
    sb = _get_supabase()
    sb.table("swing_model_book").delete().eq("id", str(entry_id)).execute()
```

- [ ] **Step 3: Register router + run tests + commit**

```bash
# api/main.py
from api.endpoints.swing_model_book import router as swing_model_book_router
app.include_router(swing_model_book_router)
```

```bash
.venv/bin/python -m pytest tests/swing/test_model_book_endpoint.py -v
git add api/endpoints/swing_model_book.py api/main.py tests/swing/test_model_book_endpoint.py
git commit -m "feat(swing): add model book CRUD endpoint"
```

---

## Task 11: Events endpoint — GET list (POST comes from Plan 3)

Plan 3 provides `POST /api/swing/ideas/<id>/events`. Plan 4 only adds GET for the frontend timeline.

**Files:**
- Modify: Plan 3's events endpoint file (likely `api/endpoints/swing_events.py` or `swing.py`) OR create a thin `api/endpoints/swing_events_read.py` if Plan 3 didn't add GET.

- [ ] **Step 1: Check Plan 3's shape**

```bash
grep -R "swing/ideas.*events" api/endpoints/ 2>/dev/null
grep -Rn "def list_events\|events.*GET" api/endpoints/ 2>/dev/null
```

If Plan 3 already added a GET, skip this task. Otherwise:

- [ ] **Step 2: Add GET in same file Plan 3 used (or new minimal file)**

```python
# Append to Plan 3's swing_events router module

@router.get("/api/swing/ideas/{idea_id}/events", response_model=list[EventResponse])
def list_events(idea_id: UUID) -> list[EventResponse]:
    sb = _get_supabase()
    rows = (sb.table("swing_events").select("*").eq("idea_id", str(idea_id))
            .order("occurred_at", desc=True).execute().data or [])
    return [EventResponse(**r) for r in rows]
```

- [ ] **Step 3: Smoke test + commit**

```bash
.venv/bin/python -m pytest tests/swing/ -v -k events
git add api/endpoints/  tests/swing/
git commit -m "feat(swing): add GET events list endpoint for timeline"
```

---

## Task 12: Weekly synthesis — GET archive endpoint

Weekly syntheses are stored as `swing_idea_snapshots` rows with `snapshot_type='weekly'`. The archive view groups them by week.

**Files:**
- Modify: Plan 3's `api/endpoints/swing_ideas.py` OR create `api/endpoints/swing_weekly.py`
- Create: `tests/swing/test_weekly_endpoint.py`

- [ ] **Step 1: Write failing test**

```python
# tests/swing/test_weekly_endpoint.py
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch("api.endpoints.swing_weekly._get_supabase")
def test_list_weekly_groups_by_week(mock_sb):
    sb = FakeSupabaseClient()
    id1, id2 = str(uuid4()), str(uuid4())
    sb.table("swing_idea_snapshots").insert([
        {"id": 1, "idea_id": id1, "snapshot_date": "2026-04-12", "snapshot_type": "weekly", "claude_analysis": "NVDA: consolidating."},
        {"id": 2, "idea_id": id2, "snapshot_date": "2026-04-12", "snapshot_type": "weekly", "claude_analysis": "AMD: breaking."},
        {"id": 3, "idea_id": id1, "snapshot_date": "2026-04-05", "snapshot_type": "weekly", "claude_analysis": "NVDA: first base week."},
    ])
    sb.table("swing_ideas").insert([
        {"id": id1, "ticker": "NVDA", "status": "triggered", "cycle_stage": "base_n_break", "confluence_score": 7, "stop_price": 100.0, "setup_kell": "base_n_break", "direction": "long"},
        {"id": id2, "ticker": "AMD", "status": "triggered", "cycle_stage": "wedge_pop", "confluence_score": 6, "stop_price": 90.0, "setup_kell": "wedge_pop", "direction": "long"},
    ])
    mock_sb.return_value = sb
    client = TestClient(app)
    r = client.get("/api/swing/weekly")
    assert r.status_code == 200
    weeks = r.json()
    assert len(weeks) == 2
    assert weeks[0]["week_of"] == "2026-04-12"
    assert len(weeks[0]["entries"]) == 2
```

- [ ] **Step 2: Implement**

```python
# api/endpoints/swing_weekly.py
from __future__ import annotations

import functools
import os
from collections import defaultdict

from fastapi import APIRouter
from pydantic import BaseModel
from supabase import Client, create_client

router = APIRouter(tags=["swing-weekly"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


class WeeklyEntry(BaseModel):
    idea_id: str
    ticker: str
    cycle_stage: str | None
    status: str
    claude_analysis: str | None


class WeekGroup(BaseModel):
    week_of: str
    entries: list[WeeklyEntry]


@router.get("/api/swing/weekly", response_model=list[WeekGroup])
def list_weekly() -> list[WeekGroup]:
    sb = _get_supabase()
    snaps = (sb.table("swing_idea_snapshots").select("*")
             .eq("snapshot_type", "weekly").order("snapshot_date", desc=True)
             .execute().data or [])
    ideas = {i["id"]: i for i in (sb.table("swing_ideas").select("*").execute().data or [])}

    grouped: dict[str, list[WeeklyEntry]] = defaultdict(list)
    for s in snaps:
        idea = ideas.get(s["idea_id"])
        if not idea:
            continue
        grouped[s["snapshot_date"]].append(WeeklyEntry(
            idea_id=s["idea_id"],
            ticker=idea["ticker"],
            cycle_stage=idea.get("cycle_stage"),
            status=idea["status"],
            claude_analysis=s.get("claude_analysis"),
        ))

    return [WeekGroup(week_of=w, entries=grouped[w]) for w in sorted(grouped.keys(), reverse=True)]
```

- [ ] **Step 3: Register + run + commit**

```bash
# api/main.py
from api.endpoints.swing_weekly import router as swing_weekly_router
app.include_router(swing_weekly_router)
```

```bash
.venv/bin/python -m pytest tests/swing/test_weekly_endpoint.py -v
git add api/endpoints/swing_weekly.py api/main.py tests/swing/test_weekly_endpoint.py
git commit -m "feat(swing): add weekly synthesis archive endpoint"
```

---

## Task 13: Frontend types + proxy routes (Next.js)

**Files:**
- Modify: `frontend/src/lib/swing-types.ts`
- Create: `frontend/src/app/api/swing/ideas/[id]/snapshots/route.ts`
- Create: `frontend/src/app/api/swing/ideas/[id]/events/route.ts`
- Create: `frontend/src/app/api/swing/ideas/[id]/charts/route.ts`
- Create: `frontend/src/app/api/swing/events/[id]/charts/route.ts`
- Create: `frontend/src/app/api/swing/model-book/route.ts`
- Create: `frontend/src/app/api/swing/model-book/[id]/route.ts`
- Create: `frontend/src/app/api/swing/model-book/[id]/charts/route.ts`
- Create: `frontend/src/app/api/swing/weekly/route.ts`
- Create: `frontend/src/app/api/swing/charts/route.ts` (generic POST for chart URL record)

Each proxy route is a thin `railwayFetch()` wrapper — match the pattern Plan 1 set up for universe routes.

- [ ] **Step 1: Add types**

```typescript
// frontend/src/lib/swing-types.ts — append
export type SwingEvent = {
  id: number;
  idea_id: string;
  event_type:
    | "stage_transition" | "thesis_updated" | "setup_fired" | "invalidation"
    | "earnings" | "exhaustion_warning" | "user_note" | "chart_uploaded"
    | "trade_recorded" | "promoted_to_model_book";
  occurred_at: string;
  summary: string | null;
  payload: Record<string, unknown> | null;
};

export type SwingSnapshot = {
  id: number;
  idea_id: string;
  snapshot_date: string;
  snapshot_type: "daily" | "weekly";
  daily_close: number | null;
  ema_10: number | null;
  ema_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  kell_stage: string | null;
  claude_analysis: string | null;
  chart_daily_url: string | null;
  chart_weekly_url: string | null;
  chart_60m_url: string | null;
};

export type SwingChart = {
  id: string;
  idea_id: string | null;
  event_id: number | null;
  model_book_id: string | null;
  image_url: string;
  thumbnail_url: string | null;
  timeframe: "daily" | "weekly" | "60m" | "annotated";
  source: "deepvue-auto" | "tradingview-upload" | "user-markup" | "claude-annotated";
  annotations: Record<string, unknown> | null;
  caption: string | null;
  captured_at: string;
};

export type SwingModelBookEntry = {
  id: string;
  title: string;
  ticker: string;
  setup_kell: string;
  outcome: "winner" | "loser" | "example" | "missed";
  entry_date: string | null;
  exit_date: string | null;
  r_multiple: number | null;
  source_idea_id: string | null;
  narrative: string | null;
  key_takeaways: string[] | null;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
};

export type SwingWeekGroup = {
  week_of: string;
  entries: Array<{
    idea_id: string;
    ticker: string;
    cycle_stage: string | null;
    status: string;
    claude_analysis: string | null;
  }>;
};
```

- [ ] **Step 2: Add proxy routes (one pattern, repeated)**

Example — adapt for each path:

```typescript
// frontend/src/app/api/swing/ideas/[id]/events/route.ts
import { railwayFetch } from "@/lib/railway-fetch";
import { NextResponse } from "next/server";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await railwayFetch(`/api/swing/ideas/${id}/events`);
  return NextResponse.json(await r.json(), { status: r.status });
}

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json();
  const r = await railwayFetch(`/api/swing/ideas/${id}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.SWING_API_TOKEN}`,
    },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

Repeat for `snapshots`, `charts`, `model-book`, `weekly`, `events/[id]/charts`, `model-book/[id]/charts`. For `GET /api/swing/weekly` and `GET /api/swing/model-book` — no bearer token needed.

For `POST /api/swing/charts` (the generic record-chart-URL endpoint), forward multipart-free JSON:

```typescript
// frontend/src/app/api/swing/charts/route.ts
import { railwayFetch } from "@/lib/railway-fetch";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json();
  const r = await railwayFetch("/api/swing/charts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.SWING_API_TOKEN}`,
    },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build 2>&1 | tail -15
git add frontend/src/lib/swing-types.ts frontend/src/app/api/swing/
git commit -m "feat(swing): add Next.js proxy routes for events/snapshots/charts/model-book/weekly"
```

---

## Task 14: SWR hooks

**Files:**
- Create: `frontend/src/hooks/use-swing-events.ts`
- Create: `frontend/src/hooks/use-swing-snapshots.ts`
- Create: `frontend/src/hooks/use-swing-charts.ts`
- Create: `frontend/src/hooks/use-swing-model-book.ts`
- Create: `frontend/src/hooks/use-swing-weekly.ts`

All hooks follow Plan 1's `use-swing-universe.ts` pattern — SWR with explicit typed fetcher.

- [ ] **Step 1: Implement `use-swing-events.ts`**

```typescript
// frontend/src/hooks/use-swing-events.ts
"use client";
import useSWR from "swr";
import type { SwingEvent } from "@/lib/swing-types";

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingEvent[]>);

export function useSwingEvents(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingEvent[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/events` : null,
    fetcher,
  );
  return { events: data ?? [], isLoading, error, mutate };
}
```

- [ ] **Step 2: Implement the remaining hooks using the same shape**

```typescript
// frontend/src/hooks/use-swing-snapshots.ts
"use client";
import useSWR from "swr";
import type { SwingSnapshot } from "@/lib/swing-types";
const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingSnapshot[]>);
export function useSwingSnapshots(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingSnapshot[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/snapshots` : null, fetcher);
  return { snapshots: data ?? [], isLoading, error, mutate };
}
```

```typescript
// frontend/src/hooks/use-swing-charts.ts
"use client";
import useSWR from "swr";
import type { SwingChart } from "@/lib/swing-types";
const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingChart[]>);
export function useSwingCharts(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingChart[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/charts` : null, fetcher);
  return { charts: data ?? [], isLoading, error, mutate };
}
```

```typescript
// frontend/src/hooks/use-swing-model-book.ts
"use client";
import useSWR from "swr";
import type { SwingModelBookEntry } from "@/lib/swing-types";
type Filters = { setup_kell?: string; outcome?: string; ticker?: string };
const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingModelBookEntry[]>);
export function useSwingModelBook(filters: Filters = {}) {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][]).toString();
  const url = `/api/swing/model-book${q ? `?${q}` : ""}`;
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry[]>(url, fetcher);
  return { entries: data ?? [], isLoading, error, mutate };
}
export function useSwingModelBookEntry(id: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry>(
    id ? `/api/swing/model-book/${id}` : null, (u: string) => fetch(u).then(r => r.json()));
  return { entry: data, isLoading, error, mutate };
}
```

```typescript
// frontend/src/hooks/use-swing-weekly.ts
"use client";
import useSWR from "swr";
import type { SwingWeekGroup } from "@/lib/swing-types";
const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingWeekGroup[]>);
export function useSwingWeekly() {
  const { data, isLoading, error, mutate } = useSWR<SwingWeekGroup[]>("/api/swing/weekly", fetcher);
  return { weeks: data ?? [], isLoading, error, mutate };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-swing-events.ts frontend/src/hooks/use-swing-snapshots.ts frontend/src/hooks/use-swing-charts.ts frontend/src/hooks/use-swing-model-book.ts frontend/src/hooks/use-swing-weekly.ts
git commit -m "feat(swing): add SWR hooks for events/snapshots/charts/model-book/weekly"
```

---

## Task 15: Idea detail page — Timeline component

**Files:**
- Create: `frontend/src/components/swing/idea-timeline.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/swing/idea-timeline.tsx
"use client";
import { useSwingEvents } from "@/hooks/use-swing-events";
import type { SwingEvent } from "@/lib/swing-types";
import { formatDistanceToNow } from "date-fns";

const ICONS: Record<SwingEvent["event_type"], string> = {
  stage_transition: "🔄",
  thesis_updated: "📝",
  setup_fired: "🎯",
  invalidation: "🛑",
  earnings: "📊",
  exhaustion_warning: "⚠️",
  user_note: "🗒️",
  chart_uploaded: "🖼️",
  trade_recorded: "💵",
  promoted_to_model_book: "⭐",
};

export function IdeaTimeline({ ideaId }: { ideaId: string }) {
  const { events, isLoading } = useSwingEvents(ideaId);
  if (isLoading) return <div className="text-muted-foreground">Loading timeline…</div>;
  if (!events.length) return <div className="text-muted-foreground">No events yet.</div>;

  return (
    <ol className="space-y-3">
      {events.map(e => (
        <li key={e.id} className="flex gap-3 border-l border-border pl-4 pb-3">
          <span className="text-xl" aria-hidden>{ICONS[e.event_type] ?? "•"}</span>
          <div>
            <div className="text-sm font-medium">{e.summary ?? e.event_type}</div>
            <div className="text-xs text-muted-foreground">
              {formatDistanceToNow(new Date(e.occurred_at), { addSuffix: true })}
              {" · "}
              <code>{e.event_type}</code>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/swing/idea-timeline.tsx
git commit -m "feat(swing): add idea timeline component"
```

---

## Task 16: Chart gallery + upload dropzone

**Files:**
- Create: `frontend/src/components/swing/chart-gallery.tsx`
- Create: `frontend/src/components/swing/chart-upload-dropzone.tsx`

- [ ] **Step 1: Implement gallery with tabs + lightbox**

```tsx
// frontend/src/components/swing/chart-gallery.tsx
"use client";
import { useState } from "react";
import Image from "next/image";
import { useSwingCharts } from "@/hooks/use-swing-charts";
import type { SwingChart } from "@/lib/swing-types";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ChartUploadDropzone } from "./chart-upload-dropzone";

const TFS = ["daily", "weekly", "60m", "annotated", "uploads"] as const;
type TF = (typeof TFS)[number];

function chartMatchesTab(c: SwingChart, tab: TF): boolean {
  if (tab === "uploads") return c.source === "tradingview-upload" || c.source === "user-markup";
  if (tab === "annotated") return c.timeframe === "annotated" || c.source === "claude-annotated";
  return c.timeframe === tab;
}

export function ChartGallery({ ideaId }: { ideaId: string }) {
  const { charts, mutate } = useSwingCharts(ideaId);
  const [lightbox, setLightbox] = useState<SwingChart | null>(null);

  return (
    <div className="space-y-4">
      <ChartUploadDropzone ideaId={ideaId} onUploaded={() => mutate()} />
      <Tabs defaultValue="daily">
        <TabsList>{TFS.map(t => <TabsTrigger key={t} value={t}>{t}</TabsTrigger>)}</TabsList>
        {TFS.map(tab => (
          <TabsContent key={tab} value={tab}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {charts.filter(c => chartMatchesTab(c, tab)).map(c => (
                <button key={c.id} onClick={() => setLightbox(c)} className="overflow-hidden rounded border">
                  <Image src={c.thumbnail_url ?? c.image_url} alt={c.caption ?? c.timeframe} width={360} height={240} className="h-auto w-full" />
                  {c.caption && <div className="p-1 text-xs text-muted-foreground">{c.caption}</div>}
                </button>
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>
      {lightbox && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={() => setLightbox(null)}>
          <Image src={lightbox.image_url} alt={lightbox.caption ?? ""} width={1600} height={1000} className="max-h-full max-w-full object-contain" />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implement dropzone using Vercel Blob client-upload**

```tsx
// frontend/src/components/swing/chart-upload-dropzone.tsx
"use client";
import { useState } from "react";
import { upload } from "@vercel/blob/client";
import { toast } from "sonner";

type Props = {
  ideaId?: string;
  eventId?: number;
  modelBookId?: string;
  onUploaded?: () => void;
};

export function ChartUploadDropzone({ ideaId, eventId, modelBookId, onUploaded }: Props) {
  const [busy, setBusy] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    try {
      const newBlob = await upload(`swing-charts/${Date.now()}-${file.name}`, file, {
        access: "public",
        handleUploadUrl: "/api/swing/blob/upload-token",
      });
      // Detect timeframe from filename hint or default to 'daily'
      const lower = file.name.toLowerCase();
      const timeframe =
        lower.includes("weekly") ? "weekly" :
        lower.includes("60") ? "60m" :
        lower.includes("annotated") ? "annotated" : "daily";

      const r = await fetch("/api/swing/charts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url: newBlob.url, timeframe,
          source: "tradingview-upload",
          idea_id: ideaId, event_id: eventId, model_book_id: modelBookId,
        }),
      });
      if (!r.ok) throw new Error((await r.json()).detail ?? "upload failed");
      toast.success("Chart uploaded");
      onUploaded?.();
    } catch (e) {
      toast.error(`Upload failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <label className="flex cursor-pointer items-center justify-center rounded border-2 border-dashed border-border p-6 text-sm text-muted-foreground hover:bg-muted/40">
      <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
             disabled={busy}
             onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
      {busy ? "Uploading…" : "Drop a chart image, or click to browse"}
    </label>
  );
}
```

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build 2>&1 | tail -10
git add frontend/src/components/swing/chart-gallery.tsx frontend/src/components/swing/chart-upload-dropzone.tsx
git commit -m "feat(swing): add chart gallery with tabs, lightbox, and Vercel Blob dropzone"
```

---

## Task 17: Idea action dialogs — Note / Invalidate / Promote to Model Book

**Files:**
- Create: `frontend/src/components/swing/note-dialog.tsx`
- Create: `frontend/src/components/swing/invalidate-dialog.tsx`
- Create: `frontend/src/components/swing/promote-model-book-dialog.tsx`
- Create: `frontend/src/components/swing/idea-actions.tsx`

- [ ] **Step 1: Note dialog — writes `user_note` event**

```tsx
// frontend/src/components/swing/note-dialog.tsx
"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export function NoteDialog({ ideaId, onSaved }: { ideaId: string; onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const r = await fetch(`/api/swing/ideas/${ideaId}/events`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: "user_note", summary: text, payload: { text } }),
      });
      if (!r.ok) throw new Error((await r.json()).detail ?? "failed");
      toast.success("Note added"); setOpen(false); setText(""); onSaved?.();
    } catch (e) { toast.error(`Failed: ${(e as Error).message}`); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button variant="outline">Add Note</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Add note</DialogTitle></DialogHeader>
        <Textarea value={text} onChange={e => setText(e.target.value)} placeholder="Observation, concern, pivot…" rows={5} />
        <Button onClick={save} disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save"}</Button>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Invalidate + Promote dialogs (same shape)**

```tsx
// frontend/src/components/swing/invalidate-dialog.tsx
"use client";
// …same structure; POSTs event_type="invalidation" and PATCHes idea status='invalidated'
```

```tsx
// frontend/src/components/swing/promote-model-book-dialog.tsx
"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import type { SwingIdea } from "@/lib/swing-types";

export function PromoteModelBookDialog({ idea, onSaved }: { idea: SwingIdea; onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(`${idea.ticker} ${idea.setup_kell} ${new Date().getFullYear()}`);
  const [narrative, setNarrative] = useState("");
  const [takeaways, setTakeaways] = useState("");
  const [outcome, setOutcome] = useState<"winner" | "loser" | "example" | "missed">("example");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const r = await fetch("/api/swing/model-book", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title, ticker: idea.ticker, setup_kell: idea.setup_kell, outcome,
          source_idea_id: idea.id, narrative,
          key_takeaways: takeaways.split("\n").map(s => s.trim()).filter(Boolean),
        }),
      });
      if (!r.ok) throw new Error((await r.json()).detail ?? "failed");
      toast.success("Added to Model Book"); setOpen(false); onSaved?.();
    } catch (e) { toast.error(`Failed: ${(e as Error).message}`); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Promote to Model Book</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Promote to Model Book</DialogTitle></DialogHeader>
        <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" />
        <select value={outcome} onChange={e => setOutcome(e.target.value as typeof outcome)} className="rounded border px-2 py-1">
          <option value="winner">Winner</option>
          <option value="loser">Loser</option>
          <option value="example">Example</option>
          <option value="missed">Missed</option>
        </select>
        <Textarea value={narrative} onChange={e => setNarrative(e.target.value)} placeholder="Narrative — what happened, why it worked/failed" rows={5} />
        <Textarea value={takeaways} onChange={e => setTakeaways(e.target.value)} placeholder="Key takeaways (one per line)" rows={4} />
        <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Promote"}</Button>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Unified actions bar**

```tsx
// frontend/src/components/swing/idea-actions.tsx
"use client";
import type { SwingIdea } from "@/lib/swing-types";
import { NoteDialog } from "./note-dialog";
import { InvalidateDialog } from "./invalidate-dialog";
import { PromoteModelBookDialog } from "./promote-model-book-dialog";

export function IdeaActions({ idea, onChanged }: { idea: SwingIdea; onChanged?: () => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      <NoteDialog ideaId={idea.id} onSaved={onChanged} />
      <InvalidateDialog idea={idea} onSaved={onChanged} />
      <PromoteModelBookDialog idea={idea} onSaved={onChanged} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/swing/note-dialog.tsx frontend/src/components/swing/invalidate-dialog.tsx frontend/src/components/swing/promote-model-book-dialog.tsx frontend/src/components/swing/idea-actions.tsx
git commit -m "feat(swing): add idea action dialogs (note/invalidate/promote)"
```

---

## Task 18: Complete the idea detail page

**Files:**
- Modify: `frontend/src/app/swing-ideas/[id]/page.tsx` (Plan 3 created the shell with thesis)

- [ ] **Step 1: Add Timeline / Charts / Fundamentals / Actions sections**

```tsx
// frontend/src/app/swing-ideas/[id]/page.tsx — replace/extend Plan 3's shell
"use client";
import { use } from "react";
import { useSwingIdeaDetail } from "@/hooks/use-swing-idea-detail";   // from Plan 3
import { IdeaTimeline } from "@/components/swing/idea-timeline";
import { ChartGallery } from "@/components/swing/chart-gallery";
import { IdeaActions } from "@/components/swing/idea-actions";
import { ThesisPanel } from "@/components/swing/thesis-panel";        // from Plan 3

export default function IdeaDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { idea, isLoading, mutate } = useSwingIdeaDetail(id);

  if (isLoading || !idea) return <div className="p-6">Loading…</div>;

  return (
    <div className="container mx-auto max-w-5xl space-y-6 py-6">
      <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-background/95 pb-4 backdrop-blur">
        <div>
          <h1 className="text-2xl font-bold">{idea.ticker}</h1>
          <div className="text-sm text-muted-foreground">
            {idea.cycle_stage} · {idea.status} · confluence {idea.confluence_score}/10
          </div>
        </div>
        <IdeaActions idea={idea} onChanged={() => mutate()} />
      </header>

      <section id="thesis">
        <h2 className="mb-2 text-lg font-semibold">Thesis</h2>
        <ThesisPanel idea={idea} onUpdated={() => mutate()} />
      </section>

      <section id="timeline">
        <h2 className="mb-2 text-lg font-semibold">Timeline</h2>
        <IdeaTimeline ideaId={idea.id} />
      </section>

      <section id="charts">
        <h2 className="mb-2 text-lg font-semibold">Charts</h2>
        <ChartGallery ideaId={idea.id} />
      </section>

      <section id="fundamentals">
        <h2 className="mb-2 text-lg font-semibold">Fundamentals</h2>
        <dl className="grid grid-cols-2 gap-y-1 text-sm">
          {Object.entries(idea.fundamentals ?? {}).map(([k, v]) => (
            <div key={k} className="contents"><dt className="text-muted-foreground">{k}</dt><dd>{String(v)}</dd></div>
          ))}
          {idea.next_earnings_date && <>
            <dt className="text-muted-foreground">Next earnings</dt>
            <dd>{idea.next_earnings_date}</dd>
          </>}
          {idea.beta != null && <>
            <dt className="text-muted-foreground">Beta</dt><dd>{idea.beta}</dd>
          </>}
          {idea.avg_daily_dollar_volume != null && <>
            <dt className="text-muted-foreground">Avg $ volume</dt>
            <dd>${(idea.avg_daily_dollar_volume / 1e6).toFixed(1)}M</dd>
          </>}
        </dl>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Build + commit**

```bash
cd frontend && npm run build 2>&1 | tail -10
git add frontend/src/app/swing-ideas/[id]/page.tsx
git commit -m "feat(swing): complete idea detail page with timeline/charts/fundamentals/actions"
```

---

## Task 19: Exited tab

**Files:**
- Create: `frontend/src/components/swing/exited-list.tsx`
- Modify: `frontend/src/app/swing-ideas/page.tsx` — wire Exited tab

- [ ] **Step 1: Implement exited list**

```tsx
// frontend/src/components/swing/exited-list.tsx
"use client";
import Link from "next/link";
import { useSwingIdeas } from "@/hooks/use-swing-ideas";
import { PromoteModelBookDialog } from "./promote-model-book-dialog";

export function ExitedList() {
  const { ideas, isLoading } = useSwingIdeas({ status: ["exited", "invalidated"] });
  if (isLoading) return <div>Loading…</div>;
  if (!ideas.length) return <div className="text-muted-foreground">No exited or invalidated ideas yet.</div>;
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-left text-muted-foreground">
        <th>Ticker</th><th>Setup</th><th>Outcome</th><th>R</th><th>Reason</th><th></th>
      </tr></thead>
      <tbody>
        {ideas.map(i => (
          <tr key={i.id} className="border-t">
            <td><Link href={`/swing-ideas/${i.id}`} className="font-medium hover:underline">{i.ticker}</Link></td>
            <td>{i.setup_kell}</td>
            <td>{i.status === "exited" ? "Exited" : "Invalidated"}</td>
            <td>{i.r_multiple != null ? `${i.r_multiple.toFixed(2)}R` : "—"}</td>
            <td className="max-w-xs truncate">{i.invalidated_reason ?? ""}</td>
            <td><PromoteModelBookDialog idea={i} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**Note**: `r_multiple` may not be on `swing_ideas` (it's on `swing_model_book`). Leave `"—"` unless Plan 3 or a trade-log flow populates it. If Plan 3 didn't add `status: ["exited","invalidated"]` filter to the hook, extend `useSwingIdeas` to accept an array.

- [ ] **Step 2: Wire tab in `/swing-ideas/page.tsx`**

Replace "Coming Soon" placeholder:

```tsx
<TabsContent value="exited"><ExitedList /></TabsContent>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/swing/exited-list.tsx frontend/src/app/swing-ideas/page.tsx
git commit -m "feat(swing): add Exited tab"
```

---

## Task 20: Model Book tab + detail page

**Files:**
- Create: `frontend/src/components/swing/model-book-grid.tsx`
- Create: `frontend/src/components/swing/model-book-card.tsx`
- Create: `frontend/src/components/swing/model-book-form.tsx`
- Create: `frontend/src/app/swing-ideas/model-book/[id]/page.tsx`
- Modify: `frontend/src/app/swing-ideas/page.tsx` — wire Model Book tab

- [ ] **Step 1: Card + grid**

```tsx
// frontend/src/components/swing/model-book-card.tsx
"use client";
import Link from "next/link";
import Image from "next/image";
import type { SwingModelBookEntry } from "@/lib/swing-types";

export function ModelBookCard({ entry, previewChartUrl }: { entry: SwingModelBookEntry; previewChartUrl?: string | null }) {
  return (
    <Link href={`/swing-ideas/model-book/${entry.id}`} className="block overflow-hidden rounded border hover:shadow">
      {previewChartUrl && <Image src={previewChartUrl} alt={entry.title} width={400} height={250} className="h-40 w-full object-cover" />}
      <div className="p-3">
        <div className="text-sm font-semibold">{entry.ticker} · {entry.setup_kell}</div>
        <div className="line-clamp-2 text-sm text-muted-foreground">{entry.title}</div>
        <div className="mt-1 flex gap-2 text-xs">
          <span className={`rounded px-2 py-0.5 ${entry.outcome === "winner" ? "bg-green-100" : entry.outcome === "loser" ? "bg-red-100" : "bg-muted"}`}>{entry.outcome}</span>
          {entry.r_multiple != null && <span>{entry.r_multiple.toFixed(2)}R</span>}
        </div>
      </div>
    </Link>
  );
}
```

```tsx
// frontend/src/components/swing/model-book-grid.tsx
"use client";
import { useState } from "react";
import { useSwingModelBook } from "@/hooks/use-swing-model-book";
import { ModelBookCard } from "./model-book-card";

export function ModelBookGrid() {
  const [setup, setSetup] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("");
  const { entries, isLoading } = useSwingModelBook({ setup_kell: setup || undefined, outcome: outcome || undefined });

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <select value={setup} onChange={e => setSetup(e.target.value)} className="rounded border px-2 py-1">
          <option value="">All setups</option>
          <option value="wedge_pop">Wedge Pop</option>
          <option value="ema_crossback">EMA Crossback</option>
          <option value="base_n_break">Base-n-Break</option>
          <option value="reversal_extension">Reversal Extension</option>
          <option value="post_eps_flag">Post-EPS Flag</option>
        </select>
        <select value={outcome} onChange={e => setOutcome(e.target.value)} className="rounded border px-2 py-1">
          <option value="">All outcomes</option>
          <option value="winner">Winner</option>
          <option value="loser">Loser</option>
          <option value="example">Example</option>
          <option value="missed">Missed</option>
        </select>
      </div>
      {isLoading ? <div>Loading…</div> :
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {entries.map(e => <ModelBookCard key={e.id} entry={e} />)}
        </div>}
    </div>
  );
}
```

- [ ] **Step 2: Detail page**

```tsx
// frontend/src/app/swing-ideas/model-book/[id]/page.tsx
"use client";
import { use } from "react";
import { useSwingModelBookEntry } from "@/hooks/use-swing-model-book";
import { ChartGallery } from "@/components/swing/chart-gallery";

export default function ModelBookDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { entry, isLoading } = useSwingModelBookEntry(id);
  if (isLoading || !entry) return <div className="p-6">Loading…</div>;
  return (
    <div className="container mx-auto max-w-4xl space-y-6 py-6">
      <header>
        <h1 className="text-2xl font-bold">{entry.title}</h1>
        <div className="text-sm text-muted-foreground">{entry.ticker} · {entry.setup_kell} · {entry.outcome}</div>
      </header>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Narrative</h2>
        <p className="whitespace-pre-wrap">{entry.narrative ?? "—"}</p>
      </section>
      {entry.key_takeaways?.length ? (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Key takeaways</h2>
          <ul className="list-disc pl-6">{entry.key_takeaways.map((k, i) => <li key={i}>{k}</li>)}</ul>
        </section>
      ) : null}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Charts</h2>
        {/* ChartGallery is currently idea-scoped; for model-book use the model-book variant */}
        <ChartGalleryForOwner modelBookId={entry.id} />
      </section>
    </div>
  );
}
```

Add a tiny variant (or a prop) to `chart-gallery.tsx` that accepts `modelBookId` instead of `ideaId` and uses `/api/swing/model-book/[id]/charts`. Easiest path: add an optional `modelBookId` prop to `ChartGallery` and branch the fetch URL.

- [ ] **Step 3: Wire Model Book tab**

```tsx
// frontend/src/app/swing-ideas/page.tsx
<TabsContent value="model-book"><ModelBookGrid /></TabsContent>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/swing/model-book-grid.tsx frontend/src/components/swing/model-book-card.tsx frontend/src/app/swing-ideas/model-book/ frontend/src/app/swing-ideas/page.tsx
git commit -m "feat(swing): add Model Book grid + detail page"
```

---

## Task 21: Weekly tab

**Files:**
- Create: `frontend/src/components/swing/weekly-list.tsx`
- Modify: `frontend/src/app/swing-ideas/page.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/swing/weekly-list.tsx
"use client";
import { useSwingWeekly } from "@/hooks/use-swing-weekly";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

export function WeeklyList() {
  const { weeks, isLoading } = useSwingWeekly();
  if (isLoading) return <div>Loading…</div>;
  if (!weeks.length) return <div className="text-muted-foreground">No weekly syntheses yet.</div>;
  return (
    <div className="space-y-3">
      {weeks.map((w, i) => (
        <Collapsible key={w.week_of} defaultOpen={i === 0}>
          <CollapsibleTrigger className="w-full text-left font-medium">Week of {w.week_of} · {w.entries.length} ideas</CollapsibleTrigger>
          <CollapsibleContent className="space-y-2 pt-2">
            {w.entries.map(e => (
              <div key={e.idea_id} className="rounded border p-3">
                <div className="text-sm font-semibold">{e.ticker} · {e.cycle_stage} · {e.status}</div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{e.claude_analysis ?? "—"}</p>
              </div>
            ))}
          </CollapsibleContent>
        </Collapsible>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Wire + commit**

```bash
# in swing-ideas/page.tsx:
<TabsContent value="weekly"><WeeklyList /></TabsContent>
```

```bash
git add frontend/src/components/swing/weekly-list.tsx frontend/src/app/swing-ideas/page.tsx
git commit -m "feat(swing): add Weekly tab"
```

---

## Task 22: `/swing-deep-analyze` Claude Code skill (Mac)

**Files:**
- Create: `.claude/skills/swing-deep-analyze.md`

This is a **markdown template** — it's a skill, not code. It's read by Claude Code and the scheduled-tasks MCP.

- [ ] **Step 1: Write skill**

```markdown
# .claude/skills/swing-deep-analyze.md
---
description: Deep swing analysis — Claude-in-Chrome on Deepvue for top-10 active ideas. Scheduled 2:30pm PT weekdays via scheduled-tasks MCP.
trigger_phrases:
  - /swing-deep-analyze
  - deep analyze swing ideas
required_mcps:
  - Claude-in-Chrome
  - computer-use   # for app-foregrounding precheck
---

# /swing-deep-analyze

## Goal
For each of the top-10 active swing ideas (by confluence_score, excluding ideas whose deep_thesis_at < 24h old), capture daily/weekly/60m charts from Deepvue, scrape the data panel, and POST an updated snapshot with `claude_analysis`, chart URLs, and `deepvue_panel` to Railway.

## Preflight (abort if any fails)

1. Screenshot the desktop. Is Chrome running and frontmost (or background)? If not:
   - Slack `#swing-alerts`: "🚫 Deep analyze aborted: Chrome not running. Please open Chrome → Deepvue → login, then run `/swing-deep-analyze` manually."
   - Exit.

2. Use `Claude-in-Chrome.tabs_context_mcp` to list tabs. Is there a tab with URL matching `deepvue.com`? If not:
   - Slack: "🚫 Deep analyze aborted: Deepvue tab not open."
   - Exit.

3. `Claude-in-Chrome.get_page_text` on the Deepvue tab. Search for a logged-in-only marker (e.g., "Logout" link or user avatar text). If missing, assume logged out:
   - Slack: "🚫 Deep analyze aborted: not logged into Deepvue."
   - Exit.

4. If the Claude-in-Chrome extension is deferred-loaded, request schemas first via ToolSearch (`query: "Claude-in-Chrome", max_results: 30`).

## Load top-10 ideas

```
GET https://$RAILWAY_API_URL/api/swing/ideas?status_in=watching,triggered,adding,trailing&order=-confluence_score&limit=20
```

Filter client-side to ideas where `deep_thesis_at` is null or older than 24h. Take top 10.

## For each ticker (serial; sleep 10s between)

1. Navigate Deepvue to the ticker chart: `https://deepvue.com/charts/<TICKER>` (exact URL to be confirmed on first run).
2. Set timeframe = Daily. Wait 2s for render. Screenshot via Claude-in-Chrome. Upload to Vercel Blob via `POST /api/swing/blob/upload-token` flow (use the fetch/blob client pattern). Capture URL.
3. Set timeframe = Weekly. Screenshot + upload → capture URL.
4. Set timeframe = 60min. Screenshot + upload → capture URL.
5. Use `get_page_text` on the data panel sidebar. Parse into a dict (key metrics — rev growth, EPS, float, RS, etc.). If parse fails, store raw text.
6. `GET /api/swing/ideas/<id>/snapshots?limit=5` — pull recent history.
7. Claude analyzes: given thesis + 3 charts + data panel + recent snapshots, write a 3-paragraph analysis. Sections:
   - What the chart is showing vs last snapshot (daily action, any cycle-stage inference)
   - What the data panel adds (fundamentals/theme strength)
   - Next action: wait / add / trim / exit — with reasoning.
8. POST to Railway:

```
POST /api/swing/ideas/<id>/snapshots
Authorization: Bearer $SWING_API_TOKEN
Content-Type: application/json

{
  "snapshot_date": "<today ISO>",
  "snapshot_type": "daily",
  "claude_analysis": "<the 3 paragraphs>",
  "claude_model": "claude-opus-4-7",
  "chart_daily_url": "<blob url>",
  "chart_weekly_url": "<blob url>",
  "chart_60m_url": "<blob url>",
  "deepvue_panel": { ... parsed panel ... },
  "analysis_sources": { "deepvue_url": "..." }
}
```

Also POST `deep_thesis` via `POST /api/swing/ideas/<id>/thesis { layer: "deep", ... }` (Plan 3 endpoint).

9. Sleep 10 seconds before the next ticker (to avoid hammering Deepvue and to pace Max rate limits).

## Final Slack message

"✅ Deep analysis complete: N ideas analyzed, M exhaustion warnings reviewed, K ready-to-add."

## Failure modes

- Screenshot fails: skip this timeframe but continue with other 2.
- Data panel scrape fails: proceed with only chart analysis; note in `analysis_sources`.
- Max rate limit hit mid-run: abort, Slack the count completed, leave remaining ideas for next run.
- Railway 5xx: retry once with backoff; if still failing, Slack the error.

## Non-goals

- Don't invent new ideas here — only analyze already-active ones. New-idea creation is the pre-market detection pipeline's job.
- Don't touch `swing_ideas.status` from this skill (except via thesis POST which doesn't change status).
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/swing-deep-analyze.md
git commit -m "feat(swing): add /swing-deep-analyze Claude Code skill"
```

---

## Task 23: `/swing-weekly-synth` skill (Mac)

**Files:**
- Create: `.claude/skills/swing-weekly-synth.md`

- [ ] **Step 1: Write skill**

```markdown
# .claude/skills/swing-weekly-synth.md
---
description: Sunday 5pm PT weekly swing synthesis — per-idea reviews + theme clustering + journal append. Runs AFTER weekend-refresh universe cron at 4:30pm PT.
trigger_phrases:
  - /swing-weekly-synth
  - weekly swing synthesis
---

# /swing-weekly-synth

## Preflight

Quick sanity: `GET /api/swing/universe?source=latest` — confirm universe resolved (either fresh Deepvue or backend-refreshed). If empty:
- Slack: "🚫 Weekly synth aborted: empty universe."
- Exit.

## Step 1: Per-active-idea synthesis

For each idea with status in ('watching','triggered','adding','trailing'):

1. `GET /api/swing/ideas/<id>` + `GET /api/swing/ideas/<id>/snapshots?limit=5` + `GET /api/swing/ideas/<id>/events?event_type=user_note`
2. Compose a ~150-word synthesis covering:
   - How price evolved vs last week's setup
   - Stage transitions (if any)
   - Any exhaustion warnings
   - Change in thesis strength (improving/deteriorating/unchanged) and why
   - Next-week watch criteria
3. `POST /api/swing/ideas/<id>/snapshots` with:
   ```
   { "snapshot_date": "<Sunday ISO>", "snapshot_type": "weekly",
     "claude_analysis": "<the 150 words>", "claude_model": "claude-opus-4-7" }
   ```

## Step 2: Closed-idea retrospectives

For ideas closed (status exited|invalidated) in the last 7 days:
1. Gather full timeline (detection → transitions → exit).
2. Generate a "what went right/wrong + takeaway" retrospective (~100 words).
3. POST as `event_type=user_note` with `summary="Retrospective"` and the text in `payload.text`.
4. Offer model-book promotion: Slack DM with ticker + setup + outcome + link to `/swing-ideas/[id]` with auto-opened Promote dialog hint.

## Step 3: Theme clustering

1. `GET /api/swing/universe` → pull `extras` sector/theme tags for each ticker.
2. Join with active idea tickers.
3. Group by theme → list tickers per theme with their stages.
4. Identify rotation: which themes gained/lost membership week-over-week (compare to last Sunday's theme map — store in a lightweight `swing_weekly_themes` JSONB blob on the latest weekly snapshot, or skip and regenerate fresh each time for MVP).

## Step 4: Journal append

Invoke existing `/journal` command with a structured block:

```markdown
## Weekly Swing Review — <date>

### Themes
- **AI/Semis**: NVDA (trailing), AMD (triggered), AVGO (watching)
- **Cybersec**: CRWD (trailing), PANW (watching)
- ...

### Active ideas — quick read
- NVDA: <1-sentence thesis change>
- AMD: <1-sentence>
- ...

### Closed this week
- XYZ (+2.3R, winner): <1-sentence>
- ABC (invalidated): <1-sentence>

### Next week's focus
- <2-3 bullets>
```

## Step 5: Slack digest

Post to `#swing-alerts`:

```
:books: *Weekly Swing Review* — <date>
• Active: N ideas
• Closed: K wins, M losses
• Top theme: <e.g. AI/Semis>
• Full review: <link to /swing-ideas?tab=weekly>
```

## Failure modes

- Max rate limit: pause, abort with Slack msg + count completed.
- Journal command not available: persist synthesis via `/note` commands or skip append and Slack the raw text.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/swing-weekly-synth.md
git commit -m "feat(swing): add /swing-weekly-synth Claude Code skill"
```

---

## Task 24: `/swing-model-book-add` skill (Mac) — manual historical entries

**Files:**
- Create: `.claude/skills/swing-model-book-add.md`

- [ ] **Step 1: Write skill**

```markdown
# .claude/skills/swing-model-book-add.md
---
description: Manually add a historical exemplary setup to the model book. Ad-hoc.
trigger_phrases:
  - /swing-model-book-add
---

# /swing-model-book-add

Args: free-form. Typical invocation:
- `/swing-model-book-add NVDA base_n_break 2024-03-15`
- `/swing-model-book-add` (no args → interactive)

## Steps

1. Parse args (ticker, setup, approximate date). If missing, ask user.
2. Pull historical chart via yfinance + a local plotter helper (or direct user to upload from TradingView). MVP path: ask user to paste TradingView screenshot URLs — skip autocapture.
3. Pull historical fundamentals via yfinance (rev growth trend at the time of the setup).
4. Ask user for:
   - Title (default: `<TICKER> <setup> <YYYY>`)
   - Outcome (winner/loser/example/missed)
   - R-multiple (if known)
   - Narrative (~100 words — what made it work/fail)
   - Key takeaways (bulleted)
   - Tags
5. `POST /api/swing/model-book` with all fields.
6. If user pasted chart URLs: for each, `POST /api/swing/charts` with `model_book_id` set.
7. Confirm: "✅ Added to Model Book — <link>".
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/swing-model-book-add.md
git commit -m "feat(swing): add /swing-model-book-add Claude Code skill"
```

---

## Task 25: Integration smoke test — full postmarket loop

**Files:**
- Create: `tests/swing/test_postmarket_integration.py`

- [ ] **Step 1: Write integration test exercising the pipeline + endpoint together**

```python
# tests/swing/test_postmarket_integration.py
"""End-to-end: seed active idea → call postmarket endpoint → verify snapshot + event + Slack call."""
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
import pandas as pd
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch.dict("os.environ", {"SWING_API_TOKEN": "t"})
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.endpoints.swing_postmarket._get_supabase")
def test_full_postmarket_loop_writes_snapshot_and_exhaustion(
    mock_sb, mock_bars, mock_slack,
):
    sb = FakeSupabaseClient()
    idea_id = str(uuid4())
    sb.table("swing_ideas").insert([{
        "id": idea_id, "ticker": "NVDA", "status": "triggered",
        "cycle_stage": "base_n_break", "stop_price": 50.0,
        "setup_kell": "base_n_break", "direction": "long",
        "risk_flags": {},
    }])
    # Far-above-10ema to trigger exhaustion
    closes = [100.0] * 50 + [200.0]
    n = len(closes)
    mock_bars.return_value = pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": [c * 0.995 for c in closes], "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes, "volume": [1_000_000] * n,
    })
    mock_sb.return_value = sb

    client = TestClient(app)
    r = client.post("/api/swing/pipeline/postmarket", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    body = r.json()
    assert body["active_ideas_processed"] == 1
    assert body["exhaustion_warnings"] == 1
    assert body["snapshots_written"] == 1
    assert mock_slack.called

    assert sb.table("swing_ideas").rows[0]["risk_flags"]["far_above_10ema"] is True
    assert any(e["event_type"] == "exhaustion_warning" for e in sb.table("swing_events").rows)
```

- [ ] **Step 2: Run + commit**

```bash
.venv/bin/python -m pytest tests/swing/test_postmarket_integration.py -v
git add tests/swing/test_postmarket_integration.py
git commit -m "test(swing): add end-to-end postmarket integration test"
```

---

## Task 26: Manual Slack → "Add to Model Book" button (deferred — optional if time permits)

The spec mentions a Slack button on idea-exit messages that opens a pre-filled form. Building Slack interactivity is non-trivial (requires action-endpoint URL, signature verification, etc.).

- [ ] **Step 1: Decide MVP scope**

For Plan 4 MVP, link the Slack exit message to `/swing-ideas/[id]?openPromote=1` and have the idea detail page auto-open `PromoteModelBookDialog` when that query param is present. Full Slack button block kit is deferred.

- [ ] **Step 2: Implement the auto-open query-param**

In `frontend/src/app/swing-ideas/[id]/page.tsx`, read `useSearchParams()` and programmatically open the promote dialog if `openPromote=1`.

- [ ] **Step 3: In `api/indicators/swing/pipeline/slack.py`, format stop-out messages**

```python
def format_stop_out_message(idea: dict, base_url: str) -> str:
    return (f":octagonal_sign: *Stopped out*: {idea['ticker']} ({idea['setup_kell']})\n"
            f"<{base_url}/swing-ideas/{idea['id']}?openPromote=1|Add to Model Book>")
```

- [ ] **Step 4: Commit**

```bash
git add api/indicators/swing/pipeline/slack.py frontend/src/app/swing-ideas/[id]/page.tsx
git commit -m "feat(swing): link Slack stop-out messages to auto-open promote dialog"
```

---

## Task 27: Verify end-to-end + update `docs/schema/`

**Files:**
- Optional: `docs/schema/NNN_swing_postmarket_notes.md` (only if any schema drift introduced)

- [ ] **Step 1: Full test sweep**

```bash
cd /Users/krishnaeedula/claude/coding/trend-trading-mcp
.venv/bin/python -m pytest tests/swing/ -v
```

Expected: all passing (including Plan 1/2/3 tests plus all Plan 4 additions).

- [ ] **Step 2: Verify no Claude SDK on Railway**

```bash
grep -R "^from anthropic\|^import anthropic" api/ | grep -v tests/
```

Expected: empty.

- [ ] **Step 3: Verify Vercel cron count = 2**

```bash
grep -c '"path"' frontend/vercel.json
```

Expected: `2`.

- [ ] **Step 4: Frontend build**

```bash
cd frontend && npm run build
```

Expected: clean build, no TS errors.

- [ ] **Step 5: Commit any docs updates**

```bash
git add docs/schema/
git commit -m "docs(swing): Plan 4 schema notes (if any)" --allow-empty
```

---

## Definition of Done

All the following must be green before Plan 4 is declared complete:

- [ ] `run_swing_postmarket_snapshot()` processes every active idea, handles stop violations, writes exhaustion warnings with `risk_flags`, and is idempotent on re-runs.
- [ ] `POST /api/swing/pipeline/postmarket` and `POST /api/swing/pipeline/universe-refresh` are live, bearer-protected, and the `daily-dispatcher` calls the former at 21:00 UTC.
- [ ] `frontend/vercel.json` has exactly 2 cron entries: `daily-dispatcher` and `weekend-refresh`.
- [ ] `/api/swing/ideas/<id>/snapshots` GET + POST work; Mac-side POST with `claude_analysis` preserves price fields.
- [ ] `/api/swing/ideas/<id>/charts`, `/api/swing/events/<id>/charts`, `/api/swing/model-book/<id>/charts` accept chart records; the "exactly one owner" check is enforced server-side and by DB.
- [ ] `/api/swing/model-book` supports list, get, create, patch, delete — all protected for writes.
- [ ] `/api/swing/weekly` groups weekly snapshots by week.
- [ ] `/swing-ideas` page shows Active / Watching / Exited / Universe / Model Book / Weekly tabs all live (no "Coming Soon").
- [ ] `/swing-ideas/[id]` shows Thesis (from Plan 3), Timeline, Charts, Fundamentals, and Actions sections.
- [ ] Chart upload via Vercel Blob works end-to-end: drag → Blob URL → Railway record → appears in gallery.
- [ ] `/swing-deep-analyze`, `/swing-weekly-synth`, `/swing-model-book-add` markdown skills exist in `.claude/skills/`.
- [ ] All `tests/swing/*` pass.
- [ ] No `from anthropic`/`import anthropic` in `api/` (excluding `tests/`).
- [ ] `frontend/npm run build` is clean.
- [ ] Manual smoke test (post-Plan 4 merge): run `curl -X POST $RAILWAY/api/swing/pipeline/postmarket -H "Authorization: Bearer $SWING_API_TOKEN"` against a dev DB with one seeded active idea — returns 200 and writes a snapshot.

---

## Out of Scope (explicit deferrals)

- **Trade execution + P&L tracking** — no `swing_trades` table, no pyramid-add calculator, no automatic R-multiple computation on idea exit. `PATCH /api/swing/ideas/<id>` with a manual `r_multiple` field is acceptable until the trades plan is written.
- **Shorts / down-cycle setups** — Wedge Drop, downside EMA Crossback, downside Base-n-Break, topping Reversal Extension not implemented. Schema allows `direction='short'` but no detectors fire.
- **Backtesting** — no vectorbt historical validation of detectors or Exhaustion Extension rules.
- **Slack Block Kit interactivity** — the "Add to Model Book" Slack button is a link, not a true interactive button. Full interactivity + action handler + signature verification is a follow-up.
- **Real-time intraday swing alerts** — only daily close detection; intraday price action not monitored.
- **Chart annotation in-app** — user uploads pre-annotated charts from TV/TOS/Deepvue; no drawing UI in this app.
- **Setup dismissal / mute** — no per-ticker blacklist; manage by removing from universe.
- **Blob retention policy** — charts accumulate indefinitely. A cleanup cron for > 90-day Deepvue-auto screenshots is a follow-up.
- **Closed-lid Mac scheduling** — if `scheduled-tasks` MCP can't fire on a closed-lid MacBook, fallback to `launchd` + `caffeinate` is a follow-up (see spec §8 prerequisite 1).

---

## Open Questions to Resolve During Execution

1. **`last_base_breakout_idx` lookup** — current implementation scans `swing_events` for `setup_fired` with `payload.setup_kell='base_n_break'`. Confirm Plan 2 writes this payload shape when the base-n-break detector fires. If not, the Exhaustion Extension Kell-direct branch will never trigger; either fix Plan 2's payload or look up via `swing_idea_stage_transitions` with `to_stage='base_n_break'`.
2. **Idea r_multiple column** — the Exited tab displays R-multiple but `swing_ideas` doesn't currently have it. Decide: add a nullable `r_multiple` column via a thin migration, or surface it only on model-book entries and show "—" on exited-tab rows.
3. **`useSwingIdeas({ status: [...] })` hook shape** — if Plan 3's hook only takes a single-status filter, extend it to accept an array before the Exited tab lands.
4. **Deepvue URL format** — skill Task 22 guesses `https://deepvue.com/charts/<TICKER>`. First real run may need to tune to the actual route (e.g., `https://deepvue.com/ticker/<TICKER>?panel=chart`). Plan to patch the skill after first successful run.
5. **Max rate-limit observation** — after the first full week, measure messages consumed by scheduled skills + ad-hoc; if close to 5-hour window cap, reduce top-10 to top-5 in `/swing-deep-analyze`.
6. **Multi-tenant Supabase singletons** — `functools.lru_cache(maxsize=1)` on `_get_supabase()` is copied across 5 endpoint modules. Acceptable duplication for Plan 4; consolidate into `api/clients/supabase.py` in a future refactor pass.
7. **Idempotency-Key handling** — current plan relies on natural unique keys (snapshot by `(idea_id, date, type)`, events by type+date dedupe). If we later need true replay protection for arbitrary POSTs (e.g., retried chart uploads from the Mac), add a `swing_idempotency` table.
8. **`_last_base_breakout_idx` date matching** — uses `df["date"]` direct comparison. If yfinance returns timezone-aware timestamps and events store UTC strings, may need to normalize both sides. Verify on first post-market run.
9. **Slack exit-out auto-open dialog param** — the query-param `?openPromote=1` auto-opens the dialog once. Consider also auto-clearing the param on dialog close so a browser refresh doesn't re-trigger.
