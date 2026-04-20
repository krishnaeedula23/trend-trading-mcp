---
description: Deep swing analysis — tradingview-mcp for charts + indicators, Claude-in-Chrome on Deepvue for fundamentals. Top-10 active ideas. Scheduled 2:30pm PT weekdays via scheduled-tasks MCP.
trigger_phrases:
  - /swing-deep-analyze
  - deep analyze swing ideas
required_mcps:
  - tradingview
  - Claude-in-Chrome
---

# /swing-deep-analyze

## Goal
For each of the top-10 active swing ideas (by confluence_score, excluding ideas whose deep_thesis_at < 24h old), capture charts and indicator reads from TradingView Desktop via tradingview-mcp, scrape the fundamentals panel from Deepvue via Claude-in-Chrome, and POST an updated snapshot with `claude_analysis`, chart URLs, `tv_indicators`, and `deepvue_panel` to Railway.

See `_swing-shared.md` for env vars (`RAILWAY_SWING_BASE`, `SWING_API_TOKEN` file location) and Slack channel routing.

## KNOWN LIMITATION (Plan 4 MVP)

Chart upload to Vercel Blob from the Mac-side skill is **not yet implemented**.
The `@vercel/blob/client.upload()` flow is browser-only (it needs the Vercel
Blob client SDK + `HandleUploadBody` shape). For now:

- Capture charts with `tv_screenshot()` locally
- Save to `~/Downloads/swing-charts/<ticker>-<yyyy-mm-dd>-<tf>.png`
- The POST to `/api/swing/ideas/<id>/snapshots` should set
  `chart_*_url: null` and include the local path in `analysis_sources.local_chart_paths`

Follow-up tracked: add a Mac-callable `POST $RAILWAY_SWING_BASE/api/swing/charts/upload`
endpoint that accepts multipart and forwards to Vercel Blob server-side.

This limitation does NOT block the skill — Claude vision analysis still
runs on the local chart file; only the persisted blob URL is deferred.

## Preflight (abort + Slack warn on any failure — check in order)

1. **tradingview-mcp health**: call `tv_health_check`. If it does not return OK:
   - Post Slack `#swing-alerts`: "⚠️ /swing-deep-analyze aborted: tradingview-mcp not reachable. Is TradingView Desktop running with --remote-debugging-port=9222? See docs/swing/tradingview-mcp-setup.md."
   - Exit.

2. **Deepvue tab check**: use `Claude-in-Chrome.tabs_context_mcp` to list tabs. Is there a tab with URL matching `deepvue.com`? If not:
   - Slack: "⚠️ /swing-deep-analyze aborted: Deepvue tab not open. Please open Chrome → Deepvue → login."
   - Exit.

3. **Deepvue login check**: `Claude-in-Chrome.get_page_text` on the Deepvue tab. Search for a logged-in-only marker (e.g., "Logout" link or user avatar). If missing:
   - Slack: "⚠️ /swing-deep-analyze aborted: not logged into Deepvue."
   - Exit.

4. If tradingview-mcp or Claude-in-Chrome tools are deferred-loaded, fetch schemas first via ToolSearch before proceeding.

## Load top-10 ideas

```
GET $RAILWAY_SWING_BASE/api/swing/ideas?status=watching&limit=20
GET $RAILWAY_SWING_BASE/api/swing/ideas?status=triggered&limit=20
GET $RAILWAY_SWING_BASE/api/swing/ideas?status=adding&limit=20
GET $RAILWAY_SWING_BASE/api/swing/ideas?status=trailing&limit=20
```

Merge, filter client-side to ideas where `deep_thesis_at` is null or older than 24h, sort by `confluence_score` descending, take top 10.

## For each ticker (serial; sleep 10s between)

### 1. Charts via tradingview-mcp (authoritative for chart captures)

