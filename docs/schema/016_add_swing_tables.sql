-- Migration: 016_add_swing_tables
-- Applied: 2026-04-18 via Supabase MCP apply_migration (project: pmjufbiagokrrcxnhmah)
-- Spec: docs/superpowers/specs/2026-04-18-kell-saty-swing-system-design.md
-- Plan: docs/superpowers/plans/2026-04-18-plan-1-foundation-universe.md
--
-- NOTE: This SQL was applied directly to Supabase, bypassing Alembic.
-- The repo's Alembic chain has pre-existing missing revisions
-- (002_add_authentication_tables, 005_add_user_table, 0004, 416a0259129d)
-- which predate the swing system. Restoring Alembic integrity is a separate
-- cleanup task, independent of swing. Keep this SQL file as the authoritative
-- record of the swing schema and apply to other environments via Supabase
-- SQL Editor or psql.

-- ===== swing_universe =====
CREATE TABLE swing_universe (
  id SERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  source TEXT NOT NULL,
  batch_id UUID NOT NULL,
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  removed_at TIMESTAMPTZ,
  extras JSONB
);
CREATE UNIQUE INDEX swing_universe_active_ticker_uniq
  ON swing_universe (ticker) WHERE removed_at IS NULL;
CREATE INDEX ix_swing_universe_batch_id ON swing_universe (batch_id);

-- ===== swing_ideas =====
CREATE TABLE swing_ideas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  direction TEXT NOT NULL DEFAULT 'long',
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cycle_stage TEXT NOT NULL,
  setup_kell TEXT NOT NULL,
  setup_saty TEXT,
  confluence_score INTEGER NOT NULL,
  entry_zone_low NUMERIC,
  entry_zone_high NUMERIC,
  stop_price NUMERIC NOT NULL,
  first_target NUMERIC,
  second_target NUMERIC,
  suggested_position_pct NUMERIC,
  suggested_risk_bips INTEGER,
  fundamentals JSONB,
  next_earnings_date DATE,
  beta NUMERIC,
  avg_daily_dollar_volume NUMERIC,
  base_thesis TEXT,
  base_thesis_at TIMESTAMPTZ,
  thesis_status TEXT NOT NULL DEFAULT 'pending',
  deep_thesis TEXT,
  deep_thesis_at TIMESTAMPTZ,
  deep_thesis_sources JSONB,
  market_health JSONB,
  risk_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'watching',
  watching_since TIMESTAMPTZ,
  invalidated_at TIMESTAMPTZ,
  invalidated_reason TEXT,
  user_notes TEXT,
  tags TEXT[]
);
CREATE UNIQUE INDEX swing_ideas_active_ticker_stage_uniq
  ON swing_ideas (ticker, cycle_stage)
  WHERE status NOT IN ('exited', 'invalidated');
CREATE INDEX ix_swing_ideas_status_detected ON swing_ideas (status, detected_at DESC);
CREATE INDEX ix_swing_ideas_ticker ON swing_ideas (ticker);
CREATE INDEX ix_swing_ideas_thesis_pending
  ON swing_ideas (thesis_status) WHERE thesis_status = 'pending';

-- ===== swing_idea_stage_transitions =====
CREATE TABLE swing_idea_stage_transitions (
  id SERIAL PRIMARY KEY,
  idea_id UUID NOT NULL REFERENCES swing_ideas(id) ON DELETE CASCADE,
  from_stage TEXT,
  to_stage TEXT NOT NULL,
  transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  daily_close NUMERIC,
  snapshot JSONB
);
CREATE INDEX ix_swing_stage_trans_idea_time
  ON swing_idea_stage_transitions (idea_id, transitioned_at);

-- ===== swing_idea_snapshots =====
CREATE TABLE swing_idea_snapshots (
  id SERIAL PRIMARY KEY,
  idea_id UUID NOT NULL REFERENCES swing_ideas(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  snapshot_type TEXT NOT NULL,
  daily_close NUMERIC,
  daily_high NUMERIC,
  daily_low NUMERIC,
  daily_volume BIGINT,
  ema_10 NUMERIC,
  ema_20 NUMERIC,
  sma_50 NUMERIC,
  sma_200 NUMERIC,
  weekly_ema_10 NUMERIC,
  rs_vs_qqq_20d NUMERIC,
  phase_osc_value NUMERIC,
  kell_stage TEXT,
  saty_setups_active TEXT[],
  claude_analysis TEXT,
  claude_model TEXT,
  analysis_sources JSONB,
  deepvue_panel JSONB,
  chart_daily_url TEXT,
  chart_weekly_url TEXT,
  chart_60m_url TEXT,
  CONSTRAINT uq_swing_snap_idea_date_type UNIQUE (idea_id, snapshot_date, snapshot_type)
);
CREATE INDEX ix_swing_snap_idea_date
  ON swing_idea_snapshots (idea_id, snapshot_date DESC);
CREATE INDEX ix_swing_snap_date_type
  ON swing_idea_snapshots (snapshot_date DESC, snapshot_type);

-- ===== swing_events =====
CREATE TABLE swing_events (
  id SERIAL PRIMARY KEY,
  idea_id UUID NOT NULL REFERENCES swing_ideas(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB,
  summary TEXT
);
CREATE INDEX ix_swing_events_idea_time
  ON swing_events (idea_id, occurred_at DESC);

-- ===== swing_model_book =====
CREATE TABLE swing_model_book (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  ticker TEXT NOT NULL,
  setup_kell TEXT NOT NULL,
  outcome TEXT NOT NULL,
  entry_date DATE,
  exit_date DATE,
  r_multiple NUMERIC,
  source_idea_id UUID REFERENCES swing_ideas(id) ON DELETE SET NULL,
  ticker_fundamentals JSONB,
  narrative TEXT,
  key_takeaways TEXT[],
  tags TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===== swing_charts =====
CREATE TABLE swing_charts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID REFERENCES swing_ideas(id) ON DELETE CASCADE,
  event_id INTEGER REFERENCES swing_events(id) ON DELETE CASCADE,
  model_book_id UUID REFERENCES swing_model_book(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  thumbnail_url TEXT,
  timeframe TEXT NOT NULL,
  source TEXT NOT NULL,
  annotations JSONB,
  caption TEXT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT swing_charts_one_owner
    CHECK (num_nonnulls(idea_id, event_id, model_book_id) = 1)
);
CREATE INDEX ix_swing_charts_idea ON swing_charts (idea_id);
CREATE INDEX ix_swing_charts_model_book ON swing_charts (model_book_id);
