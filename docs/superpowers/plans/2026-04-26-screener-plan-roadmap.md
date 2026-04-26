# Screener — Plans 2, 3, 4 Roadmap

> **For Claude (next session):** This is a handoff document. Read this + the spec + Plan 1 to get full context, then start whichever plan is next. Each plan section below has enough scope/deliverables to drive a `superpowers:writing-plans` invocation that produces a detailed task-by-task plan.

**Spec:** [docs/superpowers/specs/2026-04-25-unified-screener-design.md](../specs/2026-04-25-unified-screener-design.md)
**Plan 1 (shipped):** [docs/superpowers/plans/2026-04-25-screener-plan-1-foundation.md](2026-04-25-screener-plan-1-foundation.md)

---

## Where Plan 1 left things (state at session handoff, 2026-04-26)

**Shipped & merged to main:**
- 3 Supabase tables (`screener_runs`, `coiled_watchlist`, `universe_overrides`) — applied to project `pmjufbiagokrrcxnhmah`
- Indicator overlay: `compute_overlay()` returning ATR%, %from50MA, jfsrev extension
- Scan registry pattern (`ScanDescriptor` + `register_scan` + `get_scans_for_mode`)
- ONE end-to-end scan: **Coiled Spring** (Donchian + TTM Squeeze + compression proxy + above-50MA gate)
- Persistence: `save_run` + `update_coiled_watchlist` + `backfill_days_in_compression` (helper exists, NOT yet wired into runner — see Plan 2 carryovers)
- yfinance bulk bar fetcher
- 3 FastAPI endpoints: `POST /api/screener/morning/run` (auth), `GET /api/screener/universe`, `POST /api/screener/universe/update` (auth)
- `/screener-universe-edit` Claude Code skill (5 subcommands: show / add / remove / replace / clear)
- 40 screener tests passing, 179 swing tests passing (no regressions)
- Saturday weekly-synthesis routine (`trig_01QwdUGhgk9DgeNZftarfxd3`) — committed to repo, runs `0 14 * * 6` UTC

**Known broken / pending action items NOT in any plan yet:**
1. **Railway auto-deploy is not picking up main.** As of merge `3eef42e`, `/health` returns 200 but `/api/screener/universe` returns 404 — Railway is running pre-merge code. User needs to check Railway dashboard → service → Settings → Source / Triggers, or trigger a manual redeploy. Until this is fixed, the Saturday routine will write failure-paragraph reports.
2. **Bearer token in routine prompt.** `SWING_API_TOKEN=a7cbcb27...` is embedded in the Saturday routine's prompt (only the user can see it via their claude.ai account) AND saved at `~/.config/trend-trading-mcp/swing-api.token` for local skill use. Verify Railway env has the same `SWING_API_TOKEN` value or the auth check will 500.

**Plan 1 carryovers (must be addressed in Plan 2 — flagged in code reviews):**
- **Wire `backfill_days_in_compression` into the runner.** Helper exists in `api/indicators/screener/persistence.py:96`, unit-tested, but never called. Spec §4 requires backfill so existing coils don't reset to day-1. There's a `TODO(plan-2)` comment in `api/indicators/screener/runner.py` at the watchlist-update site.
- **Replace the `_compression_proxy`** in `api/indicators/screener/scans/coiled.py` with the real Phase Oscillator port from `docs/phase_oscillator_pine_script.txt`. The proxy (rolling stddev / SMA20) is a stand-in; Phase Oscillator threshold values may need recalibration.
- **Extend `IndicatorOverlay` schema** with the union of fields needed by Plan 2 scans: `volume_avg_50d`, `relative_volume`, `gap_pct_open`, `pct_change_30d`, `pct_change_90d`, `pct_change_180d`, `adr_pct_20d`. (Pure additive Pydantic change, no migration.)
- **Live smoke run validation** of the Coiled Spring threshold against real market data — `scripts/screener_smoke_test.py` exists but was never executed. Ground-truth on whether the conditions ever fire is unknown.
- **Tighten implementer-subagent prompts** (process fix, not code fix): require `pwd` check ending in `.worktrees/<name>` before any `git commit` — two cwd-drift incidents during Plan 1 caused commits to land on main and required cherry-pick recovery.

