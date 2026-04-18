# Kell + Saty Unified Swing Trading System — Design Spec

**Date:** 2026-04-18
**Author:** Krishna Eedula (with Claude Code)
**Status:** Draft for review

---

## 1. Goal

Build a swing-trading subsystem that combines **Oliver Kell's methodology** (daily/weekly cycle-of-price-action) with the existing **Saty trading system** (already implemented in this repo) into a unified framework. The system identifies swing setups on daily timeframe, tracks their evolution over weeks, generates fundamental theses using the user's **Claude Max subscription** (not API), and delivers actionable digests via Slack + a new `/swing-ideas` page.

This is **parallel to**, not a replacement for, the existing SPY intraday day-trading system in this repo.

---

## 2. Problem & Context

### Existing state
- FastAPI backend with Saty indicators (ATR Levels, Pivot Ribbon, Phase Oscillator)
- Saty setups already implemented: Vomy, Golden Gate, Flag Into Ribbon, ORB, Squeeze, Divergence, EOD Divergence, Wicky
- Next.js 16 frontend on Vercel with `/screener` (Momentum + Golden Gate + Vomy), `/trade-plan`, `/ideas`, `/watchlists`
- Two existing Vercel crons: `daily-screeners` (9am ET) and `market-monitor` (4:30pm ET)
- Slack integration with multi-channel routing
- Trading companion with ideas, journal, trade log, `/note`, `/plan`, `/log-trade`
- User has external subscriptions: Deepvue, TradingView, ThinkorSwim
- User has Claude Max subscription (flat rate) — wants to leverage this instead of per-token API billing

### Gap
The existing system is largely intraday/day-trading-focused on SPY and a handful of day tickers. Kell's methodology — 4-12 week holds, individual growth names, cycle-of-price-action nomenclature, rigorous fundamental + technical filters — has no counterpart. The user wants:
1. Kell methodology codified and combined with Saty in a unified swing framework
2. Screeners tuned for daily-timeframe Kell-style setups
3. A universe sourced from Deepvue with backend fallback
4. Scheduled pre-market and post-market automated analysis
5. Claude-driven fundamental and thesis analysis per stock
6. Longitudinal tracking (daily/weekly) with a "model book" for pattern recognition
7. Ad-hoc analysis of any ticker via slash command
8. Bookkeeping with marked-up chart images

### Key reference
Kell methodology source notes: [docs/kell/source-notes.md](../../kell/source-notes.md). This is the source of truth for Kell's rules. The design never paraphrases from memory — it grounds against those notes.

---

## 3. Design Decisions (pinned)

These were locked in during brainstorming and drive the rest of the design:

