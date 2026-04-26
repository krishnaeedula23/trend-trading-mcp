# Unified Screener — Design Spec

**Date:** 2026-04-25
**Status:** Design approved, ready for implementation plan
**Owner:** krishnaeedula

---

## 1. Goal

Replace the daily morning routine of bouncing between Deepvue, ThinkorSwim, and the existing dashboard with a single **Morning Command Center** page that:

1. Runs all consolidated scans (~30+ from Deepvue + TOS) in one job
2. Overlays Saty / Kell context (ATR levels, ribbon state, phase oscillator, extension) on every hit
3. Feeds hits directly into the existing swing-ideas pipeline (snapshot → Mac-side Claude analysis → model book)
4. Surfaces confluence — "MXL hit 6 of my 32 scans today"
5. Tracks coiled / basing / squeezed stocks across days, not just point-in-time
6. Is **clean and restrained** by design — explicit antidote to the cluttered existing dashboard

Deepvue and TOS are **not** being replaced. They stay for charting and exploration; this tool owns the morning prep workflow.

## 2. Core organizing model

### 2.1 Two trading modes

| Mode | Bar timeframes | Hold duration | MVP? |
|---|---|---|---|
| **Swing** | Daily + Hourly | 3 days – 6 weeks | Yes |
| **Position** | Weekly + Daily | 1 – 6 months | Data layer yes, UI no |

Intraday / 10m is explicitly **out of scope** — already covered by the existing SPY day-trading system.

### 2.2 Three lanes (by trader's intent)

A trader in market prep first decides **what kind of trade they're hunting today**, then filters scans to that intent. The lanes mirror Kell's cycle of price action and align with each methodology:

| Lane | Methodology | What it hunts |
|---|---|---|
| **🚀 Breakout** | Qullamaggie · Pradeep · Kell Base-n-Break / Wedge Pop | Strong stock, tight base, expansion bar |
| **🔄 Transition** | Saty EMA · Kell EMA Crossback / Flag Into Ribbon | Uptrend pulled back to support, reclaiming |
| **🪃 Reversion** | Saty Reversion · Kell Reversal / Exhaustion Extension | Extended too far, snap back |

### 2.3 Four roles within each lane

| Role | Persistence | Updated | Question it answers |
|---|---|---|---|
| **Universe** | weeks | weekly refresh | What's eligible? |
| **Coiled / Tracked** | days–weeks | daily | What's tightening right now? |
| **Setup-ready** | today | each run | What's about to fire? |
| **Trigger** | today | each run | What just fired? |

Roles are **ordered top-down** in morning prep: Universe count → Coiled count → Setup-ready count → Trigger hits (the actionable list).

## 3. Scan catalog (Swing mode)

### 🚀 Breakout

| Role | Scans |
|---|---|
| Universe | Qullamaggie 1M / 3M Top Gainers · Saty Momentum |
| Coiled | **Multi-condition coiled spring** (see §4) |
| Setup-ready | Qullamaggie Continuation Base · Kell Wedge Pop · Kell Flag Base |
| Trigger | Pradeep 4% Breakout · Qullamaggie Episodic Pivot · Saty Trigger Day/Multiday/Swing Up · Saty Golden Gate Day/Multiday/Swing Up |

### 🔄 Transition

| Role | Scans |
|---|---|
| Universe | (shares Breakout universe) |
| Coiled | EMA-touch tracker (days-since-touched-21EMA counter) |
| Setup-ready | Pullback to 10/21 EMA · Kell EMA Crossback |
| Trigger | **Vomy Up Hourly** (key) · Vomy Up Daily · Saty Trigger Multiday Up reclaim |

### 🪃 Reversion

| Role | Scans |
|---|---|
| Universe | Extension > 7 (B/A) · Phase Oscillator > 80 |
| Coiled | Extension trackers (days-extended counter) |
| Setup-ready | Saty Reversion Up/Down candidates · Bias candles forming |
| Trigger | Vomy Down at extension highs · Saty Trigger Down · Kell Exhaustion Extension warning |

### Position mode (data layer in MVP, UI deferred)

Same lane × role structure, populated by Saty Trigger / GG **Position** + **Long-Term** variants and 13/48 Weekly Up/Down. Built but not surfaced in v1 UI.

