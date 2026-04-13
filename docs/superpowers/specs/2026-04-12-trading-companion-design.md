# Trading Companion System — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Project:** trend-trading-mcp (extends existing infrastructure)

## Overview

A Claude-powered trading companion that integrates with TradingView to deliver daily pre-market plans, real-time setup alerts with probability-driven grading, trade logging via voice/text, journaling, and performance analytics. All input happens through Slack, Claude CLI, or Claude Desktop. All data persists in Supabase. Viewing and analytics happen on the existing Next.js frontend.

**One-line summary:** TradingView monitors the market → Claude grades setups and manages your workflow → Supabase stores everything → Next.js displays it.

---

## Section 1: Scheduled Touchpoints (PST)

| Time (PST) | Name | What It Does | Channel |
|---|---|---|---|
| 5:30am | Morning Brief | ES/SPX overnight levels, ATR levels, structural bias, VIX, confluence zones, quant data | Slack summary + Supabase `daily_plans` |
| 5:45-6:30am | Opening Trade Plan | Mark up key levels, only flag pre-market trades if VERY clear | Slack |
| 6:40am | ORB Marker | Logs 10-min Opening Range High/Low automatically | Slack ping |
| 6:40am-9:30am | Active Session | TradingView webhook alerts fire when playbook setups trigger. Trade logging via Slack/CLI/Desktop | Slack alerts |
| 7:00am | Trend Time | "Trend time. Ribbon should be establishing direction. Look for Flag Into Ribbon and continuation setups." | Slack alert |
| 8:20am | Euro Close Warning | "Euro close in 10 mins (8:30am PST). Watch for reversals and volatility shift." | Slack alert |
| 9:30am | Midday Nudge | "Break time. Session so far: X trades, +Y R. Step away from charts." | Slack nudge |
| 12:00-1:00pm | Power Hour | Webhook alerts active again for clear setups | Slack alerts |
| 1:00pm | Journal Prompt | "Session over. What did you trade? How'd you feel? What worked?" Structured prompt, accepts natural language/voice replies | Slack prompt → Supabase |
| 5:00pm | Next-Day Prep | Key levels for tomorrow, overnight context, setups to watch | Slack + Supabase |
| Friday 1:00pm | Weekly Review | Auto-generated performance analytics posted to Slack | Slack + Supabase `weekly_reviews` |

---

## Section 2: Data Layer (Supabase Schema)

### `daily_plans`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| date | date | Trading day |
| ticker | text | Default SPY/ES |
| structural_bias | text | Strongly Bullish / Bullish / Neutral / Bearish / Strongly Bearish |
| atr_levels | jsonb | All fib levels (23.6%, 38.2%, 61.8%, 100%, extensions) |
| ribbon_state | text | Bullish / Bearish / Chopzilla |
| phase_state | text | Green / Red / Compression |
| vix_reading | float | Current VIX |
| key_levels | jsonb | Confluence zones, PDH/PDL/PMH/PML |
| or_high | float | Opening Range High (filled at 6:40am) |
| or_low | float | Opening Range Low (filled at 6:40am) |
| mtf_scores | jsonb | MTF Score Dashboard values per timeframe |
| plan_notes | text | Free-form notes |
| setups_to_watch | jsonb | Array of setup objects |
| updated_at | timestamptz | |
| created_at | timestamptz | |

### `trades`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| date | date | Trading day |
| ticker | text | |
| direction | text | long / short |
| setup_type | text | Enum (9 values): orb, vomy, ivomy, flag_into_ribbon, golden_gate, squeeze, divergence_from_extreme, eod_divergence, wicky_wicky. Note: vomy and ivomy are separate enum values (mirror setups with same flag structure but opposite direction logic) |
| instrument | text | e.g. "SPY 560C 0DTE" |
| trigger | text | What triggered entry (text) |
| entry_price | float | |
| exit_price | float | |
| stop_price | float | |
| target_price | float | |
| sizing | int | Number of contracts |
| risk_amount | float | Dollar risk |
| r_multiple | float | Calculated: (exit - entry) / (entry - stop) |
| pnl | float | Dollar P&L |
| status | text | open / closed / stopped_out / incomplete |
| grade | text | A+ / A / B / skip |
| green_flags | jsonb | Full flag breakdown with pass/fail per flag |
| mtf_scores | jsonb | MTF scores at time of entry |
| probability | float | Estimated or backtested probability at entry |
| reasoning | text | Full grading reasoning text |
| daily_plan_id | uuid | FK to daily_plans (nullable) |
| alert_id | uuid | FK to alerts (nullable, set when trade created from "take" reply) |
| notes | text | |
| entered_at | timestamptz | |
| exited_at | timestamptz | |
| updated_at | timestamptz | |

