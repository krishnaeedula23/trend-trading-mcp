// ---------------------------------------------------------------------------
// Saty API response types — mirrors the Python return shapes exactly.
// ---------------------------------------------------------------------------

// --- ATR Levels ---

export interface AtrLevel {
  price: number;
  pct: string;
  fib: number;
}

export interface TriggerBox {
  low: number;
  high: number;
  inside: boolean;
}

export type AtrStatus = "green" | "orange" | "red";
export type Trend = "bullish" | "bearish" | "neutral";
export type TradingMode = "day" | "multiday" | "swing" | "position";

export interface AtrLevels {
  atr: number;
  pdc: number;
  current_price: number;
  levels: Record<string, AtrLevel>;
  call_trigger: number;
  put_trigger: number;
  trigger_box: TriggerBox;
  price_position: string;
  daily_range: number;
  period_range: number;
  atr_covered_pct: number;
  atr_status: AtrStatus;
  atr_room_ok: boolean;
  chopzilla: boolean;
  trend: Trend;
  trading_mode: TradingMode;
  trading_mode_label: string;
  use_current_close?: boolean;
}

// --- Pivot Ribbon ---

export type RibbonState = "bullish" | "bearish" | "chopzilla";
export type BiasCandle = "green" | "blue" | "orange" | "red" | "gray";
export type BiasSignal =
  | "bullish"
  | "buy_pullback"
  | "short_pullback"
  | "bearish"
  | "compression";
export type ConvictionArrow = "bullish_crossover" | "bearish_crossover" | null;

export interface PivotRibbon {
  ema8: number;
  ema13: number;
  ema21: number;
  ema48: number;
  ema200: number;
  ribbon_state: RibbonState;
  bias_candle: BiasCandle;
  bias_signal: BiasSignal;
  conviction_arrow: ConvictionArrow;
  last_conviction_type: ConvictionArrow;
  last_conviction_bars_ago: number | null;
  spread: number;
  above_48ema: boolean;
  above_200ema: boolean;
  in_compression: boolean;
  chopzilla: boolean;
}

// --- Phase Oscillator ---

export type Phase = "compression" | "green" | "red";
export type CurrentZone =
  | "extreme_up"
  | "distribution"
  | "neutral_up"
  | "above_zero"
  | "below_zero"
  | "neutral_down"
  | "accumulation"
  | "extreme_down";

export interface ZoneCrosses {
  leaving_accumulation: boolean;
  leaving_extreme_down: boolean;
  leaving_distribution: boolean;
  leaving_extreme_up: boolean;
}

export interface ZoneBounds {
  up: number;
  down: number;
}

export interface Zones {
  extreme: ZoneBounds;
  distribution: ZoneBounds;
  neutral: ZoneBounds;
  zero: number;
}

export type MeanReversionType =
  | "leaving_accumulation"
  | "leaving_extreme_down"
  | "leaving_distribution"
  | "leaving_extreme_up";

export interface PhaseOscillator {
  oscillator: number;
  oscillator_prev: number;
  phase: Phase;
  in_compression: boolean;
  current_zone: CurrentZone;
  zone_crosses: ZoneCrosses;
  last_mr_type: MeanReversionType | null;
  last_mr_bars_ago: number | null;
  zones: Zones;
}

// --- Calculate Response (POST /api/satyland/calculate) ---

export interface CalculateResponse {
  ticker: string;
  timeframe: string;
  trading_mode: TradingMode;
  use_current_close?: boolean;
  bars: number;
  atr_source_bars: number;
  atr_levels: AtrLevels;
  pivot_ribbon: PivotRibbon;
  phase_oscillator: PhaseOscillator;
}

// --- Price Structure ---

export type StructuralBias =
  | "strongly_bullish"
  | "bullish"
  | "neutral"
  | "bearish"
  | "strongly_bearish";

export type GapScenario =
  | "gap_above_pdh"
  | "gap_below_pdl"
  | "gap_up_inside_range"
  | "gap_down_inside_range"
  | "no_gap";

