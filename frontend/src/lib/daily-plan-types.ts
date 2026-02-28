// ---------------------------------------------------------------------------
// Daily Trade Plan types — multi-timeframe data + computed targets.
// ---------------------------------------------------------------------------

import type { CalculateResponse, TradePlanResponse } from "./types"

// --- Instrument config (data-source swappable) ---

export interface InstrumentConfig {
  ticker: string
  displayName: string
  dataSource: "yfinance" | "schwab"
}

export const INSTRUMENTS: InstrumentConfig[] = [
  { ticker: "SPY", displayName: "SPY", dataSource: "yfinance" },
  { ticker: "^GSPC", displayName: "SPX", dataSource: "yfinance" },
  // Future: { ticker: "/ES", displayName: "ES", dataSource: "schwab" },
]

export const VIX_TICKER = "^VIX"

// --- Target ---

export interface Target {
  price: number
  label: string // e.g. "Golden Gate Bull"
  source: string // e.g. "ATR 1D" or "EMA21 1H"
  confluences: string[] // other levels clustered near this price
  confluenceCount: number
}

// --- Instrument Plan (one per ticker) ---

export interface InstrumentPlan {
  ticker: string
  displayName: string
  daily: TradePlanResponse
  hourly: CalculateResponse
  fifteenMin: CalculateResponse
  weekly: CalculateResponse
  targets: { upside: Target[]; downside: Target[] }
}

// --- VIX Snapshot ---

export interface VixSnapshot {
  price: number
  atrStatus: string
  trend: string // "bullish" | "bearish" | "chopzilla"
  phase: string
  keyLevel: string // "Below 17 (bullish)" etc.
}

// --- Daily Plan Data (full page payload) ---

export interface DailyPlanData {
  instruments: InstrumentPlan[]
  vix: VixSnapshot
  session: string
  fetchedAt: string
}

// --- Supabase row shape ---

export interface DailyPlanRow {
  id: string
  ticker: string
  display_name: string
  session: string
  fetched_at: string
  daily: TradePlanResponse
  hourly: CalculateResponse
  fifteen_min: CalculateResponse
  weekly: CalculateResponse
  vix: VixSnapshot | null
  targets: { upside: Target[]; downside: Target[] } | null
}
