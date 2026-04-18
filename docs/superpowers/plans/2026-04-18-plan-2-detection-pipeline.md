# Plan 2 — Detection Pipeline + Pre-market Cron

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Reference Plan 1 ([docs/superpowers/plans/2026-04-18-plan-1-foundation-universe.md](./2026-04-18-plan-1-foundation-universe.md)) for conventions (Supabase `_get_supabase()` pattern, FakeSupabaseClient, `railwayFetch` proxy pattern, etc.) — all still apply.

**Goal:** Daily swing setup detection running on a Vercel cron at 6am PT, writing `swing_ideas` rows to Supabase, posting a ranked Slack digest, and making the results readable on the `/swing-ideas` Active + Watching tabs.

**Architecture:** 5 pre-market detectors (Wedge Pop, EMA Crossback, Base-n-Break, Reversal Extension, Post-EPS Flag Base) run against the active universe (from Plan 1's `swing_universe` table). Each detector is pure-Python, works on daily bars, and emits `SetupHit` objects. A shared **`api/indicators/common/`** module holds EMAs/SMAs/ATR/RS/phase-osc proxies used across detectors and later reused by Plan 4. Orchestrator wires universe → bars → indicators → detectors → confluence scoring → `swing_ideas` upserts → Slack. A **consolidated `/api/cron/daily-dispatcher`** Vercel endpoint fires at 13:00 + 21:00 UTC weekdays (per spec Section 9 and Plan 1's cron consolidation decision); 13:00 invokes swing pre-market + existing `daily-screeners`, 21:00 invokes existing `market-monitor` (and, in Plan 4, swing post-market). `vercel.json` goes from 2 single-purpose crons to 1 dispatcher + (Plan 4 adds Sunday `weekend-refresh`).

**Tech Stack:** Python 3.12, FastAPI, pandas, yfinance, supabase-py, pytest. Next.js 16 (App Router), React 19, Tailwind 4, shadcn/ui, SWR-style hooks. Slack Webhooks via existing `api/integrations/slack.py`.

**Reference:**
- Spec: [docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md](../specs/2026-04-18-kell-saty-swing-system-design.md) — particularly Section 6 (detectors), Section 9 (pipeline schedule).
- Kell source notes: [docs/kell/source-notes.md](../../kell/source-notes.md) — use for detector filter tuning.
- Plan 1 for repo conventions and test patterns.

---

## File Structure

**Backend — new:**
- `api/indicators/common/__init__.py`
- `api/indicators/common/moving_averages.py` — `ema()`, `sma()`, weekly resample helper
- `api/indicators/common/atr.py` — true-range + ATR
- `api/indicators/common/relative_strength.py` — `rs_vs_benchmark()`
- `api/indicators/common/phase_oscillator.py` — simplified Saty phase-osc for daily TF
- `api/indicators/swing/setups/__init__.py`
- `api/indicators/swing/setups/base.py` — `SetupHit` dataclass + shared helpers
- `api/indicators/swing/setups/wedge_pop.py`
- `api/indicators/swing/setups/ema_crossback.py`
- `api/indicators/swing/setups/base_n_break.py`
- `api/indicators/swing/setups/reversal_extension.py`
- `api/indicators/swing/setups/post_eps_flag.py`
- `api/indicators/swing/earnings_calendar.py` — yfinance primary + Finnhub fallback
- `api/indicators/swing/market_health.py` — QQQ green-light + index cycle stage
- `api/indicators/swing/confluence.py` — scoring + ranking
- `api/indicators/swing/pipeline.py` — `run_premarket_detection()` orchestrator
- `api/indicators/swing/slack_digest.py` — pre-market digest formatter

**Backend — modify:**
- `api/endpoints/swing.py` — add `GET /api/swing/ideas` + `GET /api/swing/ideas/{id}` endpoints
- `api/schemas/swing.py` — add `SwingIdea`, `SwingIdeaListResponse`, `SetupHitResponse` Pydantic models
- `api/main.py` — no change (router already registered)

