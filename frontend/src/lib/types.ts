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

export interface PhaseOscillator {
  oscillator: number;
  oscillator_prev: number;
  phase: Phase;
  in_compression: boolean;
  current_zone: CurrentZone;
  zone_crosses: ZoneCrosses;
  zones: Zones;
}

// --- Calculate Response (POST /api/satyland/calculate) ---

export interface CalculateResponse {
  ticker: string;
  timeframe: string;
  trading_mode: TradingMode;
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

// --- Trade Plan Response (POST /api/satyland/trade-plan) ---

export interface TradePlanResponse extends CalculateResponse {
  direction: string;
  price_structure: PriceStructure;
  green_flag: GreenFlag;
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

// --- Watchlist (Supabase row) ---

export interface Watchlist {
  id: string;
  name: string;
  tickers: string[];
  is_default: boolean;
  created_at: string;
}
