---
name: swing-analyze
description: On-demand Kell+Saty setup analysis for any ticker. Usage `/swing-analyze <TICKER> [--save]`.
---

# /swing-analyze

**Trigger**: user types `/swing-analyze NVDA` (or `--save`) in chat.

## Procedure

1. Parse args: `TICKER` (required, uppercased), `--save` (optional).

2. Read `_swing-shared.md` prerequisites; set `$BASE` and `$TOKEN`.

3. Fetch recent bars (no auth on GET):
   ```bash
   curl -sf "$BASE/api/swing/ticker/$TICKER/bars?tf=daily&lookback=250"
   ```
   Show a compact summary (last 5 bars) to the user.

4. Run detectors (POST, needs auth):
   ```bash
   curl -sf -X POST "$BASE/api/swing/ticker/$TICKER/detect" \
     -H "Authorization: Bearer $TOKEN"
   ```
   Response includes `setups`, `fundamentals`, `market_health`, `data_sufficient`.

5. If `data_sufficient == false`: tell user `"Ticker X: insufficient data
   (reason)."` and exit.

6. Render a thesis for the user in chat. Structure:
   - **Setup**: which Kell setup(s) fired (can be zero — if zero, say "no
     active swing setup, but here is the structural read").
   - **Cycle stage read**.
   - **Levels**: entry zone / stop / first target (from detectors, or
     discretionary if none).
   - **Fundamentals snapshot**: rev YoY, earnings date, beta.
   - **Market context**: QQQ cycle (`market_health.index_cycle_stage` +
     `green_light`).
   - **Verdict**: pass / watch / enter.

7. If `--save` OR user confirms "save as watching":
   - Railway has no "create idea for ad-hoc ticker" endpoint until Plan 4.
     Tell the user: `"Save-as-watching needs Plan 4's idea-create endpoint —
     will persist the analysis as a chat note only."` and do NOT write.

## Note

This skill does NOT call any Railway write endpoint in the MVP. It's
read-only. Thesis lives in the chat transcript.

## Never

- Create a `swing_ideas` row via direct SQL. Wait for Plan 4's ideas POST route.
