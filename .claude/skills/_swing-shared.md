<!-- .claude/skills/_swing-shared.md -->
# Swing Skill — Shared Conventions

**Auth**: read the bearer token from `~/.config/trend-trading-mcp/swing-api.token`.
Send as `Authorization: Bearer <token>` on all POSTs. GETs are unauth'd.

**Base URL**: read from `RAILWAY_SWING_BASE` env (falls back to
`https://trend-trading-mcp-production.up.railway.app`).

**Idempotency**: for retry-safe writes, include `Idempotency-Key: <uuid>` with a
stable UUID per logical operation (e.g., per-idea-per-day). Same key + same
endpoint returns the first response verbatim within 24h.

**Model tag**: every thesis POST must include `model` matching the Claude model
that generated the text. Source of truth: `$CLAUDE_MODEL` env set by Claude Code
at invocation time; otherwise hard-code `claude-opus-4-7`. Record in thesis
metadata for later audit.

**Prerequisites to verify at each skill start** (spec §8 prereqs):

1. Token file exists + readable — fail fast with a clear error if missing.
2. `curl -sf "$BASE/health"` returns 200 — if not, Slack the error and abort.
3. For `/swing-analyze-pending` specifically: Mac is awake and plugged in
   (`pmset -g batt`) — if on battery and < 50%, log a warning but proceed.

**Shell snippet for the first two checks:**

```bash
BASE="${RAILWAY_SWING_BASE:-https://trend-trading-mcp-production.up.railway.app}"
TOKEN_FILE="${HOME}/.config/trend-trading-mcp/swing-api.token"
[[ -r "$TOKEN_FILE" ]] || { echo "token file missing at $TOKEN_FILE"; exit 1; }
TOKEN="$(head -n1 "$TOKEN_FILE" | tr -d '[:space:]')"
curl -sf "$BASE/health" >/dev/null || { echo "Railway /health down"; exit 2; }
```

**Failure mode**: any HTTP non-2xx from Railway → print the response, Slack the
error, exit with non-zero status. Do NOT retry silently. The next scheduled run
will pick up the pending idea again.

**Never call the Anthropic API directly** — this is Claude Code on Max.
Generation happens via the LLM already powering this session; we just write
text to Railway via HTTP.

**Known API shape notes (keep in sync with Plans 2/3):**

- `MarketHealth.snapshot` keys: `qqq_close`, `qqq_10ema`, `qqq_20ema`,
  `green_light` (bool), `index_cycle_stage` (`bull|neutral|bear`).
- `GET /api/swing/ideas` supports `?status=`, `?thesis_status=`, `?ticker=`,
  `?limit=` query params (added in Plan 3 Task 10).
- `GET /api/swing/ideas/{id}` returns the full idea row but does NOT embed
  events. Timeline events must be fetched separately — currently there's no
  listing endpoint; Plan 4 adds one.
