-- Migration: 018_add_swing_idempotency_keys
-- Depends on: 017_add_swing_detection_evidence
-- Applied: 2026-04-18 via Supabase MCP apply_migration (project: pmjufbiagokrrcxnhmah)
-- Spec: docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md §8
-- Plan: docs/superpowers/plans/2026-04-18-plan-3-claude-analysis-layer.md (Task 2)
--
-- Dedupe repeated POSTs from Mac-Claude retries within a 24h window.
-- NOT tracked in Alembic — matches the Plan 1/2 convention.
--
-- NOTE: The plan doc originally numbered this 017. Renumbered to 018 because
-- Plan 2's detection_evidence migration took 017.

CREATE TABLE IF NOT EXISTS swing_idempotency_keys (
  key UUID PRIMARY KEY,
  endpoint TEXT NOT NULL,
  response_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS swing_idempotency_keys_created
  ON swing_idempotency_keys (created_at);

-- Manual cleanup (or schedule via pg_cron once available):
-- DELETE FROM swing_idempotency_keys WHERE created_at < NOW() - INTERVAL '24 hours';