**Backend — tests (mirror structure):**
- `tests/swing/test_common_indicators.py`
- `tests/swing/test_setups_base.py`
- `tests/swing/test_setups_wedge_pop.py`
- `tests/swing/test_setups_ema_crossback.py`
- `tests/swing/test_setups_base_n_break.py`
- `tests/swing/test_setups_reversal_extension.py`
- `tests/swing/test_setups_post_eps_flag.py`
- `tests/swing/test_earnings_calendar.py`
- `tests/swing/test_market_health.py`
- `tests/swing/test_confluence.py`
- `tests/swing/test_pipeline.py`
- `tests/swing/test_slack_digest.py`
- `tests/swing/test_ideas_endpoints.py`

**Frontend — new:**
- `frontend/src/app/api/swing/ideas/route.ts` — GET list
- `frontend/src/app/api/swing/ideas/[id]/route.ts` — GET one
- `frontend/src/app/api/cron/daily-dispatcher/route.ts` — Vercel cron entry
- `frontend/src/hooks/use-swing-ideas.ts`
- `frontend/src/components/swing/ideas-list.tsx` — shared list view for Active + Watching tabs
- `frontend/src/components/swing/market-health-bar.tsx`

**Frontend — modify:**
- `frontend/src/app/swing-ideas/page.tsx` — wire Active + Watching tabs
- `frontend/src/lib/types.ts` — append swing idea types
- `frontend/vercel.json` — consolidate 2 existing crons → 1 dispatcher cron

---

## Cross-cutting conventions (applies to every detector)

- **Detector signature:**
  ```python
  def detect(bars: pd.DataFrame, qqq_bars: pd.DataFrame, ctx: dict) -> SetupHit | None:
      """bars: daily OHLCV with 'date'/'open'/'high'/'low'/'close'/'volume' cols.
      qqq_bars: same for QQQ (for RS computation).
      ctx: {"universe_extras": {...}, "prior_ideas": [...], "today": date}."""
  ```
- **`SetupHit`** dataclass (defined in `setups/base.py`):
  ```python
  @dataclass
  class SetupHit:
      ticker: str
      setup_kell: str              # 'wedge_pop', etc.
      cycle_stage: str
      entry_zone: tuple[float, float]
      stop_price: float
      first_target: float | None
      second_target: float | None
      detection_evidence: dict
      raw_score: int               # 1-5, per-detector quality assessment
  ```
- **TDD discipline:** every detector task writes failing tests first covering: 1 happy-path bars fixture that fires, 1 fixture that fails (too few bars / below EMA / etc.), 1 fixture that asserts specific `detection_evidence` values.
- **Bars fixtures:** build synthetic `pd.DataFrame` bars. Example helper in `setups/base.py`:
  ```python
  def synth_bars(days: int, closes: list[float], volume: int = 10_000_000, start: str = "2026-01-01") -> pd.DataFrame:
      import pandas as pd
      dates = pd.date_range(start, periods=len(closes), freq="B")
      return pd.DataFrame({"date": dates, "open": closes, "high": [c * 1.01 for c in closes], "low": [c * 0.99 for c in closes], "close": closes, "volume": volume})
  ```

---

## Task 1: Shared indicator helpers (moving averages + ATR)

**Files:** `api/indicators/common/{__init__.py,moving_averages.py,atr.py}` + `tests/swing/test_common_indicators.py`.

