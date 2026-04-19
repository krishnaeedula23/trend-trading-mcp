-- Migration: 017_add_swing_detection_evidence
-- Depends on: 016_add_swing_tables
-- Applied: 2026-04-18 via Supabase MCP apply_migration (project: pmjufbiagokrrcxnhmah)
-- Spec: docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md Section 8
--
-- Adds the per-detector evidence blob to swing_ideas so Plan 3 thesis generation
-- can read the exact indicator readings that triggered the setup.
--
-- Pipeline writes keys like: ema10, ema20, ema10_slope, rs_vs_qqq_10d,
-- volume_vs_20d_avg, dist_to_sma200_pct, phase_osc, support_type, gap_pct,
-- gap_bars_ago, consolidation_bars, etc. Shape varies per detector.

ALTER TABLE swing_ideas
  ADD COLUMN IF NOT EXISTS detection_evidence JSONB;
