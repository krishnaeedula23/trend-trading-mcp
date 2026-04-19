#!/usr/bin/env bash
# scripts/swing/bootstrap-mac.sh
# One-shot: wires the user's Mac into the swing Claude-analysis layer.
# Idempotent — safe to re-run.
set -euo pipefail

TOKEN_DIR="$HOME/.config/trend-trading-mcp"
TOKEN_FILE="$TOKEN_DIR/swing-api.token"

# ── Check 1: Token file exists ─────────────────────────────────────────────
if [[ ! -f "$TOKEN_FILE" ]]; then
    cat <<EOF
✗ Token file missing at $TOKEN_FILE

To generate + write:
  1. On Railway → trend-trading-mcp → Variables tab → Add variable
       name:  SWING_API_TOKEN
       value: \$(openssl rand -hex 32)     # copy the generated value
  2. Locally on this Mac:
       mkdir -p $TOKEN_DIR
       printf '%s' '<paste-the-token>' > $TOKEN_FILE
       chmod 600 $TOKEN_FILE

Re-run this script after both steps.
EOF
    exit 1
fi

# ── Check 2: Token file mode is 600 ────────────────────────────────────────
mode="$(stat -f '%A' "$TOKEN_FILE")"
if [[ "$mode" != "600" ]]; then
    echo "✗ Token file must be mode 600 (currently $mode). Fix: chmod 600 $TOKEN_FILE"
    exit 1
fi
echo "✓ Token file OK (mode 600)."

# ── Check 3: Railway health ────────────────────────────────────────────────
BASE="${RAILWAY_SWING_BASE:-https://trend-trading-mcp-production.up.railway.app}"
if ! curl -sf "$BASE/health" >/dev/null; then
    echo "✗ $BASE/health did not return 2xx. Check Railway deploy."
    exit 1
fi
echo "✓ Railway reachable at $BASE."

# ── Check 4: Bearer auth works against a real SWING_API_TOKEN-gated endpoint.
#            We probe POST /api/swing/ideas/<zero-uuid>/thesis because:
#              - It's gated by require_swing_token (not _verify_cron_auth, which
#                reads CRON_SECRET — a different env var).
#              - The zero UUID won't match any real idea; after auth passes we
#                get a 404, which proves the happy bearer path reached the route.
TOKEN="$(head -n1 "$TOKEN_FILE" | tr -d '[:space:]')"
PROBE_PATH="/api/swing/ideas/00000000-0000-0000-0000-000000000000/thesis"
PROBE_BODY='{"layer":"base","text":"probe thesis (ignored)","model":"probe"}'

wrong_status=$(
    curl -s -o /dev/null -w '%{http_code}' \
        -X POST "$BASE$PROBE_PATH" \
        -H "Authorization: Bearer nope-wrong-token" \
        -H "Content-Type: application/json" \
        -d "$PROBE_BODY" || echo "ERR"
)
if [[ "$wrong_status" != "401" ]]; then
    echo "✗ Wrong-token probe returned $wrong_status (expected 401)."
    echo "  If 500 — SWING_API_TOKEN is not set on Railway."
    echo "  If 404 — Plan 3 code is not deployed yet (check Railway build)."
    exit 1
fi
echo "✓ Auth layer rejects bad tokens (401)."

correct_status=$(
    curl -s -o /dev/null -w '%{http_code}' \
        -X POST "$BASE$PROBE_PATH" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PROBE_BODY" || echo "ERR"
)
if [[ "$correct_status" != "404" ]]; then
    echo "✗ Correct-token probe returned $correct_status (expected 404 for the fake idea ID)."
    echo "  If 401 — Railway's SWING_API_TOKEN doesn't match $TOKEN_FILE."
    echo "  If 500 — SWING_API_TOKEN is empty/unset on Railway."
    exit 1
fi
echo "✓ Local token matches Railway's SWING_API_TOKEN (404 on unknown idea as expected)."

# ── Task 11 Step 3: scheduled-tasks MCP registration (manual) ──────────────
cat <<'EOF'

Next step (manual, one-time): register the daily task.

In a Claude Code session on this Mac, call the scheduled-tasks MCP tool:

    mcp__scheduled-tasks__create_scheduled_task
      name:   "swing-analyze-pending"
      cron:   "30 13 * * 1-5"        # 13:30 UTC ≈ 6:30 PT (drifts ±1h with DST)
      prompt: "/swing-analyze-pending"

Verify with:
    mcp__scheduled-tasks__list_scheduled_tasks

Smoke-test manually:
    /swing-analyze-pending

Expected: either "No pending theses this morning." (if Plan 2's pipeline
hasn't produced any), or N theses posted + a Slack summary.
EOF

echo ""
echo "✓ Bootstrap complete."
