-- =============================================================================
-- Trading Companion System: Supabase Table Definitions
-- =============================================================================
-- Task 3.2: Creates 6 tables for daily plans, trades, journal entries, alerts,
-- notes, and weekly reviews. Run once against the Supabase project.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- updated_at trigger function
-- Automatically sets updated_at = NOW() before any UPDATE on tables that
-- include the column.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- Table 1: daily_plans
-- Stores the morning game-plan for a given date + ticker (SPY by default).
-- Captures indicator state (ATR levels, ribbon, phase, VIX), opening range,
-- key price levels, and free-form plan notes.
-- =============================================================================
CREATE TABLE IF NOT EXISTS daily_plans (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE        NOT NULL,
    ticker          TEXT        NOT NULL DEFAULT 'SPY',
    structural_bias TEXT,                           -- 'bullish' | 'bearish' | 'neutral'
    atr_levels      JSONB,                          -- {atr, r1, r2, s1, s2, ...}
    ribbon_state    TEXT,                           -- 'above' | 'below' | 'inside'
    phase_state     TEXT,                           -- 'green' | 'red' | 'compression'
    vix_reading     REAL,
    key_levels      JSONB,                          -- [{label, price}, ...]
    or_high         REAL,                           -- opening range high
    or_low          REAL,                           -- opening range low
    mtf_scores      JSONB,                          -- {daily, weekly, monthly}
    plan_notes      TEXT,
    setups_to_watch JSONB,                          -- [{setup_type, notes}, ...]
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_daily_plans_date   ON daily_plans (date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_plans_ticker ON daily_plans (ticker);

CREATE OR REPLACE TRIGGER trg_daily_plans_updated_at
    BEFORE UPDATE ON daily_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Table 2: trades
-- Records every trade taken: entry/exit/stop/target, sizing, risk, R-multiple,
-- P&L, grade, setup metadata, and FK links to daily_plans and alerts.
-- alert_id FK is added after the alerts table is created (see below).
-- =============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE        NOT NULL,
    ticker          TEXT        NOT NULL,
    direction       TEXT        NOT NULL CHECK (direction IN ('long', 'short')),
    setup_type      TEXT        NOT NULL CHECK (setup_type IN (
                        'orb', 'vomy', 'ivomy', 'flag_into_ribbon',
                        'golden_gate', 'squeeze', 'divergence_from_extreme',
                        'eod_divergence', 'wicky_wicky'
                    )),
    instrument      TEXT,                           -- 'stock' | 'call' | 'put' | 'spy_option'
    trigger         TEXT,                           -- what triggered entry
    entry_price     REAL,
    exit_price      REAL,
    stop_price      REAL,
    target_price    REAL,
    sizing          INTEGER,                        -- shares / contracts
    risk_amount     REAL,                           -- dollars risked
    r_multiple      REAL,                           -- realized R
    pnl             REAL,                           -- realized P&L in dollars
    status          TEXT        NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'closed', 'stopped_out', 'incomplete')),
    grade           TEXT        CHECK (grade IN ('A+', 'A', 'B', 'skip')),
    green_flags     JSONB,                          -- [{flag, present}, ...]
    mtf_scores      JSONB,                          -- {daily, weekly, monthly}
    probability     REAL,                           -- estimated win probability 0–1
    reasoning       TEXT,                           -- AI or manual reasoning for the trade
    daily_plan_id   UUID        REFERENCES daily_plans(id),
    alert_id        UUID,                           -- FK added below after alerts table
    notes           TEXT,
    entered_at      TIMESTAMPTZ,
    exited_at       TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_date       ON trades (date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker     ON trades (ticker);
CREATE INDEX IF NOT EXISTS idx_trades_setup_type ON trades (setup_type);
CREATE INDEX IF NOT EXISTS idx_trades_status     ON trades (status);

CREATE OR REPLACE TRIGGER trg_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Table 3: journal_entries
-- One row per trading day. Captures emotional state, what worked/didn't,
-- lessons learned, rule adherence, and session-level performance stats.
-- =============================================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE        NOT NULL UNIQUE,
    emotional_state TEXT,                           -- 'calm' | 'anxious' | 'overconfident' | ...
    what_worked     TEXT,
    what_didnt      TEXT,
    lessons         TEXT,
    followed_rules  BOOLEAN,
    rules_broken    JSONB,                          -- [rule_name, ...]
    session_grade   TEXT        CHECK (session_grade IN ('A', 'B', 'C', 'F')),
    total_trades    INTEGER,
    total_pnl       REAL,
    total_r         REAL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries (date DESC);


-- =============================================================================
-- Table 4: trading_alerts (named to avoid conflict with existing "alerts" table)
-- Stores inbound alerts (webhook from TradingView or scheduled scan).
-- Linked back to a trade once the alert is acted on.
-- =============================================================================
CREATE TABLE IF NOT EXISTS trading_alerts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE        NOT NULL,
    ticker          TEXT        NOT NULL,
    setup_type      TEXT        NOT NULL,
    direction       TEXT        NOT NULL,
    timeframe       TEXT,                           -- '5m' | '15m' | '1h' | '1d'
    alert_type      TEXT        CHECK (alert_type IN ('webhook', 'scheduled')),
    grade           TEXT,                           -- pre-graded quality from signal
    details         JSONB,                          -- raw payload from the alert source
    acknowledged    BOOLEAN     DEFAULT FALSE,
    traded          BOOLEAN     DEFAULT FALSE,
    trade_id        UUID        REFERENCES trades(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trading_alerts_date       ON trading_alerts (date DESC);
CREATE INDEX IF NOT EXISTS idx_trading_alerts_ticker     ON trading_alerts (ticker);
CREATE INDEX IF NOT EXISTS idx_trading_alerts_setup_type ON trading_alerts (setup_type);

CREATE OR REPLACE TRIGGER trg_trading_alerts_updated_at
    BEFORE UPDATE ON trading_alerts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- Deferred FK: trades.alert_id → trading_alerts.id
-- Added here because trading_alerts did not exist when trades was created.
-- ---------------------------------------------------------------------------
ALTER TABLE trades
    ADD CONSTRAINT fk_trades_alert
    FOREIGN KEY (alert_id) REFERENCES trading_alerts(id);


-- =============================================================================
-- Table 5: notes
-- Lightweight free-form notes linked to a date, optionally to a ticker
-- or a specific trade. Categorized for easy filtering.
-- =============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE        NOT NULL,
    ticker          TEXT,
    content         TEXT        NOT NULL,
    category        TEXT        CHECK (category IN ('observation', 'emotional', 'setup', 'lesson')),
    linked_trade_id UUID        REFERENCES trades(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_date   ON notes (date DESC);
CREATE INDEX IF NOT EXISTS idx_notes_ticker ON notes (ticker);


-- =============================================================================
-- Table 6: weekly_reviews
-- Aggregated performance metrics and qualitative review for each trading week.
-- One row per week (unique on week_start). Includes per-setup and time-of-day
-- breakdowns as well as emotional correlation data.
-- =============================================================================
CREATE TABLE IF NOT EXISTS weekly_reviews (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start              DATE    NOT NULL,
    week_end                DATE    NOT NULL,
    total_trades            INTEGER,
    wins                    INTEGER,
    losses                  INTEGER,
    win_rate                REAL,                   -- 0.0 – 1.0
    total_pnl               REAL,
    total_r                 REAL,
    avg_r                   REAL,
    best_setup              TEXT,
    worst_setup             TEXT,
    setup_breakdown         JSONB,                  -- {setup_type: {trades, wins, avg_r}}
    time_of_day_breakdown   JSONB,                  -- {open, midday, close: {trades, avg_r}}
    rules_followed_pct      REAL,                   -- 0.0 – 100.0
    emotional_correlation   JSONB,                  -- {state: avg_r, ...}
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_reviews_week_start ON weekly_reviews (week_start DESC);
