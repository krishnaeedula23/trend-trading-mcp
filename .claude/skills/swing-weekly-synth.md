---
description: Sunday 5pm PT weekly swing synthesis — per-idea reviews + theme clustering + journal append. Runs AFTER weekend-refresh universe cron at 4:30pm PT.
trigger_phrases:
  - /swing-weekly-synth
  - weekly swing synthesis
---

# /swing-weekly-synth

See `_swing-shared.md` for env vars and Slack routing.

## Preflight

Quick sanity: `GET $RAILWAY_SWING_BASE/api/swing/universe` — confirm universe resolved (either fresh Deepvue or backend-refreshed). If the `tickers` array is empty:
- Slack: "🚫 Weekly synth aborted: empty universe."
- Exit.

## Step 1: Per-active-idea synthesis

For each idea with status in ('watching','triggered','adding','trailing'):

1. `GET /api/swing/ideas/<id>`
2. `GET /api/swing/ideas/<id>/snapshots` (use last 5)
3. `GET /api/swing/ideas/<id>/events` — filter to `event_type=user_note`
4. Compose a ~150-word synthesis covering:
   - How price evolved vs last week's setup
   - Stage transitions (if any)
   - Any exhaustion warnings
   - Change in thesis strength (improving/deteriorating/unchanged) and why
   - Next-week watch criteria
5. `POST /api/swing/ideas/<id>/snapshots` with:
   ```
   { "snapshot_date": "<Sunday ISO>",
     "snapshot_type": "weekly",
     "claude_analysis": "<the 150 words>",
     "claude_model": "claude-opus-4-7" }
   ```

## Step 2: Closed-idea retrospectives

For ideas closed (status exited|invalidated) in the last 7 days:
1. Gather full timeline (detection → transitions → exit).
2. Generate a "what went right/wrong + takeaway" retrospective (~100 words).
3. POST as `event_type=user_note` to `/api/swing/ideas/<id>/events` with `summary="Retrospective"` and the text in `payload.text`.
4. Offer model-book promotion: Slack DM with ticker + setup + outcome + link to `/swing-ideas/[id]` with auto-opened Promote dialog hint.

## Step 3: Theme clustering

1. `GET /api/swing/universe` → pull `extras.fundamentals` sector/theme tags for each ticker.
2. Join with active idea tickers.
3. Group by theme → list tickers per theme with their stages.
4. Identify rotation: which themes gained/lost membership week-over-week (regenerate fresh each time for MVP).

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