export interface PriceStructure {
  pdc: number;
  pdh: number;
  pdl: number;
  current_price: number;
  pmh: number | null;
  pml: number | null;
  premarket_price?: number | null;
  structural_bias: StructuralBias;
  gap_scenario: GapScenario;
  price_above_pdh: boolean;
  price_above_pmh: boolean;
  price_below_pdl: boolean;
  price_below_pml: boolean;
}

// --- Green Flag ---

export type Direction = "bullish" | "bearish";
export type Grade = "A+" | "A" | "B" | "skip";

export interface GreenFlag {
  direction: Direction;
  score: number;
  max_score: number;
  grade: Grade;
  recommendation: string;
  flags: Record<string, boolean | null>;
  verbal_audit: string;
}

// --- Key Pivots ---

export interface KeyPivots {
  pwh: number | null;
  pwl: number | null;
  pwc: number | null;
  pmoh: number | null;
  pmol: number | null;
  pmoc: number | null;
  pqc: number | null;
  pyc: number | null;
}

// --- Open Gaps ---

export interface OpenGap {
  date: string;
  type: "gap_up" | "gap_down";
  gap_high: number;
  gap_low: number;
  size: number;
}

// --- Trade Plan Response (POST /api/satyland/trade-plan) ---

export interface MtfRibbonEntry {
  ribbon_state: RibbonState;
  bias_candle: BiasCandle;
  conviction_arrow: ConvictionArrow;
  last_conviction_type: ConvictionArrow;
  last_conviction_bars_ago: number | null;
  in_compression: boolean;
  above_200ema: boolean;
}

export interface MtfPhaseEntry {
  oscillator: number;
  phase: Phase;
  in_compression: boolean;
  current_zone: CurrentZone;
  last_mr_type: MeanReversionType | null;
  last_mr_bars_ago: number | null;
}

export interface TradePlanResponse extends CalculateResponse {
  direction: string;
  price_structure: PriceStructure;
  key_pivots?: KeyPivots;
  open_gaps?: OpenGap[];
  green_flag: GreenFlag;
  mtf_ribbons?: Record<string, MtfRibbonEntry>;
  mtf_phases?: Record<string, MtfPhaseEntry>;
}

// --- Idea (Supabase row) ---

export type IdeaStatus =
  | "watching"
  | "active"
  | "triggered"
  | "closed"
  | "expired";