### `journal_entries`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| date | date | Trading day |
| emotional_state | text | focused / anxious / overconfident / tilted / patient / disciplined |
| what_worked | text | |
| what_didnt | text | |
| lessons | text | |
| followed_rules | boolean | |
| rules_broken | jsonb | Array of strings |
| session_grade | text | A / B / C / F |
| total_trades | int | |
| total_pnl | float | |
| total_r | float | |
| created_at | timestamptz | |

### `alerts`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| date | date | |
| ticker | text | |
| setup_type | text | Same enum as trades |
| direction | text | long / short |
| timeframe | text | 3m / 10m / 1h |
| alert_type | text | webhook / scheduled |
| grade | text | A+ / A / B / skip |
| details | jsonb | Levels, ribbon state, phase, flags, MTF scores, probability, reasoning |
| acknowledged | boolean | |
| traded | boolean | Links to trade if taken |
| trade_id | uuid | FK to trades (nullable, bidirectional with trades.alert_id) |
| updated_at | timestamptz | |
| created_at | timestamptz | |

### `notes`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| date | date | |
| ticker | text | Optional |
| content | text | Raw note content |
| category | text | observation / emotional / setup / lesson (auto-tagged by Claude) |
| linked_trade_id | uuid | FK to trades (nullable) |
| created_at | timestamptz | |

### `weekly_reviews`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| week_start | date | |
| week_end | date | |
| total_trades | int | |
| wins | int | |
| losses | int | |
| win_rate | float | |
| total_pnl | float | |
| total_r | float | |
| avg_r | float | |
| best_setup | text | Setup type with highest win rate |
| worst_setup | text | Setup type with lowest win rate |
| setup_breakdown | jsonb | Per-setup stats |
| time_of_day_breakdown | jsonb | Performance by hour |
| rules_followed_pct | float | |
| emotional_correlation | jsonb | Emotional state vs. outcomes |
| notes | text | |
| created_at | timestamptz | |

---

## Section 3: TradingView Webhook Alerts

### Endpoint

`POST /api/webhooks/tradingview` on the existing Saty API (Railway).

**Authentication:** The webhook URL includes a secret token as a query parameter: `POST /api/webhooks/tradingview?token=<TRADINGVIEW_WEBHOOK_SECRET>`. The API validates this token before processing. The secret is stored as an environment variable on Railway (`TRADINGVIEW_WEBHOOK_SECRET`). This prevents fabricated alerts from being processed.

### Webhook Payload Format

Configured in TradingView alert message box:

```json
{
  "ticker": "{{ticker}}",
  "timeframe": "{{interval}}",
  "setup": "flag_into_ribbon",
  "direction": "long",
  "price": {{close}},
  "alert": "Price touching 21 EMA with ribbon stacked bullish"
}
```

### Alerts to Configure (per ticker, per timeframe: 3m, 10m, 1h)

| Alert Condition | Setup Type |
|---|---|
| Price touches 13 or 21 EMA with ribbon stacked | flag_into_ribbon |
| Price crosses ribbon and closes other side + retests | vomy / ivomy |
| Price breaks and retests OR high/low (after 6:40am PST) | orb |
| Price breaks through ±38.2% ATR with conviction | golden_gate |
| Phase oscillator compression fires | squeeze |
| Phase oscillator divergence at extreme | divergence_from_extreme |
| Phase oscillator divergence after 12:00pm PST | eod_divergence |
| Tweezer bottom pattern (parallel wicks) | wicky_wicky |

### Webhook Processing Flow

