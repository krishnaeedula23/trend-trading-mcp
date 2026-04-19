---
name: swing-review
description: Pull an existing swing idea's detail + latest thesis. Usage `/swing-review <TICKER>`.
---

# /swing-review

## Procedure

1. Parse `TICKER`. Read `_swing-shared.md` prerequisites; set `$BASE`.

2. List recent ideas for this ticker (no auth on GET):
   ```bash
   curl -sf "$BASE/api/swing/ideas?ticker=$TICKER&limit=5"
   ```
   Show the user a numbered list (most recent first).

3. Let user pick one (or auto-pick #1 if only one active idea).

4. Fetch the full idea row:
   ```bash
   curl -sf "$BASE/api/swing/ideas/$IDEA_ID"
   ```
   Note: `GET /ideas/{id}` returns the idea row but does NOT embed events.
   Plan 4 adds a `/ideas/{id}/events` listing; until then, timeline is
   unavailable in this skill.

5. Render a summary:
   - **Header**: ticker, status, cycle_stage, confluence, detection_age.
   - **Base thesis** (truncate to 600 chars, offer "Show full").
   - **Deep thesis** (if present).
   - **Risk flags**.

6. Offer follow-up actions:
   - "Add note" → POST `/ideas/{id}/events` with `event_type: "user_note"` and
     the user's text as `summary`.
   - "View in browser" → print URL to `/swing-ideas/<id>`.

## Never

- Silently regenerate the thesis. Use `/swing-analyze` for fresh analysis.
