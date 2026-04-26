---
description: Manual universe edits for the morning screener — add/remove/replace/clear tickers in swing or position mode via Railway API.
trigger_phrases:
  - /screener-universe-edit
---

# /screener-universe-edit — Manual universe edits for the morning screener

Mutates the active screener universe via the Railway API. Persists overrides
across CSV refreshes; per-mode (swing | position).

## Subcommands

- `/screener-universe-edit show [--mode swing|position]`
- `/screener-universe-edit add NVDA, AMD, MXL [--mode swing]`
- `/screener-universe-edit remove TSLA [--mode swing]`
- `/screener-universe-edit replace NVDA, AMD [--mode swing]`
- `/screener-universe-edit clear [--mode swing]`

Default mode is `swing`.

## Auth & base URL

Same conventions as the swing skills (see `.claude/skills/_swing-shared.md`):

- Bearer token at `~/.config/trend-trading-mcp/swing-api.token`
- Base URL from `RAILWAY_SWING_BASE` env, fallback
  `https://trend-trading-mcp-production.up.railway.app`

## Implementation

Parse the user input. Then:

1. **show**

   ```bash
   curl -sf "$BASE/api/screener/universe?mode=$MODE" \
     -H "Authorization: Bearer $TOKEN" | jq .
   ```

   Render the output as a table:

   ```
   Mode: swing
   Base source: deepvue
   Base size: 524 tickers
   Manual added: NVDA, AMD, MXL (3)
   Manual removed: TSLA (1)
   Effective size: 526 tickers
   ```

2. **add / remove / replace** — all use POST `/api/screener/universe/update`:

   ```bash
   curl -sf -X POST "$BASE/api/screener/universe/update" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"mode\": \"$MODE\", \"action\": \"$ACTION\", \"tickers\": $TICKERS_JSON}"
   ```

   Where `$ACTION` is `add` / `remove` / `replace` and `$TICKERS_JSON` is a
   JSON array. Tickers should be uppercased and trimmed.

3. **clear** — POST with `action: "clear_overrides"` and no tickers.

## Failure modes

- Token file missing: `echo "token file missing"` and exit 1.
- HTTP non-2xx: print response body, exit 2. Do NOT retry silently.
- Empty ticker list for add/remove/replace: tell the user and exit without
  calling the API.

## Examples

User: `/screener-universe-edit add NVDA, AMD, MXL`

Action: parse 3 tickers, POST `{mode:"swing", action:"add", tickers:["NVDA","AMD","MXL"]}`,
then run `show` to print the new state.

User: `/screener-universe-edit remove TSLA --mode position`

Action: POST `{mode:"position", action:"remove", tickers:["TSLA"]}`, then `show` for position mode.