TDD:
- [ ] Write tests asserting `ema(bars, 10)` returns a `pd.Series` length==bars, first N-1 values NaN, matching pandas' `.ewm(span=10, adjust=False).mean()`.
- [ ] Write tests for `sma(bars, 20)`.
- [ ] Write tests for `atr(bars, 14)` — true-range then 14-period RMA (Wilder's). Known-value fixture: 20 bars of high=101, low=99, close=100 → ATR stabilizes to 2.
- [ ] Write tests for `weekly_resample(daily_bars)` — Friday-close resampling, aggregates open/high/low/close/volume correctly.
- [ ] Implement. Keep each function ≤ 15 lines. Commit.

Commit msg: `feat(swing): add common indicator helpers (EMA/SMA/ATR/weekly resample)`.

---

## Task 2: Relative strength + phase oscillator proxies

**Files:** `api/indicators/common/{relative_strength.py,phase_oscillator.py}` + test appended.

- [ ] `rs_vs_benchmark(ticker_bars, benchmark_bars, lookback_days=20)` — returns a `pd.Series` of RS line (log-return spread). Test: ticker rising faster than QQQ → positive series.
- [ ] `phase_oscillator_daily(bars, fast=8, slow=21, signal=9)` — a simplified Saty-phase-osc proxy computed from MACD-style inputs. Returns `pd.Series` of oscillator values normalized to roughly [-100, +100]. Test: bars trending up → oscillator positive; bars trending down → oscillator negative; range-bound → oscillator oscillates.

**Note:** the existing intraday Saty phase-osc (`api/indicators/satyland/phase_oscillator.py`) consumes an intraday-SPY payload. This daily proxy is intentionally simpler; if later fidelity to Saty is needed, we can port. Document this in a module docstring.

Commit: `feat(swing): add RS + phase oscillator proxies for daily TF detectors`.

---

## Task 3: `SetupHit` dataclass + shared detector helpers

**File:** `api/indicators/swing/setups/base.py` + tests.

- [ ] Define `SetupHit` dataclass as above.
- [ ] Helper `volume_vs_avg(bars, lookback=20) -> float` returning current / avg ratio.
- [ ] Helper `prior_swing_high(bars, lookback=60) -> float | None`.
- [ ] Helper `prior_swing_low(bars, lookback=60) -> float | None`.
- [ ] Helper `synth_bars(days, closes, volume, start)` for test fixtures (above).
- [ ] Tests for each helper.

Commit: `feat(swing): add SetupHit dataclass + shared detector helpers`.

---

## Task 4: Wedge Pop detector

**File:** `api/indicators/swing/setups/wedge_pop.py` + tests.

**Rules (from spec Section 6.1):**
- 10-EMA slope flat over last 5 bars (|slope| < 0.2 ATR per bar)
- EMA10 / EMA20 spread < 0.5 ATR
- Higher low vs prior swing low within 15 bars, with at least one prior lower-high in last 15 bars (descending-channel context)
- RS vs QQQ positive over last 10 bars
- Today's close > both EMA10 and EMA20
- Volume on reclaim bar ≥ 1.2× avg 20-day
- **Stop:** low of reclaim bar OR low of last 3-bar consolidation, whichever is higher
- **Target:** prior swing high

**TDD:**
- [ ] Test: synthetic descending channel → 5 bars flat → breakout close > EMAs with 1.3× volume + positive RS → fires, `cycle_stage='wedge_pop'`, `raw_score >= 3`.
- [ ] Test: breakout but low volume (0.9× avg) → doesn't fire.
- [ ] Test: no prior descending structure → doesn't fire.
- [ ] Test: stop price is below reclaim bar low.
- [ ] Test: `detection_evidence` includes `{"ema10", "ema20", "ema10_slope", "rs_vs_qqq_10d", "volume_vs_20d_avg"}`.
- [ ] Implement. Keep detector ≤ 80 lines.

Commit: `feat(swing): add Wedge Pop detector with Kell-aligned filters`.

---

## Task 5: EMA Crossback detector

**File:** `api/indicators/swing/setups/ema_crossback.py` + tests.

**Rules (spec Section 6.2):**
- A prior Wedge Pop recorded on this ticker in last 30 bars — read from `ctx["prior_ideas"]` (list of `swing_ideas` rows for this ticker passed by orchestrator)
- Today's bar is a pullback to within 0.5× ATR of EMA10 or EMA20
- Low of pullback bar holds above the respected EMA (no close below)
- Volume < 0.8× avg 20-day (drying up)
- **Stop:** low of pullback bar
- **Target:** prior swing high

**TDD:**
- [ ] Test: `ctx` includes a prior Wedge Pop 10 bars ago; today's bar pullback holds above EMA10 with drying volume → fires.
- [ ] Test: no prior Wedge Pop → doesn't fire.
- [ ] Test: close below EMA10 → doesn't fire.
- [ ] Test: volume > 1× avg → doesn't fire.

Commit: `feat(swing): add EMA Crossback detector`.

---

## Task 6: Base-n-Break detector

**File:** `api/indicators/swing/setups/base_n_break.py` + tests.

**Rules (spec Section 6.3):**
- 5–8 week base = 25–40 daily bars of consolidation
- Base range (high-low)/mid-price < 15%
- Consolidation holding ABOVE both 10-EMA and 20-EMA throughout the base
- Breakout close > base high
- Volume on breakout ≥ 1.5× avg 20-day
- **Stop:** max(base_low, 20-EMA)
- **Target:** breakout + (base_high - base_low)   (measured move)

**TDD:**
- [ ] Test: 30-bar tight consolidation above MAs → breakout on 1.6× volume → fires, target == breakout + height.
- [ ] Test: base violates MAs at some point → doesn't fire.
- [ ] Test: breakout without volume → doesn't fire.
- [ ] Test: base too short (< 25 bars) → doesn't fire.

Commit: `feat(swing): add Base-n-Break detector`.

---

## Task 7: Reversal Extension detector

**File:** `api/indicators/swing/setups/reversal_extension.py` + tests.

**Rules (spec Section 6.4):**
- Proximity to higher-TF support: within 3% of 200-SMA OR of 10-week EMA OR of a weekly-base low
- Capitulation volume > 1.5× avg 20-day
- Phase oscillator reading <= -50 (oversold)
- Close stretched > 1.5× ATR below EMA10
- Bullish price/oscillator divergence over last 5-10 bars (price lower low but phase-osc higher low)
- **Stop:** below reversal bar low
- **Target:** 20-EMA (first partial only, per Kell)

**TDD:**
- [ ] Test: price at 200-SMA, heavy volume, oscillator divergence → fires.
- [ ] Test: no divergence → doesn't fire.
- [ ] Test: far from any support → doesn't fire.
- [ ] Test: second_target is None.

Commit: `feat(swing): add Reversal Extension detector`.

---

## Task 8: Earnings calendar provider

**File:** `api/indicators/swing/earnings_calendar.py` + tests.

**Contract:**
```python
def next_earnings_date(ticker: str) -> date | None: ...
def last_earnings_gap_pct(ticker: str, bars: pd.DataFrame, lookback_days: int = 10) -> float | None: ...
```

**Fallback chain:**
1. yfinance `tk.calendar` (primary, free)
2. Finnhub `/stock/earnings-calendar` (fallback, requires `FINNHUB_API_KEY` env var)
3. Return `None` if neither available

TDD:
- [ ] Mock yfinance `.calendar` to return a date → `next_earnings_date` returns it.
- [ ] Mock yfinance returning None, mock Finnhub response → returns Finnhub's date.
- [ ] Both unavailable → None.
- [ ] `last_earnings_gap_pct` scans last 10 bars for a > 5% gap up.

Commit: `feat(swing): add earnings calendar provider (yfinance + Finnhub)`.

---

## Task 9: Post-EPS Flag Base detector

**File:** `api/indicators/swing/setups/post_eps_flag.py` + tests.

**Rules (spec Section 6.6):**
- Earnings gap up > 5% in last 10 bars (from `last_earnings_gap_pct`)
- Since gap: daily range < 4% for ≥ 3 consecutive bars
- Price holding above post-gap 10-EMA
- Volume drying up (< 80% avg)
- **Stop:** min(consolidation low, post-gap 10-EMA)
- **Target:** measured move = breakout + consolidation height

**TDD:**
- [ ] Test: earnings gap + 3 tight bars on drying volume → fires.
- [ ] Test: no gap found → doesn't fire.
- [ ] Test: consolidation ranges too wide → doesn't fire.

**Graceful degradation:** if earnings calendar is unavailable for a ticker, skip (don't error the pipeline).

Commit: `feat(swing): add Post-EPS Flag Base detector with earnings gap gating`.

---

## Task 10: Market health helper

**File:** `api/indicators/swing/market_health.py` + tests.

**Contract:**
```python
@dataclass
class MarketHealth:
    qqq_close: float
    qqq_20ema: float
    qqq_10ema: float
    green_light: bool           # QQQ > 20-EMA
    index_cycle_stage: str      # Kell's cycle stage for QQQ itself
    snapshot: dict              # full dict for DB persistence
```

TDD:
- [ ] Test: QQQ above 20-EMA → `green_light=True`.
- [ ] Test: QQQ below 20-EMA → `green_light=False`.
- [ ] Test: snapshot includes all numeric fields.

Commit: `feat(swing): add market health helper for QQQ green-light`.

---

## Task 11: Confluence scoring

**File:** `api/indicators/swing/confluence.py` + tests.

**Algorithm (spec Section 6 confluence block):**
```
confluence_score = raw_score (1-5)
                 + multi_setup_bonus (+2 if 2+ swing detectors fire on same ticker)
                 + rs_bonus (+1 if RS > QQQ by 5%+)
                 + market_bonus (+1 if QQQ > 20-EMA)
                 + volume_bonus (+1 if setup volume > 1.5× avg)
                 + theme_bonus (+1 if universe_extras tags ticker as theme leader)
                 clipped to [1, 10]
```

Contract:
```python
def score_hits(hits: list[SetupHit], ticker: str, ctx: dict, market_health: MarketHealth) -> list[tuple[SetupHit, int]]: ...
```

TDD:
- [ ] Test: single hit, baseline — score == raw_score.
- [ ] Test: two detectors fire on same ticker → each gets +2.
- [ ] Test: RS high — +1.
- [ ] Test: QQQ green light — +1.
- [ ] Test: clipped to 10 at top end.

Commit: `feat(swing): add confluence scoring for setup ranking`.

---

## Task 12: Slack digest formatter

**File:** `api/indicators/swing/slack_digest.py` + tests.

Reads existing `api/integrations/slack.py` for how other digests post. Format:

```
🟢 Swing Pre-market  |  Universe: deepvue (152, 2d ago)  |  QQQ green light

Top setups (N):
1. NVDA  wedge_pop  9/10  entry 484-490  stop 478  targets 510/545  R:R 2.5
2. AAPL  ema_crossback  8/10  entry 187-189  stop 184  target 195
...

Stage transitions today (M):
• CRWD: wedge_pop → ema_crossback

Invalidations (K):
• XYZ: wedge_drop fired, stop hit

⏳ Analysis pending — Mac will pick up at 6:30am PT
```

TDD:
- [ ] Test format with 3 hits, 1 transition, 0 invalidations.
- [ ] Test empty digest (0 setups, 0 transitions).
- [ ] Test handles missing `second_target` cleanly.
- [ ] `post_premarket_digest(sb, hits_with_scores, transitions, invalidations, market_health, universe_source)` hits Slack via existing integration; test by mocking the poster.

Commit: `feat(swing): add pre-market Slack digest formatter`.

---

## Task 13: Pre-market pipeline orchestrator

**File:** `api/indicators/swing/pipeline.py` + tests.

**Orchestration:**
```python
def run_premarket_detection(sb) -> dict:
    # 1. Resolve universe (Plan 1's resolve_universe)
    # 2. Bulk-fetch daily + weekly bars for universe ∪ {QQQ}
    # 3. Compute market health
    # 4. For each ticker:
    #    - Read prior ideas (last 30 bars' worth from swing_ideas)
    #    - Run 5 detectors sequentially
    #    - Collect SetupHits
    # 5. Score all hits via confluence.score_hits
    # 6. Upsert swing_ideas rows for new fires
    # 7. Detect stage transitions on existing ideas (new Wedge Pop on existing EMA Crossback ticker, etc.)
    # 8. Capture daily snapshot rows (price/indicator only; claude_analysis blank)
    # 9. Invalidate ideas where Wedge Drop fired
    # 10. Post Slack digest
    # 11. Return {"new_ideas": N, "transitions": M, "invalidations": K, "universe_source": ...}
```

TDD:
- [ ] Test with `FakeSupabaseClient` + mocked `_fetch_bars_bulk` + small synthetic universe → verifies end-to-end: rows inserted, scores computed, digest formatted.
- [ ] Test idempotency: run twice with same date → no duplicate rows (partial unique index enforced at DB level; in fake client, endpoint must check before insert).
- [ ] Test empty universe → returns zeroes, no Slack post.

Commit: `feat(swing): add pre-market detection pipeline orchestrator`.

---

## Task 14: `GET /api/swing/ideas` + `GET /api/swing/ideas/{id}` endpoints

**Files:** `api/endpoints/swing.py` (modify), `api/schemas/swing.py` (modify) + `tests/swing/test_ideas_endpoints.py`.

Pydantic additions:
```python
class SwingIdea(BaseModel):
    id: UUID
    ticker: str
    cycle_stage: str
    setup_kell: str
    confluence_score: int
    entry_zone_low: float | None
    entry_zone_high: float | None
    stop_price: float
    first_target: float | None
    second_target: float | None
    status: str
    detected_at: datetime
    base_thesis: str | None
    thesis_status: str
    market_health: dict | None
    risk_flags: dict
    # ... (all user-facing fields from swing_ideas)

class SwingIdeaListResponse(BaseModel):
    ideas: list[SwingIdea]
    total: int
```

Endpoints:
```python
@router.get("/ideas", response_model=SwingIdeaListResponse)
def list_ideas(status: str | None = None, limit: int = 50): ...

@router.get("/ideas/{idea_id}", response_model=SwingIdea)
def get_idea(idea_id: UUID): ...
```

TDD:
- [ ] Test list with no filter returns all statuses ordered by confluence desc then detected_at desc.
- [ ] Test status filter.
- [ ] Test get-by-id happy path.
- [ ] Test 404 on missing id.

Commit: `feat(swing): add GET /api/swing/ideas endpoints`.

---

## Task 15: `/api/cron/daily-dispatcher` Vercel cron endpoint

**Files:** `frontend/src/app/api/cron/daily-dispatcher/route.ts` + modify `frontend/vercel.json`.

Behavior: on each invocation, inspect UTC hour. 13:00 → call Railway `/api/swing/pipeline/premarket` (new endpoint — add in this task) + existing daily-screeners. 21:00 → call existing market-monitor.

**Vercel cron auth:** Vercel-cron-signed `Authorization: Bearer $CRON_SECRET` header. Verify using `CRON_SECRET` env var. Reject otherwise.

**Add to backend:** `POST /api/swing/pipeline/premarket` endpoint that calls `run_premarket_detection(sb)`. Lightweight wrapper around Task 13's orchestrator.

**`vercel.json` changes:** remove the existing `daily-screeners` + `market-monitor` entries; add a single `daily-dispatcher` with schedule `0 13,21 * * 1-5` and `timezone: "America/Los_Angeles"` (wait — Vercel cron runs UTC; reconfirm by reading [docs/superpowers/specs/...](../specs/2026-04-18-kell-saty-swing-system-design.md) Section 9. Schedule stays UTC; DST drift is acceptable per spec).

TDD:
- [ ] Mock fetch to Railway, assert dispatcher-at-13 hits swing + daily-screeners endpoints.
- [ ] Mock fetch, assert dispatcher-at-21 hits market-monitor.
- [ ] Unauthorized call (missing/bad bearer) → 401.

Commit: `feat(swing): add /api/cron/daily-dispatcher + consolidate vercel.json crons`.

---

## Task 16: Frontend ideas list UI

**Files:**
- `frontend/src/lib/types.ts` — append `SwingIdea`, `SwingIdeaListResponse`.
- `frontend/src/hooks/use-swing-ideas.ts` — SWR-style hook `useSwingIdeas(status?: string)`.
- `frontend/src/app/api/swing/ideas/route.ts` — GET proxy using `railwayFetch`.
- `frontend/src/app/api/swing/ideas/[id]/route.ts` — GET single.
- `frontend/src/components/swing/ideas-list.tsx` — table + expandable rows.
- `frontend/src/components/swing/market-health-bar.tsx` — header strip showing QQQ 🟢 / 🟡 / 🔴.
- `frontend/src/app/swing-ideas/page.tsx` — wire Active + Watching tabs to `IdeasList` with status filters; keep Exited/ModelBook/Weekly as placeholders.

Table columns (per spec Section 10):
`status · stage · TICKER · conf · entry · stop · targets · R:R · expand`

Expandable row shows: base_thesis (truncated), stage evolution one-liner, actions (stub buttons for "View Detail" / "Add Note" / "Mark Invalidated" — wire as no-ops this plan; Plan 3 implements them).

- [ ] Verify build: `npm run build` lists `/api/swing/ideas` and `/api/swing/ideas/[id]`.

Commit: `feat(swing): wire Active + Watching tabs to /swing-ideas page`.

---

## Task 17: End-to-end verification

- [ ] Start backend, start frontend dev server.
- [ ] Manually seed: `.venv/bin/python` REPL → insert a small universe via `save_universe_batch(sb, {"AAPL": {}, "NVDA": {}}, "deepvue-csv", "add")`.
- [ ] Trigger the premarket endpoint manually: `curl -X POST http://localhost:8080/api/swing/pipeline/premarket`.
- [ ] Verify Supabase rows created in `swing_ideas`.
- [ ] Navigate to `/swing-ideas` → Active/Watching tabs populate.
- [ ] Check Slack channel (if `SLACK_WEBHOOK_URL` is set for dev).
- [ ] Run full test suite: `.venv/bin/python -m pytest tests/swing/ -v`. Expect existing 27 + ~60 new ≈ 87 tests passing.
- [ ] Frontend: `cd frontend && npx tsc --noEmit && npm run build`.

---

## Task 18: Merge + push

- [ ] Open PR (or fast-forward merge) from `swing/plan-2-detection` → `main`.
- [ ] User review checkpoint.
- [ ] Merge + push.

---

## Definition of Done

- ✅ 5 detectors fire on synthetic fixtures and abstain on negative fixtures (each has ≥ 4 tests).
- ✅ Shared indicators module has ≥ 8 unit tests.
- ✅ Confluence scoring tested over all bonus paths.
- ✅ Market health tested for green/yellow/red.
- ✅ Pre-market pipeline orchestrator runs end-to-end against `FakeSupabaseClient` and produces `swing_ideas` rows.
- ✅ Slack digest format verified in test.
- ✅ `vercel.json` has 1 consolidated cron; dispatcher correctly dispatches by UTC hour.
- ✅ `/api/swing/ideas` + `/api/swing/ideas/{id}` functional; `/swing-ideas` Active + Watching tabs show rows.
- ✅ No regressions in Plan 1 endpoints/tests.

---

## Out of Scope (deferred to Plans 3 / 4)

- Base thesis / deep thesis generation (Plan 3 — Claude on Mac).
- `POST /api/swing/ideas/{id}/thesis` endpoints (Plan 3).
- Post-market pipeline + Exhaustion Extension detector (Plan 4).
- Weekend `weekend-refresh` cron + backend universe regen trigger (Plan 4).
- Idea detail page `/swing-ideas/[id]` (Plan 3).
- Chart gallery, model book, weekly synthesis, events/snapshots timeline (Plan 4).

---

## Open Questions to Resolve During Execution

1. **Vercel cron auth.** Verify `CRON_SECRET` env var presence + add to docs if new. (Vercel auto-signs cron invocations with this — do not skip verification or endpoint becomes publicly callable.)
2. **Slack webhook scope.** Confirm which Slack channel `swing/#swing-alerts` maps to in `api/integrations/slack.py` multi-channel router; may need to add a new channel definition.
3. **`/api/swing/pipeline/premarket` auth.** Should the trigger endpoint require the same `CRON_SECRET` bearer token? Yes — otherwise anyone can fire the pipeline. Validate at the FastAPI layer using the same token the dispatcher injects.
4. **QQQ bars fetch cost.** `_fetch_bars_bulk` downloads QQQ inline each run. Cache for 5-10 min if multiple sub-tasks need it.
5. **`run_premarket_detection` runtime.** With 150 tickers, should fit within Vercel's 300s timeout when called from the dispatcher. Measure in Task 17 and move to background-worker pattern if needed.