1. Receive payload from TradingView
2. Fetch current indicator state from Saty API (ATR levels, ribbon, phase, structure)
3. Fetch MTF data (scores across 3m, 10m, 1h)
4. Run setup-specific green flag grading (Section 5)
5. Generate probability estimate + reasoning
6. Post formatted alert to Slack with MTF alignment, green flags, grade, and key levels
7. Save to `alerts` table in Supabase
8. Smart deduplication: if same setup AND same direction fires on 3m and 10m within 5 minutes, group into one message showing both timeframes confirming. Cross-direction or cross-setup alerts within the window are always surfaced separately.
9. Conflict filtering: if 1h is bearish but 3m bullish setup fires, flag the conflict and downgrade. This is never deduplicated — always shown.
10. Persist webhook payload immediately on receipt (even if grading fails) so no alerts are lost. Grade asynchronously if needed.

### Slack Alert Format

```
🟢 FLAG INTO RIBBON — SPY Long (3m)
Price: 562.40 | touching 21 EMA

MTF Alignment:
⏱ 3m — Score: +13 | PO: 42.3
⏱ 10m — Score: +11 | PO: 38.1
⏱ 1h — Score: +14 | PO: 55.2
Min score: +11 (Strong) ✅

Green Flags (4/5 = A grade):
✅ Ribbon stacked and fanning (required)
✅ Price at 13/21 EMA pullback (required)
✅ ATR room 58% consumed (required)
✅ Phase oscillator firing up
✅ MTF aligned — all positive, min +11
⬜ Structure: below PMH

Probability: ~65% estimated (n<30, tracking)
Key Levels: Stop below ribbon ~561.20 | Target: Mid-Range 564.80 | R:R 2.1x

Reply "take" to log entry, or ignore
```

### Golden Gate Alert Format (Bilbo-enhanced)

```
🟡 GOLDEN GATE — SPY Long (10m)
Price: 563.80 | broke through +38.2% ATR

60m Phase Oscillator: High + Rising → BILBO CONFIRMED
Backtested probability: 77.7% completion to 61.8% (n=372)
Within 1 hour: 64.8% | Mean time: 34.8 min

MTF Alignment:
⏱ 3m — Score: +12 | PO: 51.4
⏱ 10m — Score: +14 | PO: 48.7
⏱ 1h — Score: +13 | PO: 55.2 (High+Rising)

Invalidation: Trigger level (23.6%) at 561.50
  If held: 84% completion | If broken: 45% → EXIT

Green Flags (5/5 = A+):
✅ Price closed through ±38.2% (required)
✅ 60m PO not counter-trend (required)
✅ ATR room 42% consumed (required)
✅ BILBO confirmed (78% backtested)
✅ Trigger level holding
✅ Time: 7:15am PST (10:15am EST) — 57% hourly rate

Grade: A+ (Bilbo + structure + time)
Target: Mid-Range 565.80 | Full Range 568.20
Entry: Immediate or EMA 8 (10m) pullback (+11% EV)
AVOID: 50% midpoint entry (negative EV)

Reply "take" to log entry, or ignore
```

---

## Section 4: Trade Logging & Journal

### Trade Entry Flow

1. User says (voice or text, any channel): "entered SPY 560C at 2.50, flag into ribbon"
2. Claude parses: setup type, direction, instrument, entry price
3. Claude checks 6-point checklist against parsed data:
   - ✅ Setup: Flag Into Ribbon
   - ✅ Entry: 2.50
   - ❌ Trigger: missing
   - ❌ Stop: missing
   - ❌ Exits: missing
   - ❌ Sizing: missing
4. Claude asks for missing fields in one message: "Got it — SPY 560C long at 2.50, Flag Into Ribbon. Need: stop, target, contracts?"
5. Claude validates against Operator rules:
   - Is it after 6:40am PST? (10-min rule — only applies to first trade of session, not all trades)
   - Is ribbon stacked? (not Chopzilla)
   - ATR room < 70%?
   - Not counter-trend with momentum?
   - If rule violated, warns: "Heads up: ATR 74% consumed. Your rule says <70%. Still want to log?"
6. Saves to `trades` table with status `open`
7. Posts confirmation: "Logged ✓ — SPY 560C × 5 | Entry 2.50 | Stop 2.00 | Target 3.50 | Risk $250 | R-target 2.0R | Flag Into Ribbon"
8. Incomplete trades: if user doesn't reply within 5 minutes, save as `incomplete` status. Follow up once, then stop.

