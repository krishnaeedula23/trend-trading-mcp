---
name: swing-analyze-pending
description: Generate base theses for all swing ideas with thesis_status='pending'. Scheduled 6:30am PT weekdays.
---

# /swing-analyze-pending

**Trigger**: `scheduled-tasks` MCP at 13:30 UTC (6:30am PT) weekdays, OR manual invocation.

**Budget**: ≤20 ideas per run. One paragraph each. Expect ≤10 Claude messages total.

## Procedure

1. Read `.claude/skills/_swing-shared.md` prerequisites; abort on any failure.
   Set `$BASE` and `$TOKEN` as shown there.

2. Fetch pending ideas:
   ```bash
   curl -sf "$BASE/api/swing/ideas?thesis_status=pending&limit=20"
   ```
   Parse JSON; let `IDEAS=$(jq -c '.ideas[]' <<<"$RESP")`.

3. If `$IDEAS` is empty: Slack `"No pending theses this morning."` and exit 0.

4. For each idea (iterate — do not batch; keep failures isolated):

   a. Extract `IDEA_ID`, `TICKER`, `SETUP_KELL`, `CYCLE_STAGE`,
      `DETECTION_EVIDENCE`, `MARKET_HEALTH` from the row.

   b. Fetch fundamentals (no auth needed on GET):
      ```bash
      curl -sf "$BASE/api/swing/ticker/$TICKER/fundamentals"
      ```

   c. Compose a **one-paragraph base thesis** (4–7 sentences, ≤400 words).
      Ground it in:
      - `setup_kell` / `cycle_stage` and what it means (reference
        `docs/kell/source-notes.md` terminology).
      - `detection_evidence` from the idea row (volume surge, RS, EMA
        positions).
      - `fundamentals` (rev growth YoY, margins, next earnings date).
      - `market_health` (QQQ cycle color).
      Do NOT speculate on news; this is a structural/fundamental read only.

   d. POST the thesis:
      ```bash
      curl -sf -X POST "$BASE/api/swing/ideas/$IDEA_ID/thesis" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Idempotency-Key: $(uuidgen)" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg t "$THESIS_TEXT" \
              '{layer:"base", text:$t, model:"claude-opus-4-7"}')"
      ```

   e. Check status; on non-2xx, log + continue to next idea (don't abort the
      batch).

5. Post a Slack summary: `"✅ Base theses written for N/M ideas"`.

## Output example for one thesis

> NVDA fires a Wedge Pop on declining volume after a three-week consolidation
> above the 10/20 EMAs. RS vs QQQ has turned positive over the last 10
> sessions, and the reclaim bar printed 1.4× avg volume. Fundamentals remain
> the strongest in the cohort: +78% YoY Q revenue, gross margin holding above
> 74%, and guidance reiterated. Next earnings are 32 days out, giving a full
> trading window before event risk. With QQQ above its 20-EMA (green-light
> tape), this sets up as a primary pyramid candidate. Entry zone 102.00–103.50;
> stop under 99.20 (reclaim-bar low); first target at the prior swing high
> near 114.

## Never

- Exceed ~400 words per thesis.
- Invent news.
- Recommend sizing beyond the auto-computed `suggested_position_pct`.