| Decision | Choice | Rationale |
|---|---|---|
| Kell + Saty combination | **Unified framework (concept-level)** | Kell cycle stages are *conceptually* analogous to Saty setups (Wedge Pop ≈ Vomy intent, EMA Crossback ≈ Flag Into Ribbon intent, Base-n-Break ≈ Golden Gate intent, Reversal Extension ≈ Divergence intent) — same user mental model. **Detectors are net-new daily-TF code**, not wrappers of the existing Saty evaluators (which consume a pre-computed intraday-SPY payload and can't be reused directly). |
| Scope | **Swing only**, parallel to existing day trading | Clean separation; Kell's cycle applies to multi-week holds, not intraday |
| Execution timeframe | **60-min** (not Kell's 65-min) | What user's platforms support natively |
| Universe source | **Hybrid — Deepvue CSV primary + backend generator fallback** | Deepvue has superior fundamental filtering; backend keeps pipeline alive when Deepvue is stale |
| Output channels | **Slack + new `/swing-ideas` page** | Slack for alerts (matches muscle memory); page for deep review |
| Idea model | **Separate `swing_ideas` table** (not reusing `/ideas`) | Swing has cycle-stage state machine, pyramid adds, longer lifecycle — different enough to justify isolation |
| MVP setup scope | **B: 6 setups** — Wedge Pop, EMA Crossback, Base-n-Break, Reversal Extension, Exhaustion Extension (warning-only), Post-EPS Flag Base | All detectors are net-new daily-TF code. Where existing Saty code has relevant building blocks (e.g., ribbon tightness, phase oscillator), we extract the computation into a shared helper rather than reuse the intraday evaluator wholesale. |
| Fundamentals | **yfinance (bulk/cron) + Deepvue via Claude-in-Chrome (on-demand)** | yfinance is free and unblocks immediately; Deepvue is richer but only accessible through browser automation |
| Thesis generation | **Three layers**: Base (cron-time), Deep (post-market once), Weekly synthesis (Sunday) | Graduated richness, graduated cost |
| Thesis regeneration | **Auto for top-10 at detection + on next earnings or stage change** | Caches where possible, refreshes where it matters |
| Cron timing | **6am PT pre-market + 2pm PT post-market + Sun 5pm PT weekly** | Before open, after close, weekend synthesis |
| Where Claude runs | **Exclusively on user's Mac via Claude Code + Max subscription** | Zero API spend; Railway backend is pure data, no LLM |
| Ad-hoc analysis | **`/swing-analyze <TICKER>` slash command, works for any ticker** | Covers watchlist exploration beyond the universe |
| Model book | **Dedicated table for exemplary setups with charts + narrative** | Kell's OneNote ritual, formalized |
| Charts | **Vercel Blob storage, attached to ideas/events/model-book** | First-class assets, not afterthought |

---

## 4. Architecture (High Level)

```
┌──────────────────────────────────────────────────────────────────┐
│                   SWING TRADING SUBSYSTEM                        │
│                   (parallel to existing SPY day-trading)         │
└──────────────────────────────────────────────────────────────────┘

         ┌─ Vercel Cron ─────────────────────────────────┐
         │  6am PT (pre-market)   2pm PT (post-market)   │
         │                        Sun 5pm PT (weekly)     │
         └──────────────┬────────────────────────────────┘
                        ↓ triggers
         ┌─ FastAPI backend on Railway ──────────────────┐
         │  /api/swing/run-detection  (pre-market)       │
         │  /api/swing/run-postmarket (post-market)      │
         │  /api/swing/refresh-universe (Sunday)         │
         │                                               │
         │  Pure Python/pandas work:                     │
         │  • Universe resolution (Deepvue or backend)   │
         │  • Daily bar fetch (yfinance)                 │
         │  • Indicator computation                      │
         │  • 6 MVP setup detectors                      │
         │  • Confluence scoring + ranking               │
         │  • Write swing_ideas, snapshots, events       │
         │  • Post Slack digests                         │
         │  NO CLAUDE API CALLS                          │
         └───────────────────────────────────────────────┘
                        ↓ triggers (separate)
         ┌─ Your Mac — scheduled-tasks MCP ──────────────┐
         │  6:30am PT → /swing-analyze-pending           │
         │  2:30pm PT → /swing-deep-analyze              │
         │  Sun 5pm PT → /swing-weekly-synth             │
         │                                               │
         │  Claude Code (Max subscription) does:         │
         │  • Base thesis generation                     │
         │  • Deep thesis via Claude-in-Chrome → Deepvue │
         │  • Chart screenshots (daily/weekly/60m)       │
         │  • Vision analysis of charts                  │
         │  • Weekly synthesis                           │
         │  • POST results back to Railway               │
         └───────────────────────────────────────────────┘
                        ↓ user opens browser
         ┌─ Next.js /swing-ideas page ───────────────────┐
         │  Tabs: Active / Watching / Exited /           │
         │        Universe / Model Book / Weekly         │
         │  Idea detail: thesis + timeline + charts +    │
         │               fundamentals + actions          │
         └───────────────────────────────────────────────┘
```

**Key separations:**
- **Cron path** = unattended, yfinance-only, bulk detection and ranking
- **Mac-Claude path** = intelligence layer using Max subscription
- **Existing `/ideas`, `/trade-plan`, `/scan`** stay untouched — swing is additive

---

## 5. Data Model

### 5.1 `swing_universe`

Living set of tickers currently eligible for scanning. Supports CSV upload (replace or add), single-ticker add/remove, and backend-generated fallback.

```sql
CREATE TABLE swing_universe (
  id SERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  source TEXT NOT NULL,               -- 'deepvue-csv' | 'manual' | 'backend-generated'
  batch_id UUID NOT NULL,             -- groups rows from same upload
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  removed_at TIMESTAMPTZ,             -- soft-delete; NULL = active
  extras JSONB                        -- Deepvue columns, fundamentals cache
);
-- Partial unique index: only one ACTIVE row per ticker.
-- (Plain UNIQUE(ticker, removed_at) doesn't work in Postgres — NULL != NULL in unique indexes.)
CREATE UNIQUE INDEX swing_universe_active_ticker_uniq
  ON swing_universe (ticker) WHERE removed_at IS NULL;
CREATE INDEX ON swing_universe (batch_id);
```

Active universe = `WHERE removed_at IS NULL`.

### 5.2 `swing_ideas`

Core model for detected setups and their lifecycle.

```sql
CREATE TABLE swing_ideas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  direction TEXT NOT NULL DEFAULT 'long',   -- 'long' only for MVP
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Kell cycle state
  cycle_stage TEXT NOT NULL,                -- see enum below
  setup_kell TEXT NOT NULL,                 -- which Kell setup fired
  setup_saty TEXT,                          -- confluence Saty setup, if any
  confluence_score INT NOT NULL,            -- 1-10

  -- Levels
  entry_zone_low NUMERIC,
  entry_zone_high NUMERIC,
  stop_price NUMERIC NOT NULL,
  first_target NUMERIC,
  second_target NUMERIC,

  -- Sizing (Kell bips model)
  suggested_position_pct NUMERIC,           -- 10-15 initial, up to 35 top idea
  suggested_risk_bips INT,                  -- 20-25 typical

  -- Fundamentals snapshot
  fundamentals JSONB,
  next_earnings_date DATE,
  beta NUMERIC,
  avg_daily_dollar_volume NUMERIC,

  -- Thesis (populated by Mac-Claude)
  base_thesis TEXT,
  base_thesis_at TIMESTAMPTZ,
  thesis_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'ready'
  deep_thesis TEXT,
  deep_thesis_at TIMESTAMPTZ,
  deep_thesis_sources JSONB,

  -- Market health at detection (QQQ 20-EMA, green/yellow/red, index cycle stage)
  market_health JSONB,

  -- Running risk flags (updated by post-market [C]; separate from detection-time market_health)
  risk_flags JSONB DEFAULT '{}'::jsonb,     -- e.g. {exhaustion_warning: true, 2nd_extension: true, approaching_earnings: 3}

  -- Lifecycle
  status TEXT NOT NULL DEFAULT 'watching',  -- 'watching'|'triggered'|'adding'|'trailing'|'exited'|'invalidated'
  watching_since TIMESTAMPTZ,
  invalidated_at TIMESTAMPTZ,
  invalidated_reason TEXT,

  user_notes TEXT,
  tags TEXT[]
);

-- Uniqueness: at most ONE active row per (ticker, cycle_stage).
-- A ticker can re-enter the same stage later, but only after the prior idea is
-- invalidated/exited. Partial index enforces this cleanly.
CREATE UNIQUE INDEX swing_ideas_active_ticker_stage_uniq
  ON swing_ideas (ticker, cycle_stage)
  WHERE status NOT IN ('exited', 'invalidated');
CREATE INDEX ON swing_ideas (status, detected_at DESC);
CREATE INDEX ON swing_ideas (ticker);
CREATE INDEX ON swing_ideas (thesis_status) WHERE thesis_status = 'pending';
```

**`cycle_stage` enum**: `reversal_extension` | `wedge_pop` | `ema_crossback` | `base_n_break` | `post_eps_flag` | `exhaustion_warning`.

### 5.3 `swing_idea_stage_transitions`

History of how an idea moves through Kell's cycle over time.

```sql
CREATE TABLE swing_idea_stage_transitions (
  id SERIAL PRIMARY KEY,
  idea_id UUID REFERENCES swing_ideas(id) ON DELETE CASCADE,
  from_stage TEXT,
  to_stage TEXT NOT NULL,
  transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  daily_close NUMERIC,
  snapshot JSONB
);
CREATE INDEX ON swing_idea_stage_transitions (idea_id, transitioned_at);
```

### 5.4 `swing_idea_snapshots`

One row per active idea per post-market run. Holds price + indicator data (Railway) and Claude analysis (Mac).

```sql
CREATE TABLE swing_idea_snapshots (
  id SERIAL PRIMARY KEY,
  idea_id UUID REFERENCES swing_ideas(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  snapshot_type TEXT NOT NULL,         -- 'daily' | 'weekly'

  -- Price/indicator (Railway-populated)
  daily_close NUMERIC, daily_high NUMERIC, daily_low NUMERIC,
  daily_volume BIGINT,
  ema_10 NUMERIC, ema_20 NUMERIC,
  sma_50 NUMERIC, sma_200 NUMERIC,
  weekly_ema_10 NUMERIC,
  rs_vs_qqq_20d NUMERIC,
  phase_osc_value NUMERIC,
  kell_stage TEXT,
  saty_setups_active TEXT[],

  -- Claude analysis (Mac-populated)
  claude_analysis TEXT,
  claude_model TEXT,                   -- free text; current candidates: 'claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-7'
  analysis_sources JSONB,

  -- Deepvue panel scrape
  deepvue_panel JSONB,

  -- Chart references
  chart_daily_url TEXT,
  chart_weekly_url TEXT,
  chart_60m_url TEXT,

  UNIQUE(idea_id, snapshot_date, snapshot_type)
);
CREATE INDEX ON swing_idea_snapshots (idea_id, snapshot_date DESC);
-- Cross-idea date queries (e.g. weekly synthesis pulling all ideas for a week):
CREATE INDEX ON swing_idea_snapshots (snapshot_date DESC, snapshot_type);
```

### 5.5 `swing_events`

Timeline of everything that happens to an idea.

```sql
CREATE TABLE swing_events (
  id SERIAL PRIMARY KEY,
  idea_id UUID REFERENCES swing_ideas(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB,
  summary TEXT
);
CREATE INDEX ON swing_events (idea_id, occurred_at DESC);
```

`event_type` values: `stage_transition` | `thesis_updated` | `setup_fired` | `invalidation` | `earnings` | `exhaustion_warning` | `user_note` | `chart_uploaded` | `trade_recorded` | `promoted_to_model_book`.

### 5.6 `swing_charts`

```sql
CREATE TABLE swing_charts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID REFERENCES swing_ideas(id) ON DELETE CASCADE,
  event_id INT REFERENCES swing_events(id) ON DELETE CASCADE,
  model_book_id UUID REFERENCES swing_model_book(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  thumbnail_url TEXT,
  timeframe TEXT NOT NULL,             -- 'daily' | 'weekly' | '60m' | 'annotated'
  source TEXT NOT NULL,                -- 'deepvue-auto' | 'tradingview-upload' | 'user-markup' | 'claude-annotated'
  annotations JSONB,
  caption TEXT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT swing_charts_one_owner
    CHECK (num_nonnulls(idea_id, event_id, model_book_id) = 1)
);
CREATE INDEX ON swing_charts (idea_id);
CREATE INDEX ON swing_charts (model_book_id);
```

Constraint enforced in Postgres: exactly one of `idea_id` / `event_id` / `model_book_id` must be set.

### 5.7 `swing_model_book`

Curated historical exemplary setups for pattern recognition.

```sql
CREATE TABLE swing_model_book (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  ticker TEXT NOT NULL,
  setup_kell TEXT NOT NULL,
  outcome TEXT NOT NULL,               -- 'winner' | 'loser' | 'example' | 'missed'
  entry_date DATE,
  exit_date DATE,
  r_multiple NUMERIC,
  source_idea_id UUID REFERENCES swing_ideas(id),
  ticker_fundamentals JSONB,
  narrative TEXT,
  key_takeaways TEXT[],
  tags TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 6. Setup Detectors

All 6 detectors run on **daily bars**. Live in new module `api/indicators/swing/setups/`, parallel to `api/indicators/satyland/setups/`.

### Detector contract

```python
@dataclass
class SetupHit:
    ticker: str
    setup_kell: str
    setup_saty: str | None
    cycle_stage: str
    entry_zone: tuple[float, float]
    stop_price: float
    first_target: float
    second_target: float | None
    detection_evidence: dict           # for thesis generation
    raw_score: int                     # 1-10, pre-ranking
```

> **Note**: Each detector is **new code in `api/indicators/swing/setups/`**. The existing Saty evaluators (`vomy.py`, `flag_into_ribbon.py`, `golden_gate.py`, `divergence.py`, `eod_divergence.py`) consume a pre-computed intraday-SPY payload (ribbon, phase, ATR levels, mtf_scores) and cannot be reused directly on daily bars of individual growth stocks. Where building blocks are genuinely shared (Phase Oscillator computation, Pivot Ribbon compression measurement), we extract them into helpers in `api/indicators/common/` callable from both pipelines.

### 6.1 Wedge Pop (`wedge_pop.py`)

- Reclaims 10/20 EMA after compression following a reversal extension
- **Filters** (tuned to Kell's prose): 10-EMA slope flat (|slope| < 0.2 ATR per bar over last 5 bars) — captures Kell's "flatter, not steep MAs"; EMA10/EMA20 spread < 0.5 ATR; higher low vs prior swing low in a descending-channel context (at least one prior lower-high in last 15 bars); RS vs QQQ positive over last 10 bars; reclaim bar closes > 10-EMA and > 20-EMA; reclaim volume ≥ 1.2× avg 20-day
- **Stop**: low of reclaim bar OR low of last 3-day consolidation, whichever is higher
- **Target**: prior swing high

### 6.2 EMA Crossback (`ema_crossback.py`)

- Pullback to 10-EMA or 20-EMA after an established uptrend
- **Filters**: prior Wedge Pop recorded on this ticker within last 30 bars (reads `swing_ideas` history); pullback low holds above EMA (no closing break); volume dries up (< 80% of 20-day avg)
- **Stop**: low of pullback day
- **Target**: prior swing high

### 6.3 Base-n-Break (`base_n_break.py`)

- Breakout from multi-week consolidation above 10/20 EMAs
- **Filters**: 5–8 week base minimum (25–40 bars); base high-low range / mid-price < 15%; consolidation holding above (not below) 10/20 EMAs throughout base; breakout close > base high; breakout volume ≥ 1.5× avg 20-day
- **Stop**: base low OR 20-EMA, whichever is higher
- **Target**: measured move (base height projected from breakout point)

### 6.4 Reversal Extension (`reversal_extension.py`)

- Capitulation bottom with bullish divergence at higher-TF support
- **Filters**: proximity to higher-TF support (within 3% of 200-SMA OR 10-WEMA OR weekly base low); capitulation volume > 1.5× avg; oversold phase-oscillator reading on daily; price stretched > 1.5 ATR below 10-EMA; bullish price/oscillator divergence (price LL, phase osc HL) over last 5–10 bars
- **Stop**: below reversal bar low
- **Target**: 20-EMA (first partial). Per Kell, move stop to cost on partial; no further mechanical target — managed discretionarily from there.

### 6.5 Exhaustion Extension (`exhaustion_extension.py`) — warning-only

- **Does not create new ideas.** Flags warnings on existing open ideas. Runs in the **post-market** cron ([C]), not pre-market — ideas must exist before they can be flagged.
- **Triggers** (mix of Kell-direct + heuristic):
  - Kell-direct: count of extensions from 10-EMA since last base breakout ≥ 2 (primary trigger — matches Kell's "sell the second extension"); climax volume (2× avg) + upper wick > 50% of day's range
  - Heuristic (flag as "H" in Slack so user knows these aren't Kell-literal): price > 2 ATRs above 10-EMA; weekly close > 15% above 10-WSMA (placeholder proxy for Kell's "Air" — tune after first 4 weeks of observation)
- **Action**: set `exhaustion_warning=true` in a dedicated `risk_flags` JSONB field on `swing_ideas`; `status` moves to `trailing` only if currently `triggered`/`adding`; write `swing_events` row of type `exhaustion_warning`; highlighted in post-market Slack digest

### 6.6 Post-EPS Flag Base (`post_eps_flag.py`) — NEW, requires earnings calendar

- Tight consolidation after an earnings gap up
- **Triggers**: earnings gap > 5% in last 10 bars; daily range < 4% for 3+ consecutive days; price above post-earnings 10-EMA; volume drying (< 80% avg)
- **Stop**: low of consolidation OR post-earnings 10-EMA
- **Target**: measured move
- **Data dependency**: earnings calendar via yfinance `.calendar` (primary) + Finnhub free tier (fallback). Wrapped behind a single `earnings_calendar.py` provider interface.

### Confluence scoring

```
confluence_score = base_setup_score       (1-5, per-detector base quality)
                 + multi_setup_bonus      (+2 if two or more swing detectors fire on same ticker — e.g., Wedge Pop + Post-EPS Flag)
                 + rs_bonus               (+1 if RS > QQQ by 5%+)
                 + market_bonus           (+1 if QQQ > 20-EMA — Kell green light)
                 + volume_bonus           (+1 if setup volume > 1.5× avg)
                 + theme_bonus            (+1 if universe extras tags ticker as theme leader)
                 clipped to [1, 10]
```

**Note on "Saty confluence":** Because Saty evaluators are intraday-SPY-scoped, we don't mechanically run them on daily bars of individual tickers for confluence scoring. Conceptual Kell↔Saty analogy is encoded in the *choice of detectors* (Wedge Pop captures Vomy-like dynamic on daily, etc.), not in a combined score. Revisit if/when a daily Saty port is built in a follow-up spec.

**"Top 10" means**: top 10 by `confluence_score` across the union of (newly-detected ideas in today's cron run) ∪ (active ideas with a stage change today). Excludes ideas in `exited` / `invalidated` status and ideas whose thesis is already fresh (< 24h old).

---

## 7. Universe Generator (Backend Fallback)

### Resolution logic

Inside the pre-market cron:

```python
def resolve_universe():
    deepvue = query_latest_universe(source='deepvue-csv')
    if deepvue and days_since(deepvue.latest_upload) <= 7:
        return deepvue.tickers, "deepvue"
    backend = query_latest_universe(source='backend-generated')
    if backend and days_since(backend.latest_upload) <= 7:
        return backend.tickers, "backend-stale-deepvue"
    tickers = generate_backend_universe()   # inline regen
    save_universe(tickers, source='backend-generated')
    return tickers, "backend-fresh"
```

Slack digest always reports source: `📋 Universe: deepvue (152 tickers, 2d ago)` or `📋 Universe: backend-fallback (87 tickers — upload fresh Deepvue CSV)`.

### Base ticker list

Static JSON at `api/indicators/swing/universe/base_tickers.json`:
- Russell 3000 ∪ Nasdaq Composite, de-duped, ~3500 tickers
- Refreshed manually once a quarter

### Filter pipeline (cheapest first)

```
Stage 1 (price + liquidity, bulk yfinance bars)
  price in [$50, $1000]
  avg_20d_dollar_volume >= $20M

Stage 2 (trend + base, price-only)
  close > SMA_200
  (high_30d - low_30d) / mid_30d < 0.15   # 5-8wk base proxy

Stage 3 (fundamentals, yfinance .quarterly_financials — only for passers)
  latest_Q_rev_yoy >= 0.30
  latest_Q_rev_yoy > prior_Q_rev_yoy       # acceleration

Stage 4 (relative strength, price-only)
  ticker_return_63d > qqq_return_63d

Optional (often unreliable yfinance data)
  beta >= 1.3
```

### Cadence

- Sunday 5pm PT cron (`swing-universe-refresh`)
- Results stored as `swing_universe` rows with `source='backend-generated'`
- Stage-3 quarterly financials cached into `swing_universe.extras` JSONB to avoid re-fetching during weekday crons

### Explicit non-goals for backend generator

- Not identifying theme leadership (human/Deepvue work)
- No EPS surprise analysis
- No float / short-interest / institutional-ownership filtering (Deepvue territory)
- No IBD-style RS rating — just 63-day return vs QQQ

---

## 8. Claude Analysis Layer (on User's Mac)

### Why Mac, not Railway

User has Claude Max subscription (flat-rate, message-limited per 5-hour window). Railway backend has no LLM calls. Claude Code on the Mac uses the Max subscription, eliminating API spend.

### Prerequisites to verify before the Mac-Claude pipeline is viable

**This section encodes dependencies that, if not satisfied, invalidate the architecture. Implementation plan must verify each before building.**

1. **`scheduled-tasks` MCP capability** — need to confirm: (a) does it fire on a closed-lid MacBook (probably not)? (b) does it launch a new Claude Code session or inject a prompt into an existing one? (c) does it queue if Mac is asleep, or fail silently? Fallback if (a) fails: macOS `launchd` with `caffeinate` wrapper. Fallback if (b/c) unacceptable: switch scheduled Claude runs to an always-on home server or cheap EC2 spot running Claude Code Docker.
2. **Claude-in-Chrome MCP on Deepvue** — Deepvue is not officially supported; UI may change. Robustness plan: `/swing-deep-analyze` skill runs a precheck that verifies (a) Chrome is running, (b) Deepvue tab is open, (c) user is logged in (tests for a logged-in-only DOM element), (d) Claude-in-Chrome extension is connected. On any failure, post a Slack message with the specific failure and abort; do not partial-complete.
3. **Claude Code non-interactive invocation** — need to confirm Claude Code CLI can run a slash command headless and exit. Tested during implementation bootstrap.
4. **Max rate limits** — after first week of scheduled runs, measure actual message usage vs 5-hour window limits. Budget assumption: ~30 messages / 5h window for scheduled + ad-hoc combined. If exceeded: reduce deep-analysis top-10 to top-5, move weekly synth to Monday morning when limits reset.

### Three analysis layers

| Layer | When | Input | Output |
|---|---|---|---|
| **Base thesis** | 6:30am PT on pending ideas | yfinance fundamentals + setup evidence | One-paragraph thesis stored as `base_thesis` |
| **Deep thesis** | 2:30pm PT on top-10 active ideas | Claude-in-Chrome pulls Deepvue data panel + screenshots daily/weekly/60m charts | Multi-section structured analysis stored as `deep_thesis` |
| **Weekly synthesis** | Sunday 5pm PT | Last 5 daily snapshots per idea + stage transitions + user notes | Weekly review stored as `snapshot_type='weekly'` and appended to journal |

### Slash commands

| Command | Purpose | Scheduled or ad-hoc |
|---|---|---|
| `/swing-analyze-pending` | Base thesis for pending ideas | Scheduled 6:30am PT |
| `/swing-deep-analyze` | Deepvue + vision deep dive on top 10 | Scheduled 2:30pm PT |
| `/swing-weekly-synth` | Sunday weekly synthesis | Scheduled Sun 5pm PT |
| `/swing-analyze <TICKER>` | On-demand full analysis for ANY ticker | Ad-hoc |
| `/swing-review <TICKER>` | Pull existing idea timeline + latest analysis | Ad-hoc |
| `/swing-compare <T1,T2,...>` | Side-by-side setup comparison | Ad-hoc |
| `/swing-model-book-add` | Manually add a historical example | Ad-hoc |

Skills live in `.claude/skills/` as markdown templates, invoked by `scheduled-tasks` MCP for scheduled runs.

### Railway endpoints consumed by Mac-Claude

**Authentication model**: Mac-Claude uses a shared secret stored locally in `~/.config/trend-trading-mcp/swing-api.token` and sent as `Authorization: Bearer <token>` header. Railway validates against env var `SWING_API_TOKEN`. Token is a one-time rotated 32-byte hex string; manual rotation process documented in the implementation plan. For ad-hoc `/swing-analyze` commands the same token is used.

**Idempotency**: write endpoints accept an optional `Idempotency-Key` header (UUID). Railway dedupes by this key for 24h so retried POSTs don't double-insert.

**Endpoints**:

```
# Read
GET  /api/swing/ideas?thesis_status=pending&limit=20
GET  /api/swing/ideas/<id>
GET  /api/swing/ticker/<TICKER>/bars?tf=daily|weekly|60m&lookback=<days>
GET  /api/swing/ticker/<TICKER>/fundamentals

# Write (Mac → Railway)
POST /api/swing/ideas/<id>/thesis            body: { layer: 'base'|'deep', text, model, sources?, deepvue_panel? }
POST /api/swing/ideas/<id>/snapshots         body: { snapshot_date, snapshot_type, claude_analysis?, analysis_sources?, deepvue_panel?, chart_urls? }
POST /api/swing/ideas/<id>/events            body: { event_type, payload, summary }
POST /api/swing/ideas/<id>/charts            multipart: { file, timeframe, source, annotations?, caption? }  (returns blob URL)

# Run detection on arbitrary ticker (for /swing-analyze <TICKER>)
POST /api/swing/ticker/<TICKER>/detect       body: {}   returns: { ticker, setups: [SetupHit...], fundamentals, market_health }
```

Full OpenAPI schemas live in `api/endpoints/swing.py` Pydantic models; implementation plan will specify each.

### Beyond mechanical detection — where Claude adds unique value

1. **Theme clustering** — weekly Claude groups active ideas by sector/theme, surfaces rotation.
2. **Narrative scoring** — at thesis generation, Claude assesses whether the *story* justifies the price action (theme leader vs sympathy chaser).
3. **Exhaustion sentiment** — when exhaustion_extension fires, Claude reads news to distinguish "healthy extension" from "euphoric blow-off."
4. **Pre-earnings guidance** — 3 days before an idea's earnings, Claude recommends sizing action per Kell's earnings rules.
5. **Post-trade retrospective** — on idea exit, Claude auto-drafts a "what went right/wrong" entry.

### Ad-hoc `/swing-analyze <TICKER>` flow

```
1. Claude Code (Mac) fetches daily + weekly + 60m bars via Railway → yfinance
2. Runs all 6 detectors for the ticker (even if universe-absent)
3. Fetches fundamentals
4. If Deepvue tab is open → Claude-in-Chrome captures data panel + charts
5. Generates full thesis + cycle stage read
6. Offers two save options:
   - "Save as watching" → new swing_ideas row with status='watching'
   - "Just analyze" → output to chat only, nothing persisted
```

Variants: `--save` (skip confirm), `--compare T1,T2` (peer comparison).

---

## 9. Pipeline Schedule

### Weekly calendar

```
           Mon    Tue    Wed    Thu    Fri    Sat    Sun
6am PT     [A]    [A]    [A]    [A]    [A]    -      -
6:30am PT  [B]    [B]    [B]    [B]    [B]    -      -
2pm PT     [C]    [C]    [C]    [C]    [C]    -      -
2:30pm PT  [D]    [D]    [D]    [D]    [D]    -      -
4:30pm PT  -      -      -      -      -      -      [F]         ← universe refresh first
5:00pm PT  -      -      -      -      -      -      [E]         ← weekly synthesis reads refreshed universe
```

- [A] [C]: triggered by a single Vercel cron → `/api/cron/daily-dispatcher` (weekdays at 13:00 + 21:00 UTC; handler branches on hour). Dispatcher also invokes the existing `daily-screeners` and `market-monitor` endpoints as internal calls — those endpoints are no longer standalone Vercel crons.
- [F]: triggered by `/api/cron/weekend-refresh` (Sundays at 23:30 UTC).
- [B] [D] [E]: `scheduled-tasks` MCP → Claude Code on Mac (not Vercel crons).

**Vercel cron count: 2 total** (fits Hobby plan). The two existing `daily-screeners` and `market-monitor` cron entries in `vercel.json` are **removed**; their handlers are invoked from `daily-dispatcher` instead.

**Timing tradeoff**: existing `market-monitor` was firing at 21:30 UTC; under the consolidated schedule it fires at 21:00 UTC (30 min earlier). Both are post-close from a market-hours perspective; if something downstream requires exactly +30min after close, revert `market-monitor` to its own cron at the cost of a third entry.

### [A] Pre-market detection (6am PT weekdays — invoked by `daily-dispatcher` @ 13:00 UTC)

The dispatcher calls `run_swing_premarket_detection()` which:

1. Resolve universe (Deepvue → backend fallback)
2. Bulk-fetch daily + weekly bars (yfinance)
3. Compute indicators (EMAs, SMAs, phase osc, ATR, RS vs QQQ)
4. Run **5 detection-oriented** detectors: Wedge Pop, EMA Crossback, Base-n-Break, Reversal Extension, Post-EPS Flag Base. (Exhaustion Extension is warning-only; it runs in [C] against already-active ideas.)
5. Score + rank by confluence
6. Market health snapshot (QQQ vs 20-EMA)
7. Upsert `swing_ideas`; write `stage_transitions` where stages changed; invalidate ideas with Wedge Drop signal
8. Write daily snapshot rows (price/indicator only; `claude_analysis` blank)
9. Post Slack digest to `#swing-alerts` with market health, top 10 by confluence, stage transitions, invalidations, "⏳ analysis pending"

The dispatcher then also invokes the pre-existing `run_daily_screeners()` for SPY day-trading coverage.

### [B] Base thesis (6:30am PT — Mac)

Claude Code `/swing-analyze-pending`:
1. `GET /api/swing/ideas?thesis_status=pending&limit=20`
2. For each: read fundamentals + detection_evidence, generate one-paragraph thesis
3. `POST` thesis back
4. Slack update: "✅ Base thesis ready for N ideas"

### [C] Post-market snapshot + exhaustion scan (2pm PT — invoked by `daily-dispatcher` @ 21:00 UTC)

The dispatcher calls `run_swing_postmarket_snapshot()` which:

1. For each active `swing_ideas` row: pull today's bar, recompute indicators, re-check cycle stage
2. Write stage transitions where applicable
3. Run **Exhaustion Extension detector** against all active ideas (not universe-wide) — set `risk_flags` and write `exhaustion_warning` events
4. Check stop violations → status='invalidated' with reason
5. Append daily snapshot rows (price/indicator; `claude_analysis` blank for Mac to fill)
6. Slack digest: stage transitions, exhaustion warnings, stop-outs, "🔍 deep analysis kicking off"

The dispatcher then also invokes the pre-existing `run_market_monitor()` for end-of-day market tracking.

### [D] Deep analysis (2:30pm PT — Mac)

Claude Code `/swing-deep-analyze`:
1. Precheck: Deepvue tab open? If not, Slack prompts user and aborts gracefully
2. Get top 10 active ideas ranked
3. For each ticker (priority order):
   1. Claude-in-Chrome → navigate Deepvue to ticker chart
   2. Screenshot daily → upload to Vercel Blob
   3. Switch TF to weekly → screenshot
   4. Switch to 60m → screenshot
   5. Scrape data panel
   6. Read recent snapshot history from Railway
   7. Claude Opus (vision) analyzes 3 charts + data panel
   8. POST snapshot with `claude_analysis`, chart URLs, `deepvue_panel`
   9. Sleep 10s
4. Slack: "✅ Deep analysis complete. N warnings, M ready-to-add"

### [F] Universe refresh (Sunday 4:30pm PT — invoked by `weekend-refresh` cron) — runs FIRST on Sunday

`weekend-refresh` handler calls `run_swing_universe_refresh()`:
1. Skip if Deepvue-sourced universe is <7 days old
2. Otherwise run backend generator (Section 7 stages 1-4)
3. Upsert into `swing_universe` with `source='backend-generated'`
4. Populate `extras` fundamentals cache
5. Slack: "🔄 Backend universe refreshed (N tickers)"

### [E] Weekly synthesis (Sunday 5pm PT — Mac) — runs SECOND, reads refreshed universe

Claude Code `/swing-weekly-synth`:
1. For each active idea: read week's snapshots + transitions + user notes → generate weekly review → POST as `snapshot_type='weekly'`
2. For closed ideas this week: generate retrospectives, prompt user for model-book promotion
3. Theme clustering across active tickers (joins against refreshed universe extras for sector/theme tags)
4. Append summary to this week's journal entry
5. Slack: "📋 Weekly Swing Review"

### Failure modes

| Failure | Behavior |
|---|---|
| Railway down | Vercel cron retries 3× with backoff; Slack alert on final fail |
| yfinance rate limit | Exponential backoff; drop flaky tickers, Slack logs count |
| Mac offline | Ideas remain `thesis_status=pending`; next run picks them up |
| Deepvue tab closed at 2:30pm | Deep analysis aborts gracefully; Slack prompts user |
| Claude-in-Chrome extension missing | Precheck detects, aborts, Slack asks user to install |
| Max rate limit hit | Claude Code pauses, retries after window reset |
| Empty universe (no Deepvue + no backend) | "🚨 No universe — upload Deepvue CSV or wait for Sunday backend refresh" |
| Bad stage detection | Events are append-only; manual override via `/swing-ideas/[id]` |

### Idempotency

All Railway crons are idempotent. Snapshots keyed on `(idea_id, snapshot_date, snapshot_type)` with unique index. Stage transitions only written when stage actually changes. Re-triggering any run is safe.

---

## 10. Frontend: `/swing-ideas` Page

Added to sidebar between `/screener` and `/ideas`. Built with existing stack (Next.js 16, Tailwind 4, shadcn/ui, SWR hooks, railwayFetch proxy).

### Layout — tabbed

```
/swing-ideas
├── Active      (status in 'triggered'|'adding'|'trailing')
├── Watching    (status = 'watching')
├── Exited      (status in 'exited'|'invalidated')
├── Universe    (CSV upload, ticker CRUD)
├── Model Book
└── Weekly      (weekly syntheses archive)
```

### Active / Watching / Exited

Table-based list sorted by confluence score. Market health bar at top. Expandable rows with:
- Base thesis (truncated)
- 2-sentence stage evolution summary
- Inline actions: View Detail, Add Note, Upload Chart, Mark Invalidated, Promote to Model Book

### Idea detail `/swing-ideas/[id]`

Single-page layout with sticky header + scroll sections:
- **Header**: ticker, status, cycle stage, confluence, detection age, next earnings
- **Thesis**: base thesis + deep thesis (with regenerate button)
- **Timeline**: chronological event list (detections, snapshots, transitions, user notes, charts, warnings, earnings)
- **Charts**: tabs for daily / weekly / 60m / uploads / annotated; grid view with lightbox
- **Fundamentals**: revenue/EPS growth, beta, ADV, theme, next earnings, link to full Deepvue snapshot

Actions: add note, upload chart, record trade, mark invalidated, promote to model book.

### Universe tab

- Current list with source label and freshness badge
- Buttons: Upload CSV (with Replace/Add toggle), Add Ticker, Export Current, View History
- Filter + sort
- Per-row remove

CSV upload modal: radio for Replace/Add, preview of parsed tickers, column mapping for Deepvue extras.

### Model Book tab

Grid of cards filterable by setup, outcome, theme, tags. Card → detail page with narrative, charts, takeaways. "+ Add manually" button for historical examples.

### Weekly tab

Chronological list of weekly syntheses, most recent expanded by default. Links to journal entries.

### Data flow

```
Hooks (SWR pattern):
  use-swing-ideas.ts         list with filters + sort
  use-swing-idea-detail.ts   one idea + timeline + snapshots + charts
  use-swing-universe.ts      universe CRUD
  use-swing-model-book.ts    model book list + detail
  use-swing-weekly.ts        weekly archive

API routes (Next.js proxies to Railway):
  /api/swing/ideas
  /api/swing/ideas/[id]
  /api/swing/ideas/[id]/snapshots
  /api/swing/ideas/[id]/events
  /api/swing/ideas/[id]/charts
  /api/swing/universe
  /api/swing/universe/upload (multipart)
  /api/swing/model-book
  /api/swing/weekly
```

### Mobile

Responsive but not mobile-first. Mobile collapses to read-only timeline echoing Slack; universe management and chart upload are desktop-only (aligns with Deepvue being desktop-only).

---

## 11. Module/File Layout

```
api/indicators/swing/
├── __init__.py
├── setups/
│   ├── __init__.py
│   ├── base.py                    # SetupHit dataclass, shared helpers
│   ├── wedge_pop.py               # new daily-TF detector (Kell's Wedge Pop)
│   ├── ema_crossback.py           # new daily-TF detector (Kell's EMA Crossback)
│   ├── base_n_break.py            # new daily-TF detector (Kell's Base-n-Break)
│   ├── reversal_extension.py      # new daily-TF detector (Kell's Reversal Extension)
│   ├── exhaustion_extension.py    # new — warning-only, runs post-market [C]
│   └── post_eps_flag.py           # new — requires earnings-calendar provider
├── universe/
│   ├── base_tickers.json
│   ├── resolver.py                # Deepvue vs backend fallback logic
│   └── generator.py               # backend universe generator (4 stages)
├── confluence.py                  # scoring logic
├── earnings_calendar.py           # yfinance + Finnhub provider
└── market_health.py               # QQQ 20-EMA green/yellow/red

api/endpoints/
└── swing.py                       # all /api/swing/* endpoints

frontend/src/app/swing-ideas/
├── page.tsx                       # tabbed main
└── [id]/
    └── page.tsx                   # idea detail

frontend/src/components/swing/
├── active-list.tsx
├── idea-timeline.tsx
├── thesis-panel.tsx
├── chart-gallery.tsx
├── universe-manager.tsx
├── model-book-grid.tsx
└── weekly-synthesis.tsx

frontend/src/hooks/
├── use-swing-ideas.ts
├── use-swing-idea-detail.ts
├── use-swing-universe.ts
├── use-swing-model-book.ts
└── use-swing-weekly.ts

frontend/src/app/api/swing/        # proxy routes
└── [...]/route.ts

frontend/src/app/api/cron/
├── daily-dispatcher/route.ts      # NEW: weekdays 13:00+21:00 UTC, branches by hour
│                                  #   13:00 → swing pre-market detection + existing daily-screeners
│                                  #   21:00 → swing post-market snapshot + existing market-monitor
├── weekend-refresh/route.ts       # NEW: Sundays 23:30 UTC — swing universe refresh
├── daily-screeners/route.ts       # EXISTING endpoint — retained as internal function, no longer a cron
└── market-monitor/route.ts        # EXISTING endpoint — retained as internal function, no longer a cron

.claude/skills/
├── swing-analyze-pending.md
├── swing-deep-analyze.md
├── swing-weekly-synth.md
├── swing-analyze.md
├── swing-review.md
├── swing-compare.md
└── swing-model-book-add.md

alembic/versions/
└── YYYYMMDD_swing_tables.py       # migration for 7 new tables

frontend/vercel.json                # CONSOLIDATED to 2 cron entries total:
                                    #   - /api/cron/daily-dispatcher  (weekdays 13:00,21:00 UTC)
                                    #   - /api/cron/weekend-refresh    (Sundays 23:30 UTC)
                                    # Existing daily-screeners + market-monitor entries REMOVED;
                                    # their handlers are invoked internally from daily-dispatcher.
                                    # Fits Vercel Hobby plan's 2-cron limit.
```

---

## 12. Out of Scope (for MVP)

Deliberate deferrals to keep the spec actionable:

- **Short trades** — MVP is long-only. Wedge Drop / down-cycle detection structure is in place in the schema (`direction='short'` allowed) but detectors not implemented.
- **Trade execution tracking** — no `swing_trades` table yet; ideas track state but not actual fills/exits with P&L. Reuse existing `/log-trade` manually for now. Build `swing_trades` in a follow-up spec once the detection + analysis layer stabilizes.
- **Automated pyramiding calculator** — Kell's step-by-step add logic isn't automated; sizing is suggested at detection, user manages adds manually.
- **Backtesting** — no historical backtest of the 6 detectors. Leverage existing `vectorbt_engine.py` later.
- **Position-level exposure enforcement** — 30% rule is displayed (market health bar), not enforced on trades.
- **Real-time intraday swing alerts** — detection only runs on daily close. Intraday moves not tracked.
- **TradingView / Thinkorswim CSV imports** — Deepvue CSV only for MVP. Same schema can extend if needed.
- **Chart annotation tool in-app** — user uploads pre-annotated charts (from TV/TOS/Deepvue) rather than drawing inside our app. Claude-annotated overlays are auto-generated, not user-editable in-app.
- **Setup dismissal / mute** — no per-ticker blacklist yet; manage by removing from universe.

---

## 13. Success Criteria

MVP is complete when:

1. **Detection loop works end-to-end**: 6am PT cron → 6 detectors run → Slack digest posts → `/swing-ideas` Active tab shows fresh setups with populated base theses by 7am PT.
2. **Universe management is functional**: user can upload a Deepvue CSV, see it become the active universe, and see a freshness badge.
3. **`/swing-analyze NVDA` ad-hoc command returns a full thesis** for any ticker, including one not in the universe.
4. **Daily snapshots accumulate** on each active idea. Clicking an idea on `/swing-ideas/[id]` shows a timeline with at least 3-5 event types.
5. **Deep analysis at 2:30pm PT successfully screenshots Deepvue** for at least one ticker and records analysis to the snapshot row with chart URLs.
6. **Weekly synthesis produces a readable Weekly tab entry** on Sunday with at least a theme summary + per-idea evolution notes.
7. **Model book has 5+ exemplary setups** populated (a mix of historical/manual + promoted closed ideas).
8. **Graceful degradation verified**: when Mac is offline, next run catches up without data loss; when Deepvue tab is closed, deep analysis alerts the user and skips cleanly.
9. **No Claude API spend** — verified by: (a) grep of Railway backend source confirms no `anthropic\.` or `from anthropic` imports outside tests, (b) Anthropic billing console shows no new usage on user's org over the first week post-launch.
10. **Integration leaves existing systems untouched**: SPY day-trading, `/trade-plan`, existing `/screener`, `/ideas`, and journal all continue to work as before.

---

## 14. Open Questions (for implementation phase)

- **Exact Finnhub vs yfinance fallback logic for earnings calendar** — needs validation with real tickers during plan phase. **Gates Post-EPS Flag Base detector.** Mitigation: if earnings calendar is unreliable at implementation time, ship MVP with 5 detectors (drop Post-EPS Flag Base to a follow-up spec) rather than ship a noisy 6th.
- **Chart screenshot reliability via Claude-in-Chrome** — Deepvue's UI may change; need a small robustness pass when writing `/swing-deep-analyze` skill.
- **Vercel Blob quota & pricing assumptions** — charts accumulate over time; may need a retention policy (e.g., keep all user-uploaded and Claude-annotated; prune Deepvue-auto screenshots after 90 days).
- **DST handling for crons** — plan to use Vercel's cron timezone support rather than hard-coded UTC offsets.
- **Rate-limit pacing on Claude Max** — after first week of running all scheduled tasks, measure actual usage vs the 5-hour-window cap; adjust batch sizes or stagger timing if needed.
- **Deep-analysis wall-clock** — 10 tickers × (3 screenshots + data-panel scrape + vision call) is estimated at 15-20 min but unverified. First implementation run should log timing per step; if runs push past 30 min, reduce to top-5 or parallelize at 2 concurrent.
- **CSV re-upload semantics** — when user uploads with "Replace" toggle: prior `deepvue-csv` rows are soft-deleted (`removed_at=NOW()`) rather than hard-deleted, preserving audit trail. "Add" toggle: existing active rows untouched, new rows added, duplicate tickers ignored (no error, no overwrite of `extras`). Documented on upload modal.
- **Ticker validation on `/swing-analyze <TICKER>`** — before running detectors, Railway validates ticker: (a) yfinance returns >= 60 days of bars, (b) last_close >= $1, (c) avg daily volume > 0. On fail, return a structured error; Claude Code surfaces to user as "ticker X not tradeable / insufficient data."

---

## 15. Follow-Up Specs (not this one)

Explicitly deferred to future specs:

1. **Scanner integration extensions** — TradingView / ThinkorSwim CSV imports beyond Deepvue (original brainstorm item C; narrowed to Deepvue for MVP since user has it and it's the richest).
2. **Swing trade execution & P&L tracking** — dedicated `swing_trades` table, pyramid-add flows, target/stop execution tracking.
3. **Shorts / down-cycle setups** — Wedge Drop, EMA Crossback (from below), Base-n-Break (breakdown), Reversal Extension at highs.
4. **Backtesting** — historical validation of the 6 MVP detectors with vectorbt.
5. **Setup performance dashboard** — aggregate R-multiple and win rate per setup over time; feeds back into confluence scoring.

---

## References

- [docs/kell/source-notes.md](../../kell/source-notes.md) — Oliver Kell methodology source
- [docs/saty_trading_skill.md](../../saty_trading_skill.md) — existing Saty trading skill
- [docs/superpowers/specs/2026-04-12-trading-companion-design.md](./2026-04-12-trading-companion-design.md) — prior trading companion design
- Existing Saty setups: `api/indicators/satyland/setups/`
- Existing screener patterns: `frontend/src/components/screener/`, `api/endpoints/screener.py`
- Existing cron infrastructure: `frontend/vercel.json`, `api/endpoints/scheduled.py`