## 4. The Coiled Spring scan (multi-condition)

A new persistent scanner that defines what "basing / squeezed / compressing" means as one composite signal.

**Definition — ALL of these true on the same daily bar:**
- **Basing:** ADR% 20d in bottom quartile of its own 6-month range (or 20-day Donchian width < 8% of price)
- **TTM Squeeze:** ON (Bollinger Bands inside Keltner Channels)
- **Phase Oscillator:** in compression zone (-20 to +20)
- **Trend gate:** close > 50 SMA (don't catch basing-into-downtrend)

**Persistence:** stored in a `coiled_watchlist` table. Tickers stay on the list as long as the multi-condition holds; fall off when broken or when the squeeze fires. A **days-in-compression counter** tracks how long each ticker has been coiled — sort default is longest-coil-first.

**On first run:** counter is **backfilled** from historical bars (look back N days and count consecutive days of compression) so the watchlist isn't empty / reset to day 1 at launch.

**Auto-graduation:** when a coiled ticker fires (squeeze releases + price expands), it auto-promotes to the Trigger role and a row appears in the Trigger table tagged "graduated from Coiled (N days)".

**Bonus criterion (optional toggle): "Preceded by trend"** — adds the filter `+30% in prior 90 days before basing began`. This is the Qullamaggie / Pradeep "trend → base → explosive move" pattern (request 1 from the brainstorm). Off by default; user can toggle on per scan run.

## 5. Pattern history (Trend → Base → Explosive Move)

**In MVP:**
- **(a) Live setup detector** = the Coiled scan with "Preceded by trend" toggle on. Already covered by §4.
- **(c) Model-book auto-capture** — extend the existing model book with a rule: when a Coiled-tagged ticker pops +20% within 5 days of graduating, auto-create a model-book entry capturing the full pre-base / base / breakout window. Builds the user's pattern library organically over time.

**Deferred:**
- **(b) Pattern-history-aware scoring** (backtest each ticker's history for the pattern, boost rank when high-scorer reappears). Revisit after 6 months of model-book auto-captures provides data to validate whether scoring is predictive.

## 6. Universe strategy

### Hybrid: CSV when fresh, generated when stale (mirrors existing swing pattern)

**Source priority (per mode):**
1. **Deepvue CSV import** — drop CSV into watched folder OR upload via UI. Multiple CSVs union into the active universe. Hashed for change detection.
2. **Backend-generated** — yfinance + Saty Momentum filters. Used when newest CSV > 7 days old.
3. **Manual overrides via Claude Code skill** — see §6.2. Layer on top of (1) or (2); persist across CSV refreshes.

**Single bulk bar download per run** — all scans share the resulting DataFrame. This is what makes confluence cheap and keeps run time bounded (~30–60s for 500–1500 names).

**Per-scan opt-out:** a scan can override and use a wider universe if its purpose demands it (e.g., Pradeep 4% might want to scan beyond the leadership universe to catch unloved names breaking out). Configured in the scan registry, not the UI.

### 6.1 Universe scoping: per-mode

Swing mode and Position mode each have their own active universe (different size/quality buckets). Manual overrides are per-mode.

### 6.2 Manual universe edits via Claude Code skill

New skill at `.claude/skills/universe-edit/` following the existing `/swing-*` skill pattern.

| Command | Action |
|---|---|
| `/universe-add NVDA, AMD, MXL` | Append tickers to active universe (current mode) |
| `/universe-remove TSLA` | Drop ticker from active universe |
| `/universe-replace [paste list]` | Wholesale swap |
| `/universe-show` | List current contents + source breakdown (CSV / generated / manual) |
| `/universe-clear-overrides` | Reset manual edits, return to CSV/generated base |
| `/universe-mode swing\|position` | Switch which mode the next command targets |

Backed by `POST /api/screener/universe/update` and a new `universe_overrides` table.

## 7. Indicator overlay (computed for every ticker on every run)

| Metric | Formula | Use |
|---|---|---|
| **ATR%** (A) | `ATR(14) / close` | Volatility / position sizing reference |
| **% Gain from 50-MA** (B) | `(close − SMA50) / SMA50` | Distance above MA |
| **Extension** (B/A) | `B / A` — jfsrev formula | Stretched-too-far detector |
| **Saty pivot / trigger / GG** | Per Saty ATR Levels Pine script | Indicator-state scans + UI display |
| **Saty ribbon state** | Per Pivot Ribbon Pro Pine script | Trend / pullback context |
| **Phase Oscillator** | Per Phase Oscillator Pine script | Compression / extension state |
| **Hourly Vomy** | Vomy on 60m bars | Swing entry refinement (displayed in row drawer, not compact row) |

### 7.1 Extension (B/A) thresholds and behavior

| Extension | Color | Meaning | Lane behavior |
|---|---|---|---|
| 0–3 | green | Entry zone — pullback complete | Eligible for Breakout / Transition setup-ready |
| 3–7 | yellow | Trending, healthy | Hold-only |
| 7–10 | orange | Profit-taking zone | Auto-flag in Reversion / Setup-ready |
| >10 | red | Climax — historical stall (PLTR/SOFI/TSLA/VRT/NVDA examples per jfsrev) | Auto-promote to Reversion / Trigger |

**Auto-promotion between lanes** is driven by the extension value:
- Breakout/Coiled ticker reaches Ext > 8 without firing → moves to Reversion/Setup-ready (the breakout failed to develop)
- Reversion/Trigger ticker pulls back to Ext ≤ 1 → moves back to Breakout/Setup-ready (the reset completed)

## 8. Confluence engine

Single bulk run produces a `(ticker, scans_hit[])` map. Confluence count = `len(scans_hit)`.

**Per-row display:** badge with confluence count next to ticker. Hover/expand shows the full list of scans hit.

**Cross-lane meta-view:** a global "All hits" view (across all 3 lanes) sorted by confluence count desc. The user's claim "MXL hit 6 of my 32 scans today" is exactly this view.

**Confluence weighting (deferred to v2):** later, scans can carry weights (e.g., Saty Trigger Up = 3, Pradeep 4% = 2, ribbon-touch = 1) so confluence becomes a weighted score, not raw count. v1 is raw count only.

## 9. Pipeline integration with swing-ideas

Every row's primary action is **Save as Idea** — invokes existing `createIdea()` with:
- `direction`: lane-derived (Breakout/Transition = bullish-long; Reversion = depends on scan direction)
- `timeframe`: `1d` for Swing mode, `1w` for Position mode
- `status`: `watching`
- `source`: `screener`
- `tags`: `["source:screener", "lane:<lane>", "role:<role>", ...scan-specific tags including all scans the ticker hit]`
- `notes`: auto-generated summary (scans hit, current extension, days-in-coil if applicable)

This routes the ticker into the existing swing-ideas → snapshot → Mac-side Claude analysis → model book pipeline. No new pipeline.

## 10. UI / UX

**Implementation MUST invoke `frontend-design` skill at every UI task.** The clean-UI requirements below are binding, not advisory — they exist explicitly to counter the cluttered feel of the rest of the site.

### 10.1 Layout

- **Single Next.js page** at `/morning` (preferred over `/screener` to make the morning-prep purpose explicit; `/screener` page from the existing plan can either redirect or coexist as a different surface)
- **Sticky top header:** mode tabs (Swing | Position) · lane tabs (Breakout | Transition | Reversion | All) · last-refresh time · manual refresh button. Nothing else.
- **Each lane view** stacks four sections vertically: Universe count summary → Coiled table → Setup-ready table → Trigger table
- **No sidebar within the page.** No nested tabs. No card-in-card.

### 10.2 Compact row schema (every table)

7 columns max:

```
Ticker | Price | Ext (B/A) | ATR% | Confluence # | Lane scans | Quick action
```

Click row to expand inline drawer.

### 10.3 Expand drawer contents

- Saty levels visualized (mini chart with pivot / trigger / GG / ribbon marked)
- Phase Oscillator gauge
- Hourly Vomy state (large icon + value)
- Full list of scans hit (with timestamps)
- Days-in-coil / days-in-extension counters
- Secondary actions: Save as Idea · Open in Analyze · Add to model book · Open chart on Deepvue/TradingView

### 10.4 Visual restraint principles (binding)

1. One typeface; three sizes max
2. Numbers right-aligned, monospaced; tickers monospaced
3. Color = state only (extension threshold colors; one accent for "fired today"). Everything else neutral
4. No badges where a number suffices (`6` not `6 SCANS`)
5. Whitespace > borders. No "everything in a card"
6. One primary action per row; secondary actions in drawer
7. Empty states are one-liners, not placeholder cards
8. No motion except: row expand/collapse + new-hit pulse on refresh
9. Reference visual baseline: Linear, Plaid dashboards (not Bloomberg, not TradingView)

### 10.5 Responsive / mobile behavior (binding)

The page must be usable on phone (the morning routine often happens on mobile before the user is at a desk). Tailwind breakpoints: `sm` <640px, `md` ≥768px, `lg` ≥1024px.

**Layout adaptation:**

| Element | Mobile (`sm`) | Tablet (`md`) | Desktop (`lg+`) |
|---|---|---|---|
| Mode tabs | Pill toggle (Swing / Position) | Tabs | Tabs |
| Lane tabs | Horizontal-scroll tabs with snap, icon + abbreviation | Full label tabs | Full label tabs |
| Row layout | **Stacked card** — 3 lines: (1) Ticker · Price · Ext (2) Scan badge row (3) Confluence · Quick action | 5 columns (drop ATR% and Lane scans → into expanded card) | 7 columns (full schema §10.2) |
| Row expand | **Bottom sheet drawer** sliding from bottom (full-width, 80vh max) | Inline expand | Inline expand |
| Sticky header | Mode pill + lane tabs only; refresh button moves to drawer-overlay action | Full sticky header | Full sticky header |
| Section headers | Collapsed by default (Universe / Coiled / Setup-ready / Trigger as accordion) — Trigger expanded by default | All expanded | All expanded |
| Tap targets | ≥44px height on all interactive elements | Standard | Standard |

**Mobile-specific rules:**

1. **Trigger lane is the default mobile view** — that's what matters at 6:30 AM PT on a phone. Other roles collapsed under accordions.
2. **No horizontal scroll on tables.** Card stack instead. Horizontal scroll on a row is a failure mode.
3. **Bottom sheet drawer** uses native scroll and snaps to 50vh / 80vh / full. Closes on swipe down.
4. **Confluence count and Extension color** are the two visual anchors that must remain visible at every breakpoint — they drive the "scan and decide" flow.
5. **Manual refresh button** must be thumb-reachable — bottom-right floating action button on mobile, sticky header position on desktop.
6. **Charts in the drawer** (Saty levels mini-chart, Phase gauge) render at full drawer width on mobile, not fixed pixel widths.

**Out of scope for mobile MVP:**
- Universe editing — desktop-only (Claude skills are CLI anyway)
- Position mode — same as desktop, deferred entirely
- Multi-select / bulk actions

## 11. Backend architecture

### 11.1 Components

```
api/endpoints/morning_screener.py        # POST /run, GET /results, GET /universe, POST /universe/update
maverick_mcp/screener/
  registry.py                            # Scan registry: id, lane, role, mode, fn, universe_override
  runner.py                              # Bulk bar download + parallel scan dispatch + confluence aggregation
  scans/
    breakout/                            # Pradeep, Qullamaggie EP, Saty Trigger Up, Saty GG Up, Continuation Base, Wedge Pop
    transition/                          # Vomy hourly/daily, EMA Crossback, Trigger reclaim
    reversion/                           # Reversion candidates, Vomy at extremes, Trigger Down, Exhaustion
    coiled/                              # Multi-condition coiled spring
  indicators/                            # Reuse existing Saty ATR/Pivot Ribbon/Phase Osc + new Extension calc
  universe/
    csv_loader.py                        # Hashed CSV import
    generator.py                         # yfinance + Saty Momentum fallback
    overrides.py                         # Manual edits from Claude skill
  persistence/
    coiled_watchlist.py                  # Days-in-compression tracking
    runs.py                              # Store last run results for fast page loads
```

### 11.2 Run sequence

1. Resolve active universe (CSV → generated → apply overrides)
2. Bulk download daily bars (yfinance) + hourly bars (separate call, only for tickers in universe)
3. Compute indicator stack once per ticker (ATR, SMA50, Saty levels, ribbon, phase, extension)
4. Dispatch each scan in parallel (existing `parallel_screening.py` utility)
5. Aggregate `(ticker, scans_hit[])` confluence map
6. Update `coiled_watchlist` (increment counters / mark fires / promote graduates)
7. Persist run results
8. Return JSON to frontend

Target run time: **30–60 seconds** for 500–1500 ticker universe.

### 11.3 Cron schedule

Reuse existing Railway cron infrastructure:
- **6:00 AM PT pre-market** — full run for the day
- **2:00 PM PT post-market** — refresh for next-day prep + coiled watchlist update
- **Sunday 5:00 PM PT** — universe refresh + Position mode run

Same cron windows as existing swing-pipeline jobs, intentionally — this screener IS the front end of the swing pipeline.

## 12. Database additions

| Table | Purpose |
|---|---|
| `screener_runs` | Run metadata + serialized results blob (one row per cron run) |
| `coiled_watchlist` | `(ticker, mode, first_detected_at, days_in_compression, last_seen_at, status)` |
| `universe_overrides` | `(mode, ticker, action: add\|remove, created_at, source: claude_skill\|ui)` |

All other state (ideas, snapshots, model book) reuses existing swing tables.

## 13. Out of scope for MVP

Captured here so they don't sneak in:

- Position mode UI (data layer only in v1)
- Alerts (push / Slack notifications when coiled fires)
- Sector grouping view
- Earnings filter (exclude pre-earnings tickers from Breakout)
- Float / short interest data
- Confluence weighting (raw count only in v1)
- Pattern-history scoring (request 5b — defer 6 months)
- 10m / intraday scans (out of swing scope by design)
- Replacing Deepvue / TOS (this is a complement, not a replacement)

## 14. Success criteria

MVP is successful if:

1. One page replaces the user's morning routine of bouncing between Deepvue + TOS + dashboard
2. All MVP scans run in a single ≤60s job; results visible by 6:30 AM PT
3. Coiled watchlist is populated and tracking days-in-compression after first week
4. Confluence count surfaces at least one ticker per week that wouldn't have been spotted in any single scan alone
5. "Save as Idea" → swing pipeline integration works end-to-end with no manual ticker re-typing
6. Extension auto-promotion correctly moves at least one ticker between lanes per week
7. The page **does not feel cluttered** — passes a "Linear/Plaid dashboard" aesthetic test, not a "Bloomberg terminal" one
8. Manual universe editing via `/universe-*` Claude skills works without UI
9. **Trigger lane is fully usable on a phone at 6:30 AM PT** without horizontal scroll, with one-thumb operation

## 15. Open questions to revisit during implementation

- Exact Phase Oscillator compression threshold (-20 to +20 is a starting guess; may need calibration)
- Hourly bar download cost — yfinance hourly is heavier than daily; may need to scope down to a leadership subset rather than full universe
- Coiled backfill window — how many days back to look on first run (initial guess: 60)
- Whether the existing `/screener` page from the in-flight plan ([2026-03-01-screener-page.md](../../plans/2026-03-01-screener-page.md)) should be subsumed entirely or kept as a separate "ad-hoc scan" surface

---

## 16. Methodology references (for implementation context)

- **Qullamaggie:** https://qullamaggie.com/ — top gainers universe, 1/3/6-month leadership, episodic pivots, continuation bases on pullback to 10 SMA
- **Pradeep Bonde (Stockbee):** 4% breakout on volume, anticipation setups, episodic pivots, wide universe
- **Saty Pile:** ATR Levels (pivot/trigger/GG/-50%/-61.8%), Pivot Ribbon Pro, Phase Oscillator, Vomy oscillator, mean reversion candidates. Pine scripts: `docs/saty_atr_levels_pine_script.txt`, `docs/pivot_ribbon_pine_script.txt`, `docs/phase_oscillator_pine_script.txt`
- **Oliver Kell:** Cycle of price action — Reversal Extension → Wedge Pop → EMA Crossback → Base-n-Break → Exhaustion Extension. Notes: `docs/kell/source-notes.md`
- **jfsrev ATR% extension formula:** `((close - SMA50) × close) / (SMA50 × ATR)` — source: TradingView post by user `jfsrev`, profit-taking thresholds 7–10× cited as historical stall zone
