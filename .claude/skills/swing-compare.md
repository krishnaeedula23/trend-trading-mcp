---
name: swing-compare
description: Side-by-side setup comparison. Usage `/swing-compare T1,T2,...` (up to 4 tickers).
---

# /swing-compare

## Procedure

1. Parse comma-separated tickers (max 4). Read `_swing-shared.md` prerequisites;
   set `$BASE` and `$TOKEN`.

2. For each ticker, run detectors in parallel:
   ```bash
   curl -sf -X POST "$BASE/api/swing/ticker/$T/detect" \
     -H "Authorization: Bearer $TOKEN"
   ```

3. For each ticker, also fetch existing idea rows if any:
   ```bash
   curl -sf "$BASE/api/swing/ideas?ticker=$T&limit=3"
   ```

4. Render a comparison table:

   | Ticker | Setup fired | Cycle stage | Entry | Stop | Rev YoY | Earnings | Verdict |
   |--------|-------------|-------------|-------|------|---------|----------|---------|
   | NVDA   | Wedge Pop   | wedge_pop   | 102–103.5 | 99.20 | +78% | 32d | Strong |
   | AMD    | none        | —           | —     | —    | +22% | 18d | Pass   |

5. Recommend the strongest setup, or `"none of these qualify — wait."`

## Never

- Pick favorites based on hunches. Use `confluence_score` + `data_sufficient`
  (from `/detect` response) as tiebreakers.