---

## Plan 2 — Scan catalog expansion + Phase Oscillator + backfill wiring

**Goal:** populate the scan registry with the rest of the catalog so the morning screener becomes genuinely useful, and address all Plan 1 carryovers.

**Scope (estimated 18-22 tasks):**

### Foundation tightening (do these first — they unblock the scans)
1. Extend `IndicatorOverlay` schema with new metrics (volume_avg_50d, relative_volume, gap_pct_open, pct_change_30d/90d/180d, adr_pct_20d). Update `compute_overlay()` to compute them. Update existing tests + add new assertions.
2. Wire `backfill_days_in_compression` into `update_coiled_watchlist` (or into the runner before it). Threading: pass `bars_by_ticker` + `is_coiled_fn` into persistence, OR compute per-ticker initial day count in runner and pass as `dict[str, int]`. Add tests.
3. Port Phase Oscillator from `docs/phase_oscillator_pine_script.txt` to Python. Replace `_compression_proxy` in `coiled.py` with the real PO. Recalibrate threshold (-20 to +20 per spec §4).

### Scan implementations (one file each in `api/indicators/screener/scans/`)
Each scan: own file, own tests, self-registers via `register_scan(...)`, plus one line in `scans/__init__.py`. Order roughly by dependency complexity:

4. **Pradeep 4% Breakout Bullish** (lane=breakout, role=trigger): `% chg today > 4` + `volume vs yesterday > 0` + `volume > 100K`.
5. **Qullamaggie Episodic Pivot** (lane=breakout, role=trigger): `% chg today > 7.5` + `close > yesterday high` + `dollar volume > $100M`.
6. **Qullamaggie Continuation Base** (lane=breakout, role=setup_ready): leadership universe + price within ±2% of 10 SMA + ADR% > 4 + last > $5 + weekly volume vs last week < 50% + avg vol 50d > 300K.
7. **Saty Trigger Day Up** (lane=breakout, role=trigger): close above ATR Levels pivot trigger but below +50% level. Day = 1× ATR period; Multiday = ~2× period; Swing = ~5× period. Three variants → three registrations.
8. **Saty Golden Gate Day/Multiday/Swing Up** (lane=breakout, role=trigger): close hit 61.8% of next ATR level but hasn't crossed 78.6%. Three variants.
9. **Vomy Up Daily** (lane=transition, role=trigger): existing Vomy detector adapted from `api/indicators/swing/setups/...`. Daily bars.
10. **Vomy Up Hourly** (lane=transition, role=trigger): same logic, 60m bars. Requires hourly bar fetcher (extend `bars.py` with `fetch_hourly_bars_bulk`).
11. **EMA Crossback** (lane=transition, role=setup_ready): pullback to 10/21 EMA on leaders + reclaim. Reuse from swing setups.
12. **Saty Reversion Up/Down** (lane=reversion, role=setup_ready): bias candle + close relative to 21 EMA.
13. **Vomy Down at extension highs** (lane=reversion, role=trigger): Vomy detector + extension > 7.
14. **Saty Trigger Down** (lane=reversion, role=trigger): mirror of Saty Trigger Up below pivot.
15. **Kell Wedge Pop** (lane=breakout, role=setup_ready): reuse from `api/indicators/swing/setups/wedge_pop.py`.
16. **Kell Flag Base** (lane=breakout, role=setup_ready): tight consolidation post-impulse. May need new detector.
17. **Kell Exhaustion Extension** (lane=reversion, role=trigger): extension > 10 + climax volume. Reuse from `exhaustion_extension.py`.

### Confluence + observability
18. Confluence weighting (currently raw count). Add per-scan weights (Saty Trigger=3, Pradeep=2, ribbon-touch=1) so confluence becomes weighted score.
19. Sector grouping in run results (so frontend can show "5 semis fired today"). Add sector lookup (cache results).
20. Add structured logging for scan results (which tickers, how long each scan took) — helps debug Plan 3 frontend issues.
21. Earnings filter (exclude tickers with earnings in next 5 days from Breakout-lane scans). Pull from existing earnings calendar in swing module if present.
22. Run the `scripts/screener_smoke_test.py` against live Supabase + yfinance once the catalog is populated. Eyeball whether hit rate is sane.