export interface Idea {
  id: string;
  ticker: string;
  direction: Direction;
  timeframe: string;
  status: IdeaStatus;
  grade: string | null;
  ribbon_state: string | null;
  bias_candle: string | null;
  phase: string | null;
  atr_status: string | null;
  score: number | null;
  current_price: number | null;
  call_trigger: number | null;
  put_trigger: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  filled_price: number | null;
  exit_price: number | null;
  pnl: number | null;
  notes: string | null;
  tags: string[];
  source: string;
  indicator_snapshot: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// --- Batch Calculate ---

export interface BatchResultItem {
  ticker: string;
  success: boolean;
  data?: TradePlanResponse;
  error?: string;
}

export interface BatchCalculateResponse {
  results: BatchResultItem[];
}

// --- ATM Straddle (POST /api/options/atm-straddle) ---

export interface AtmStraddle {
  ticker: string
  spot: number
  atm_strike: number
  call_price: number
  put_price: number
  straddle_price: number
  expected_move: number
  expected_move_pct: number
  expiration: string
  days_to_expiry: number
  call_iv: number        // ATM call implied volatility (decimal, e.g. 0.1825)
  put_iv: number         // ATM put implied volatility (decimal)
  atm_iv: number         // Average of call/put IV (decimal)
}

// --- IV Metrics (POST /api/options/iv-metrics) ---

export interface IvMetrics {
  ticker: string
  current_iv: number     // Current VIX value
  iv_rank: number        // 0-100
  iv_percentile: number  // 0-100
  high_52w: number
  low_52w: number
}

// --- Watchlist (Supabase row) ---

export interface Watchlist {
  id: string;
  name: string;
  tickers: string[];
  is_default: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Momentum Scanner
// ---------------------------------------------------------------------------

export interface MomentumCriterion {
  label: string
  pct_change: number
  threshold: number
  lookback_days: number
}

export interface MomentumHit {
  ticker: string
  last_close: number
  criteria_met: MomentumCriterion[]
  max_pct_change: number
  weekly_pct: number | null
  monthly_pct: number | null
  three_month_pct: number | null
  six_month_pct: number | null
}

export interface MomentumScanRequest {
  universes: string[]
  min_price: number
  custom_tickers?: string[]
}

export interface MomentumScanResponse {
  hits: MomentumHit[]
  total_scanned: number
  total_hits: number
  total_errors: number
  skipped_low_price: number
  scan_duration_seconds: number
  universes_used: string[]
}

// ---------------------------------------------------------------------------
// Golden Gate Scanner
// ---------------------------------------------------------------------------

export type GoldenGateSignalType =
  | "golden_gate"
  | "golden_gate_up"
  | "golden_gate_down"
  | "call_trigger"
  | "put_trigger"

export interface GoldenGateHit {
  ticker: string
  last_close: number
  signal: GoldenGateSignalType
  direction: "bullish" | "bearish"
  pdc: number
  atr: number
  gate_level: number
  midrange_level: number
  distance_pct: number
  atr_status: AtrStatus
  atr_covered_pct: number
  trend: Trend
  trading_mode: TradingMode
  premarket_high: number | null
  premarket_low: number | null
}

export interface GoldenGateScanRequest {
  universes: string[]
  trading_mode: TradingMode
  signal_type: GoldenGateSignalType
  min_price: number
  custom_tickers?: string[]
  include_premarket: boolean
}

export interface GoldenGateScanResponse {
  hits: GoldenGateHit[]
  total_scanned: number
  total_hits: number
  total_errors: number
  skipped_low_price: number
  scan_duration_seconds: number
  signal_type: GoldenGateSignalType
  trading_mode: TradingMode
}

// ---------------------------------------------------------------------------
// VOMY / iVOMY Scanner
// ---------------------------------------------------------------------------

export type VomySignalType = "vomy" | "ivomy" | "both"

export type VomyTimeframe = "1h" | "4h" | "1d" | "1w"

export interface VomyHit {
  ticker: string
  last_close: number
  signal: "vomy" | "ivomy"
  ema13: number
  ema21: number
  ema34: number
  ema48: number
  distance_from_ema48_pct: number
  atr: number
  pdc: number
  nearest_level_name: string
  nearest_level_pct: number
  atr_status: AtrStatus
  atr_covered_pct: number
  trend: Trend
  trading_mode: TradingMode
  timeframe: VomyTimeframe
  conviction_type: "bullish_crossover" | "bearish_crossover" | null
  conviction_bars_ago: number | null
  conviction_confirmed: boolean
}

export interface VomyScanRequest {
  universes: string[]
  timeframe: VomyTimeframe
  signal_type: VomySignalType
  min_price: number
  custom_tickers?: string[]
  include_premarket: boolean
}

export interface VomyScanResponse {
  hits: VomyHit[]
  total_scanned: number
  total_hits: number
  total_errors: number
  skipped_low_price: number
  scan_duration_seconds: number
  signal_type: VomySignalType
  timeframe: VomyTimeframe
}

// ── Market Monitor ──────────────────────────────────────────────────────────

export interface BreadthSnapshotSummary {
  date: string
  computed_at: string
  scans: Record<string, number> // scan_key -> count
}

export interface DrillDownTicker {
  symbol: string
  pct_change: number
  close: number
  sector: string
}

export interface DrillDownResponse {
  date: string
  scan_key: string
  count: number
  tickers: DrillDownTicker[]
}

export interface SectorData {
  gainers_1d: number
  losers_1d: number
  net_1d: number
  gainers_1w: number
  losers_1w: number
  net_1w: number
  gainers_1m: number
  losers_1m: number
  net_1m: number
  gainers_3m: number
  losers_3m: number
  net_3m: number
  rank_1d: number
  rank_1w: number
  rank_1m: number
  rank_3m: number
  stock_count: number
}

export interface ThemeTrackerResponse {
  date: string
  sectors: Record<string, SectorData>
  universe_size?: number
}

export interface SectorStocksResponse {
  date: string
  sector: string
  stocks: DrillDownTicker[]
}

// ---------------------------------------------------------------------------
// Swing Trading — Universe (Plan 1)
// ---------------------------------------------------------------------------

export type SwingUniverseSource = "deepvue-csv" | "manual" | "backend-generated"

export interface SwingUniverseTicker {
  ticker: string
  source: SwingUniverseSource
  batch_id: string
  added_at: string
  extras: Record<string, unknown> | null
}

export interface SwingUniverseListResponse {
  tickers: SwingUniverseTicker[]
  source_summary: Record<SwingUniverseSource, number>
  active_count: number
  latest_batch_at: string | null
}

export interface SwingUniverseUploadResponse {
  batch_id: string
  mode: "replace" | "add"
  tickers_added: number
  tickers_removed: number
  total_active: number
}

export interface SwingUniverseHistoryEntry {
  batch_id: string
  source: string
  uploaded_at: string
  ticker_count: number
}

// ---------------------------------------------------------------------------
// Swing Trading — Ideas (Plan 2)
// ---------------------------------------------------------------------------

export interface SwingIdea {
  id: string
  ticker: string
  cycle_stage: string
  setup_kell: string
  confluence_score: number
  entry_zone_low: number | null
  entry_zone_high: number | null
  stop_price: number
  first_target: number | null
  second_target: number | null
  status: "active" | "watching" | "exited" | "invalidated"
  detected_at: string
  base_thesis: string | null
  thesis_status: "pending" | "ready"
  market_health: Record<string, unknown> | null
  risk_flags: Record<string, unknown>
  detection_evidence: Record<string, unknown> | null
}

export interface SwingIdeaListResponse {
  ideas: SwingIdea[]
  total: number
}

// ---------------------------------------------------------------------------
// Swing Trading — Idea Detail (Plan 3)
// ---------------------------------------------------------------------------

export type SwingThesisLayer = "base" | "deep"

export interface SwingThesis {
  text: string
  layer: SwingThesisLayer
  model: string
  updated_at: string
  sources?: string[]
}

export interface SwingEvent {
  id: number
  idea_id: string
  event_type: string
  occurred_at: string
  payload?: Record<string, unknown> | null
  summary?: string | null
}

// Detail type extends Plan 2's SwingIdea with fields the detail page needs.
// Plan 2's /ideas/{id} response returns SwingIdea's fields; extras are optional.
export interface SwingIdeaDetail extends SwingIdea {
  // All these may not be set by Plan 2's endpoint; the UI handles nulls.
  direction?: "long" | "short"
  setup_saty?: string | null
  base_thesis_at?: string | null
  deep_thesis?: string | null
  deep_thesis_at?: string | null
  deep_thesis_sources?: string[] | null
  next_earnings_date?: string | null
  // Events come in via a separate endpoint (Plan 4). For Plan 3, always [].
  events?: SwingEvent[]
}

// ───────── Plan 4 additions ─────────

export type SwingSnapshot = {
  id: number
  idea_id: string
  snapshot_date: string
  snapshot_type: "daily" | "weekly"
  daily_close: number | null
  ema_10: number | null
  ema_20: number | null
  sma_50: number | null
  sma_200: number | null
  kell_stage: string | null
  claude_analysis: string | null
  chart_daily_url: string | null
  chart_weekly_url: string | null
  chart_60m_url: string | null
}

export type SwingChart = {
  id: string
  idea_id: string | null
  event_id: number | null
  model_book_id: string | null
  image_url: string
  thumbnail_url: string | null
  timeframe: string   // backend may evolve; gallery filters string-compared anyway
  source: "deepvue-auto" | "tradingview-upload" | "user-markup" | "claude-annotated"
  annotations: Record<string, unknown> | null
  caption: string | null
  captured_at: string
}

export type SwingModelBookEntry = {
  id: string
  title: string
  ticker: string
  setup_kell: string
  outcome: "winner" | "loser" | "example" | "missed"
  entry_date: string | null
  exit_date: string | null
  r_multiple: number | null
  source_idea_id: string | null
  narrative: string | null
  key_takeaways: string[] | null
  tags: string[] | null
  created_at: string
  updated_at: string
}

export type SwingWeekGroup = {
  week_of: string
  entries: Array<{
    idea_id: string
    ticker: string
    cycle_stage: string | null
    status: string
    claude_analysis: string | null
  }>
}