### Alert-to-Trade Flow ("take" reply)

When a user replies "take" (or "entered at X") to a webhook alert in Slack:
1. Claude pre-populates from the alert record: setup_type, direction, ticker, timeframe, entry_price (from alert price), grade, green_flags, mtf_scores, probability, reasoning
2. Only asks for missing fields: instrument (e.g. "SPY 560C"), stop, target, sizing
3. Links the alert to the trade via `alerts.trade_id` and `trades.alert_id`
4. Skips redundant validation (green flags already graded in the alert)
5. Posts confirmation with pre-filled + user-provided data

### Trade Exit Flow

1. User says: "out of SPY calls at 3.20"
2. Claude matches to open trade by ticker + instrument
3. Calculates P&L and R-multiple
4. Asks: "Valhalla scale (70% at first target) or full exit?"
5. Updates trade record with exit price, P&L, R-multiple, status = `closed`
6. Posts summary: "SPY 560C closed +$350 (+2.8R). Flag Into Ribbon. Nice discipline."

### Mid-Session Notes

User talks/types naturally anytime during the session:
- "SPY rejected at the Golden Gate, ribbon starting to fold on 10m"
- "Feeling anxious about this trade"
- "Euro close caused a big wick — be careful around 8:30am PST"

Claude:
1. Timestamps the note
2. Auto-tags category: observation / emotional / setup / lesson
3. Saves to `notes` table linked to today's date
4. Optionally links to a specific trade if context is clear
5. Surfaces relevant notes during end-of-day journal prompt
6. Surfaces patterns in weekly reviews

### Journal Prompt (1:00pm PST daily)

Claude sends structured prompt to Slack:

```
Session Over — Journal Time
Today: 3 trades | +2.1R | $420 P&L

1. How did you feel today? (focused / anxious / patient / tilted / disciplined)
2. What worked?
3. What didn't?
4. Any rules broken?
5. Lessons for tomorrow?

Mid-session notes from today:
• 7:12am — "Feeling anxious about 2nd trade" (emotional)
• 8:35am — "Euro close wick caught me" (observation)

Reply naturally — I'll structure it for you.
```

User replies conversationally or via voice. Claude parses into `journal_entries` table.

---

## Section 5: Green Flag System (Setup-Aware, Probability-Driven)

### Architecture

Each of the 8 setups has:
- **Required flags** — all must be true or grade = Skip
- **Bonus flags** — count determines base grade
- **Modifiers** — upgrade or downgrade the grade
- **Probability** — backtested (Golden Gate) or estimated → self-correcting with real data
- **Reasoning** — full explanation of every flag, score, and probability

### MTF Score Integration

The MTF Score Dashboard (-15 to +15) replaces binary ribbon checks:

| MTF Score | Conviction | Sizing |
|---|---|---|
| ±13 to ±15 | Maximum — fully stacked, all trending | Full size |
| ±10 to ±12 | Strong — mostly stacked | Standard size |
| ±7 to ±9 | Moderate — some crossing | Reduced size or wait |
| ±4 to ±6 | Weak — mixed signals | Skip unless other factors strong |
| ±0 to ±3 | Chopzilla — no clear trend | Do not trade |

**Alignment rule:** All active timeframes must be same sign. Lowest-scoring timeframe sets the ceiling on conviction.

### Setup 1: Flag Into Ribbon

**Required:**
- Ribbon stacked and fanning in trade direction
- Price pulling back to 13 or 21 EMA (blue/orange candle)
- ATR room < 70% consumed

**Bonus:**
- Phase oscillator firing in direction
- MTF alignment (all TFs same sign, min score ≥ +10)
- Structure confirmed (above PMH/PDH for calls, below PML/PDL for puts)
- VIX bias aligns
- Confluence (ATR level clusters with structure level)

*Grading: uses unified formula below.*

### Setup 2: Golden Gate (Bilbo-Enhanced)

**Required:**
- Price broke through ±38.2% ATR with conviction (candle close)
- 60m PO state is NOT counter-trend (not Mid+Falling for bull, not Mid+Rising for bear)
- ATR room < 70% consumed

