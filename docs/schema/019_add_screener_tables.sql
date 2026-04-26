-- Migration: 019_add_screener_tables
-- Depends on: 018_add_swing_idempotency_keys
-- Spec: docs/superpowers/specs/2026-04-25-unified-screener-design.md
-- Plan: docs/superpowers/plans/2026-04-25-screener-plan-1-foundation.md (Task 1)
--
-- Tables for the unified morning screener (Plan 1):
--   screener_runs       — one row per scan run, stores results blob
--   coiled_watchlist    — persistent days-in-compression tracking
--   universe_overrides  — manual ticker add/remove on top of base universe

create table if not exists screener_runs (
  id uuid primary key default gen_random_uuid(),
  ran_at timestamptz not null default now(),
  mode text not null check (mode in ('swing', 'position')),
  universe_size int not null,
  scan_count int not null,
  hit_count int not null,
  duration_seconds numeric not null,
  results jsonb not null,
  error text
);

create index if not exists ix_screener_runs_ran_at on screener_runs (ran_at desc);
create index if not exists ix_screener_runs_mode_ran_at on screener_runs (mode, ran_at desc);

create table if not exists coiled_watchlist (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  mode text not null check (mode in ('swing', 'position')),
  first_detected_at date not null,
  last_seen_at date not null,
  days_in_compression int not null,
  status text not null check (status in ('active', 'fired', 'broken')),
  fired_at date,
  graduated_to_trigger jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ticker, mode, first_detected_at)
);

create index if not exists ix_coiled_watchlist_active
  on coiled_watchlist (mode, status, days_in_compression desc)
  where status = 'active';

create table if not exists universe_overrides (
  id uuid primary key default gen_random_uuid(),
  mode text not null check (mode in ('swing', 'position')),
  ticker text not null,
  action text not null check (action in ('add', 'remove')),
  source text not null default 'claude_skill',
  created_at timestamptz not null default now(),
  unique (mode, ticker, action)
);

create index if not exists ix_universe_overrides_mode on universe_overrides (mode);