**Out of scope for Plan 2 (defer to Plan 4):**
- Cron wiring (Railway scheduled jobs)
- Auto-promotion between lanes based on extension thresholds
- Model-book auto-capture rule

---

## Plan 3 — Frontend `/morning` page + mobile

**Goal:** the page the user actually opens at 6:30 AM PT for trade prep. Built per spec §10 visual restraint principles and §10.5 mobile rules. Must invoke `frontend-design` skill on every UI task.

**Scope (estimated 15-20 tasks):**

### Layout shell
1. New Next.js page at `/morning` (preferred over `/screener`; existing `/screener` page from `2026-03-01-screener-page.md` either redirects or stays as ad-hoc surface).
2. Sticky header: mode tabs (Swing | Position) · lane tabs (Breakout | Transition | Reversion | All) · last-refresh time · refresh button. Nothing else.
3. Per-lane stack: 4 sections (Universe count → Coiled table → Setup-ready table → Trigger table). Trigger lane is mobile default.

### Compact row + drawer
4. Compact row schema: 7 columns max — `Ticker | Price | Ext (B/A) | ATR% | Confluence # | Lane scans | Quick action`.
5. Click row → expand drawer with Saty levels mini-chart + Phase gauge + Hourly Vomy state + full scans list + days-in-coil counter + secondary actions (Save as Idea / Open in Analyze / Add to model book / Open chart).
6. Mobile (`sm`): row collapses to 3-line stacked card. Tablet (`md`): 5 cols. Desktop (`lg+`): full 7. Drawer becomes bottom-sheet on mobile.

### Data layer
7. Next.js API route proxies to `/api/screener/morning/run` and `/api/screener/universe` (matches existing `frontend/src/app/api/swing/...` pattern).
8. SWR hook with sessionStorage cache (matches existing `use-momentum-scan.ts` pattern).
9. TypeScript types matching Pydantic schemas (extend `frontend/src/lib/types.ts`).

### "Save as Idea" pipeline integration
10. Quick-action button on every row → calls existing `createIdea()` from `use-ideas.ts` with screener-source tags. Routes ticker into the swing-ideas → snapshot → Mac Claude analysis → model book pipeline. No new pipeline.

### Visual restraint enforcement (per spec §10.4 — binding)
11. Audit pass: typeface count, monospaced numbers, color-as-state-only, whitespace > borders, no decorative motion.
12. Empty states are one-liners.
13. Mobile-first verification: open at `375px` and confirm Trigger lane is fully usable with one thumb.

### Testing
14. Component tests for compact row + drawer.
15. End-to-end test: load page → run scan → expand row → save as idea → verify idea appears in `/swing-ideas`.

**Out of scope for Plan 3:** Position mode UI (data layer supports it; UI is Swing-only in v1 per spec §13).

---

## Plan 4 — Cron + auto-promotion + model-book auto-capture + Position mode

**Goal:** the screener becomes maintenance-free. Cron fires runs automatically; tickers auto-move between lanes based on extension; pop-after-coil patterns auto-feed the model book.

**Scope (estimated 10-14 tasks):**

### Cron wiring (per spec §11.3)
1. Railway cron job: 6:00 AM PT pre-market full run.
2. Railway cron job: 2:00 PM PT post-market refresh + coiled watchlist update.
3. Railway cron job: Sunday 5:00 PM PT — Position-mode universe refresh + Position-mode run.
4. Slack/Push digest helper: when a Coiled ticker fires (graduates from active → fired), post to Slack channel.

### Auto-promotion between lanes (per spec §7.1)
5. Background job (or part of runner): scan `screener_runs` history. When a ticker in Breakout/Coiled or Setup-ready hits Ext > 8 without firing → auto-promote to Reversion/Setup-ready (mark with reason `extension_climax_pre_breakout`).
6. When a ticker in Reversion/Trigger pulls back to Ext ≤ 1 → auto-promote back to Breakout/Setup-ready (mark with reason `extension_reset`).
7. Promotion events get logged to a new `lane_promotion_events` table (tiny: id, ticker, mode, from_lane, to_lane, reason, created_at).
8. Surface promotions in the frontend Saturday-digest routine.