**Bonus:**
- Bilbo confirmed — 60m PO High+Rising (bull) or Low+Falling (bear)
- Trigger level holding (price hasn't broken back through 23.6%)
- Time of day < 11:00am EST (> 55% hourly completion)
- MTF alignment (all TFs same sign)
- Structure confirmed

**Special rules:**
- Bilbo confirmed alone → auto A+ (78-90% backtested)
- Reasoning includes exact Milkman probability, completion speed, and continuation cascade
- Entry recommendation: immediate at 38.2% (+10% EV) or EMA 8 pullback (+11% EV)
- WARN against 50% midpoint entry (negative EV)
- Invalidation tracking: if trigger level breaks, alert "completion dropped to 45-51%, consider exit"

### Setup 3: Vomy / iVomy

**Required:**
- Ribbon transitioning — price crossed and closed other side
- Price retesting the ribbon (pullback to 13/21 EMA after cross)
- MTF score on execution TF has flipped sign

**Bonus:**
- 48 EMA broken and holding as new support/resistance
- Phase oscillator confirming new direction
- Structure break (below PML/PDL for Vomy, above PMH/PDH for iVomy)
- Higher TF (10m/30m) score starting to shift same direction
- VIX bias aligns

### Setup 4: ORB (10-Min Open Range Breakout)

**Required:**
- OR High and Low marked (after 6:40am PST)
- Candle body close outside OR range (not just wick)
- Retest of breakout level confirmed

**Bonus:**
- MTF scores aligned with breakout direction
- Phase oscillator firing in breakout direction
- Structure confirmed (breakout direction aligns with PDH/PDL/PMH/PML)
- ATR room < 70% consumed
- OR range is not too wide (stop at midpoint within Rule of 10)

### Setup 5: The Squeeze

**Required:**
- Phase oscillator in compression (magenta) or just fired
- Ribbon coiling near 21 EMA — NOT folding/tangling (Chopzilla)
- MTF score magnitude > ±7 on at least one higher TF (directional bias exists)

**Bonus:**
- A+ on MTF dashboard (±15 + compression on any TF)
- All active TF scores aligned same direction
- ATR room < 70% consumed
- Structure confirmed
- VIX not spiking (< 20)

### Setup 6: Divergence From Extreme

**Required:**
- Price made a swing high or low (HOD/LOD)
- Phase oscillator divergence at extreme (lower high on PO for bearish div, higher low for bullish)
- Ribbon showing exhaustion (compressing, slowing, or folding)

**Bonus:**
- Divergence visible on multiple timeframes (3m + 10m)
- Price at an ATR extension level (±61.8% or beyond)
- Volume declining on the second push
- MTF score starting to diverge from price (score weakening while price extends)

### Setup 7: 1-Min EOD Divergence

**Required:**
- Time is after 12:00pm PST (3:00pm EST)
- Phase oscillator divergence — PO too close to middle, new high/low with divergence
- Swing high or low formed

**Bonus:**
- Volume on divergence candle
- Price at ATR extreme (±61.8% or beyond)
- Ribbon showing exhaustion/compression
- Structure level nearby as target (21 EMA, VWAP)

### Setup 8: Tweezer Bottom (Wicky Wicky)

**Required:**
- Two parallel candles with matching bottom wicks (tweezer pattern)
- Price reclaims 50% of the down candle

**Bonus:**
- Phase oscillator showing bullish divergence or reversal
- Tweezer formed at a key level (ATR level, PDL, PML, EMA)
- Volume increasing on reclaim candle
- MTF score not strongly negative (> -10)
- Ribbon starting to flatten or curl up

### Unified Grading Formula

1. All **required** flags must be true → otherwise grade = **Skip**
2. Count bonus flags. Base grade: 4+ = A+, 3 = A, 2 = B, 0-1 = Skip
3. **Modifiers:**
   - Golden Gate with Bilbo confirmed → auto A+ (backtested 78-90%)
   - MTF A+ (±15 + compression) on any TF → upgrade by one grade
   - Counter-trend on 1h (MTF conflict) → downgrade by one grade
   - Time of day penalty (after 1:00pm EST for Golden Gate) → downgrade by one grade
   - Personal win rate (once 30+ trades logged) → overrides estimated probability
4. **Reasoning output always includes:**
   - Setup name + direction + timeframe
   - Each flag with pass/fail and why
   - MTF scores across all active timeframes
   - Probability estimate (backtested, estimated, or personal win rate)
   - Key levels (stop, target, R:R)
   - Any Operator rule violations flagged

### Self-Correcting Probabilities

- Each setup starts with an estimated probability
- Golden Gate uses backtested Milkman data (63-90% depending on Bilbo state)
- After 30+ trades per setup, Claude switches to the user's actual win rate
- Display: "Flag Into Ribbon: estimated ~65% → your actual: 72% (n=38)"
- Divergence alert: "Your Vomy win rate is 35% (n=22) vs estimated 55%. Review entries or remove from playbook."

---

## Section 6: Analytics

### Daily Summary
- Total trades, wins, losses, win rate
- Total P&L, total R, average R per trade
- Best/worst trade
- Rules followed/broken count
- Emotional state from journal

### Weekly Review (auto-generated Friday 1:00pm PST)
- Week-over-week P&L and R comparison
- Win rate by setup type
- Win rate by time of day
- Average R by setup
- Rules compliance %
- Best/worst setup of the week
- Claude recommendation based on patterns

### Monthly Review (computed on-the-fly from weekly_reviews, no separate table)
- Aggregated weekly data
- Setup performance heatmap (setup x week)
- Emotional state correlation (anxious → loss pattern?)
- Progression tracking over time
- R-expectancy per setup

### Natural Language Queries
- "What's my win rate on Flag Into Ribbon this month?"
- "How do I do on trades after 8:00am PST?"
- "Show me my worst trades this week"
- "What's my average R on Golden Gate with Bilbo confirmed?"

---

## Section 7: System Architecture

### Components

| Component | What It Does | Where It Runs |
|---|---|---|
| Saty API | Webhook receiver, indicator calculations, green flag grading | Railway (existing `api/main.py`) |
| Supabase | All persistent data (6 tables) | Supabase (existing project) |
| Slack MCP | Send/receive messages, voice transcription, scheduled alerts | Slack API |
| Scheduled Tasks | 8 daily touchpoints + weekly review | Railway cron jobs calling API endpoints that trigger Claude via Anthropic API, or Supabase pg_cron + edge functions |
| TradingView Webhooks | Real-time setup detection on 3m/10m/1h | TradingView → Saty API |
| Next.js Frontend | Journal, analytics, trade plan viewing | Vercel (existing frontend) |
| Claude | AI layer — parsing, grading, reasoning, conversation | Claude Code / Desktop / Slack |

### New Infrastructure Required

1. `POST /api/webhooks/tradingview` endpoint on existing Saty API
2. 6 new Supabase tables (daily_plans, trades, journal_entries, alerts, notes, weekly_reviews)
3. Slack workspace + channel configuration
4. 8 scheduled Claude tasks (cron)
5. TradingView alert configuration (one-time per ticker per timeframe)
6. **Reworked green flag module** (`api/indicators/satyland/green_flag.py`) — this is a full redesign, not an extension. The existing generic 10-flag system is replaced with 8 setup-specific evaluators with required/bonus flag separation. This is a breaking change to the existing `/api/satyland/trade-plan` endpoint which currently calls `green_flag_checklist()`.
7. **MTF Score calculation** ported to Python (from Pine Script) — new module `api/indicators/satyland/mtf_score.py`
8. **Phase Oscillator zone classification** — new functionality to output zone states ("High+Rising", "Mid+Falling", "Low+Falling") needed for Bilbo filtering. Extends existing `phase_oscillator.py` output.

### MTF Score Specification

The MTF Score is a Python port of the Pine Script MTF Score Dashboard. It calculates a score from -15 to +15 per timeframe.

**Inputs:** OHLCV data for a given timeframe
**Outputs per timeframe:**
```json
{
  "score": 13,
  "po_value": 42.3,
  "in_compression": false,
  "is_a_plus": false
}
```

**Aggregated output (stored in `mtf_scores` jsonb columns):**
```json
{
  "3m": {"score": 13, "po": 42.3, "compression": false},
  "10m": {"score": 11, "po": 38.1, "compression": false},
  "1h": {"score": 14, "po": 55.2, "compression": false},
  "alignment": "bullish",
  "min_score": 11,
  "conviction": "strong"
}
```

**Calculation (15 points):**
- 10 EMA cross comparisons: every pairwise combo of EMA 8, 13, 21, 48, 200 (+1 if A > B, -1 if A < B)
- 5 EMA trend directions: each EMA vs its previous bar (+1 if rising, -1 if falling)
- A+ = |score| == 15 AND compression active

**New endpoint:** `POST /api/satyland/mtf-score` — accepts ticker + list of timeframes, returns scores per TF + alignment analysis.

### Phase Oscillator Zone Classification

Extends the existing `phase_oscillator.py` output to include zone + direction state for Bilbo filtering:

```json
{
  "oscillator": 55.2,
  "phase": "green",
  "zone": "high",
  "direction": "rising",
  "zone_state": "high_rising"
}
```

**Zone thresholds:**
- High: oscillator > 38.2
- Mid: oscillator between -38.2 and 38.2
- Low: oscillator < -38.2

**Direction:** rising if current > previous bar, falling otherwise.

**Zone states used for Bilbo filtering:** `high_rising`, `high_falling`, `mid_rising`, `mid_falling`, `low_rising`, `low_falling`

### Data Flow

```
TradingView Alert → Webhook → Saty API → Green Flag Grading → Slack Alert
                                                                    ↓
User Input (Slack/CLI/Desktop) → Claude → Supabase ← Next.js Frontend
                                            ↓
                              Scheduled Tasks (cron) → Slack
```

### Input Channels

All three support voice (Slack voice messages, iOS/Android dictation, Claude Desktop voice):
- **Slack** — primary mobile/desktop channel for trade logging, notes, journal replies, and receiving alerts
- **Claude CLI** — heavier analysis sessions, querying analytics
- **Claude Desktop** — same as CLI, desktop convenience

---

## Appendix A: Milkman Trades Reference Data

Full data stored in Claude memory (`reference_milkmantrades.md`) and sourced from milkmantrades.com.

Key numbers for Golden Gate grading:
- Bullish GG baseline: 63% (n=3,411)
- Bearish GG baseline: 65% (n=3,200)
- Bullish Bilbo (PO High+Rising): 77.7%
- Bearish Bilbo (PO Low+Falling): 90.2%
- Trigger holds: 84-89% completion
- Trigger breaks: 45-51% completion
- Best entry EV: EMA 8 pullback (+11%) or immediate at 38.2% (+10%)
- NEGATIVE EV: 50% midpoint entry (-5.8%)
- 60m PO is 5-12x more predictive than 10m PO

## Appendix B: MTF Score Dashboard Reference

Full Pine Script source stored in Claude memory (`reference_mtf_score_dashboard.md`). Python port spec defined in Section 7.

Key thresholds:
- ±13 to ±15: Maximum conviction, full size
- ±10 to ±12: Strong, standard size
- ±7 to ±9: Moderate, reduced size
- ±4 to ±6: Weak, skip unless strong other factors
- ±0 to ±3: Chopzilla, do not trade
- Alignment rule: all TFs same sign, weakest link caps conviction

## Appendix C: Operator's Mindset Rules (enforced in trade logging)

1. 10-Minute Rule (no trading 6:30-6:40am PST)
2. No Counter-Trend with Momentum
3. Avoid Chopzilla (folding ribbons)
4. Never Chase Breakouts (wait for retest)
5. The Verbal Audit (narrate thesis before entering)
6. There's Always Another Trade (FOMO prevention)
7. DO NOT DIAMOND HAND (exit if thesis breaks)

## Appendix D: Risk Management Rules (enforced in trade logging)

- Rule of 10: Never risk >10% of session limit on one trade
- Stop on Ribbon Flip: exit immediately
- Stop on EMA Close: exit if price closes wrong side of 21 EMA
- Never Average Down
- Max Loss Limit: define before session
- Skip Undersized Trades: if stop risk exceeds Rule of 10

## Appendix E: Valhalla Scaling (enforced in trade exit flow)

- First ATR Target (61.8%): Sell 70% of position
- Move stop to breakeven on remaining 30%
- Full Range (100%): Sell runners or trail
- Valhalla (beyond 100%): Trail tightly