**Preferred — single composite screenshot (if `tv_multi_pane` is available):**
- `tv_navigate_symbol(ticker)`
- `tv_multi_pane(ticker, panes=["1D", "1W", "60", "phase_osc"])` — 2×2 layout
- `tv_screenshot()` → save to `~/Downloads/swing-charts/<ticker>-<date>-composite.png`
- Read indicators once: `tv_read_indicators()` → store full dict as `tv_indicators`

**Fallback (if `tv_multi_pane` not available — 3 separate captures):**
- `tv_navigate_symbol(ticker)` → `tv_set_timeframe('1D')` → `tv_screenshot()` → save to `~/Downloads/swing-charts/<ticker>-<date>-daily.png`; `tv_read_indicators()`
- `tv_set_timeframe('1W')` → `tv_screenshot()` → save to `~/Downloads/swing-charts/<ticker>-<date>-weekly.png`
- `tv_set_timeframe('60')` → `tv_screenshot()` → save to `~/Downloads/swing-charts/<ticker>-<date>-60m.png`

The Saty Pine-script indicator values from `tv_read_indicators()` (EMA10, EMA20, Phase Osc, ATR Levels) are authoritative — do not recompute them in Python.

**Do not** use manual DOM scraping or computer-use clicking to capture TV charts.

### 2. Fundamentals via Claude-in-Chrome on Deepvue (data TV doesn't expose)

- Navigate Deepvue to the ticker data panel.
- `get_page_text` → parse into a dict: revenue/EPS growth, beta, ADV, next earnings, theme/sector, narrative.
- If parse fails, store raw text in `deepvue_panel.raw`.

### 3. Read recent snapshot history

`GET $RAILWAY_SWING_BASE/api/swing/ideas/<id>/snapshots` — pull recent history for context (use the first 5).

### 4. Claude vision analysis

Pass chart screenshot(s) + `tv_indicators` + `deepvue_panel` + recent snapshots + prior thesis. Write a 3-paragraph analysis:
- What the chart is showing vs last snapshot (daily action, cycle-stage read per Kell)
- What the Deepvue data panel adds (fundamentals, theme strength, RS)
- Next action: wait / add / trim / exit — with reasoning

### 5. POST snapshot to Railway

```
POST $RAILWAY_SWING_BASE/api/swing/ideas/<id>/snapshots
Authorization: Bearer $SWING_API_TOKEN
Content-Type: application/json

{
  "snapshot_date": "<today ISO>",
  "snapshot_type": "daily",
  "claude_analysis": "<the 3 paragraphs>",
  "claude_model": "claude-opus-4-7",
  "chart_daily_url": "<blob url or null if composite>",
  "chart_weekly_url": "<blob url or null if composite>",
  "chart_60m_url": "<blob url or null if composite>",
  "deepvue_panel": { ... parsed panel ... },
  "analysis_sources": {
    "tv_indicators": { ... from tv_read_indicators() ... },
    "chart_mode": "composite|separate",
    "deepvue_url": "..."
  }
}
```

Also POST `deep_thesis` via `POST $RAILWAY_SWING_BASE/api/swing/ideas/<id>/thesis { layer: "deep", ... }` (Plan 3 endpoint).
Include header: `Idempotency-Key: <idea_id>:<today ISO>` — re-runs on same day are no-ops.

### 6. Sleep 10s before next ticker

## Final Slack message

"✅ Deep analysis complete: N ideas analyzed, M exhaustion warnings reviewed, K ready-to-add."

## Failure modes

- `tv_health_check` fails mid-run: abort remaining tickers, Slack partial count.
- TV screenshot fails for a ticker: skip to next, note in `analysis_sources`.
- Deepvue panel scrape fails: proceed with chart-only analysis; record `"deepvue_panel": null`.
- Max rate limit mid-run: abort, Slack the count completed, leave remaining for next run.
- Railway 5xx: retry once with backoff; if still failing, Slack the error.

## Non-goals

- Don't invent new ideas — only analyze already-active ones.
- Don't touch `swing_ideas.status` from this skill.
- Don't use DOM scraping or computer-use for TV chart capture (use `tv_*` tools only).