### Model book auto-capture (per spec §5)
9. New job: when a Coiled-tagged ticker pops +20% within 5 days of graduating (status='fired'), auto-create a `swing_model_book` entry capturing the full pre-base / base / breakout window. Reuses existing model-book CRUD.
10. Surface auto-captures in the model book grid with a "source: coiled-graduate" badge.

### Position mode UI
11. Clone `/morning` page → `/morning?mode=position` (or similar). Same components, different scan list (Saty Trigger Position/Long-Term, 13/48 Weekly Up/Down). Lighter check-in cadence (Sunday-only?).

### Confluence weighting (if not in Plan 2)
12. Per-scan weights so confluence becomes a weighted score rather than raw count.

### Documentation
13. Update spec §13 (out-of-scope) to reflect what's now in scope.
14. Onboarding doc: how to add a new scan in 5 steps (registry pattern).

**End state after Plan 4:** the screener runs unattended, tickers flow through lanes automatically based on extension, the model book grows organically with successful coiled-spring patterns, and the user's morning prep is one tab open at `/morning`.

---

## How to start a fresh session for any plan

1. Open a new Claude Code session in this repo.
2. Say something like: *"I want to start Plan 2 of the screener. Read `docs/superpowers/plans/2026-04-26-screener-plan-roadmap.md` and the spec, then use `superpowers:writing-plans` to draft a detailed task-by-task plan for Plan 2."*
3. Claude will read both docs, ask any clarifying questions you missed in the roadmap, then produce a Plan 2 file at `docs/superpowers/plans/2026-04-XX-screener-plan-2-scan-catalog.md` (or similar) with full TDD-structured tasks.
4. Use `superpowers:subagent-driven-development` to execute it (same workflow as Plan 1).

**Process improvements to apply from Plan 1 lessons:**
- Set up a `.worktrees/screener-plan-N` worktree before any implementation work.
- In implementer-subagent prompts, **first instruction must be `pwd` and verify it ends with the worktree path** — prevents the cwd-drift commits to main that happened twice in Plan 1.
- Apply the migration to Supabase via the MCP `apply_migration` tool with the user's blanket Supabase access (granted in Plan 1) — don't make subagents do it.
- Run smoke tests against live infrastructure before declaring foundation work "shippable" — the Plan 1 Coiled Spring threshold remains unvalidated against real market data because we never ran the smoke test.
- Verify Railway auto-deploy is functioning before relying on `git push origin main` to ship code.

---

## Quick reference

**Repo:** `https://github.com/krishnaeedula23/trend-trading-mcp`
**Supabase project:** `pmjufbiagokrrcxnhmah` (full SQL access via the user's MCP server)
**Railway URL:** `https://trend-trading-mcp-production.up.railway.app`
**Routine ID:** `trig_01QwdUGhgk9DgeNZftarfxd3` (Saturday 7am PT screener weekly synthesis)
**Plan 1 merge commit:** `3eef42e`
**Token storage (local):** `~/.config/trend-trading-mcp/swing-api.token`

**File map of what's already in place:**
```
api/indicators/screener/
  overlay.py            # ATR%, %from50MA, jfsrev extension
  registry.py           # ScanDescriptor + register/get_scans_for_mode
  runner.py             # orchestration (TODO: wire backfill)
  bars.py               # yfinance bulk daily
  persistence.py        # save_run + update_coiled_watchlist + backfill helper
  universe_override.py  # add/remove/clear/list/apply
  scans/
    __init__.py         # imports coiled (Plan 2 adds more)
    coiled.py           # Coiled Spring (compression proxy → replace with PO)

api/endpoints/screener_morning.py  # 3 routes
api/schemas/screener.py            # 9 Pydantic models
docs/schema/019_add_screener_tables.sql  # applied to Supabase
.claude/skills/screener-universe-edit.md
scripts/screener_smoke_test.py     # never run — Plan 2 should
tests/screener/                    # 40 tests
```
