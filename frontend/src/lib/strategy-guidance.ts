// ---------------------------------------------------------------------------
// Strategy Guidance — interprets ATR levels, premarket data, expected move,
// and VIX to generate actionable game plan for each instrument.
// Pure TypeScript, no side effects. Follows the setups.ts pattern.
// ---------------------------------------------------------------------------

import type { InstrumentPlan, VixSnapshot } from "./daily-plan-types"
import type { InstrumentOptionsData } from "@/hooks/use-options-data"
import type { AtrLevel } from "./types"

// --- Types ---

export interface StrategyScenario {
  label: string           // "Call Trigger Breached" / "Inside Trigger Box"
  description: string     // Human-readable interpretation
  setupsToWatch: string[] // ["Golden Gate", "Trend Continuation"]
  actionItems: string[]   // ["Wait for blue candle pullback to 13/21 EMA"]
}

export interface EmAtrComparison {
  emRange: number              // 2 × expected_move
  atrRange: number             // call_trigger - put_trigger
  emUpper: number              // spot + expected_move
  emLower: number              // spot - expected_move
  deviation: "wider" | "tighter" | "aligned"
  deviationNote: string        // "Options imply larger move..."
  confluences: string[]        // ["EM upper ($689.40) ≈ Golden Gate Bull ($689.03)"]
}

export interface VixPremarketContext {
  direction: "rising" | "falling" | "stable"
  delta: number
  deltaPct: number
  note: string
}

export interface StrategyGuidance {
  headline: string
  gapReading: string
  scenarios: StrategyScenario[]
  emAtr: EmAtrComparison | null
  vixPremkt: VixPremarketContext | null
  atrNote: string
  entryReminder: string
}

// --- Helpers ---

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

function pctDiff(a: number, b: number): number {
  return Math.abs(a - b) / Math.max(Math.abs(a), Math.abs(b))
}

const CONFLUENCE_PCT = 0.0015 // 0.15% — same as targets.ts

// --- Gap Interpretation ---

function interpretGap(gapScenario: string): string {
  switch (gapScenario) {
    case "gap_above_pdh":
      return "Gapped above PDH — extreme bullish overnight. Watch for continuation or fade back to PDH."
    case "gap_below_pdl":
      return "Gapped below PDL — extreme bearish overnight. Watch for continuation or bounce at PDL."
    case "gap_up_inside_range":
      return "Gap up inside prior range — let triggers define direction."
    case "gap_down_inside_range":
      return "Gap down inside prior range — let triggers define direction."
    case "no_gap":
      return "Opens near PDC — neutral, wait for trigger break."
    default:
      return "Gap data unavailable."
  }
}

// --- VIX Premarket Context ---

function buildVixPremarketContext(vix: VixSnapshot): VixPremarketContext | null {
  if (vix.premktPrice == null || vix.price <= 0) return null

  const delta = vix.premktPrice - vix.price
  const deltaPct = (delta / vix.price) * 100

  let direction: "rising" | "falling" | "stable"
  let note: string

  if (deltaPct > 5) {
    direction = "rising"
    note = `VIX rising premarket (+${fmt(deltaPct, 1)}%) — volatility expanding, expect wider range, defensive bias`
  } else if (deltaPct < -5) {
    direction = "falling"
    note = `VIX falling premarket (${fmt(deltaPct, 1)}%) — volatility contracting, bullish lean, tighter targets`
  } else {
    direction = "stable"
    note = `VIX stable premarket (${deltaPct > 0 ? "+" : ""}${fmt(deltaPct, 1)}%) — normal volatility environment`
  }

  return { direction, delta, deltaPct, note }
}

// --- Expected Move vs ATR Comparison ---

function buildEmAtrComparison(
  plan: InstrumentPlan,
  optionsData: InstrumentOptionsData | null,
): EmAtrComparison | null {
  const straddle = optionsData?.straddle
  if (!straddle?.expected_move || !straddle?.spot) return null

  const atr = plan.daily.atr_levels
  const emUpper = straddle.spot + straddle.expected_move
  const emLower = straddle.spot - straddle.expected_move
  const emRange = 2 * straddle.expected_move
  const atrRange = atr.call_trigger - atr.put_trigger

  // Deviation
  let deviation: "wider" | "tighter" | "aligned"
  let deviationNote: string
  const ratio = emRange / atrRange

  if (ratio > 1.3) {
    deviation = "wider"
    deviationNote = `Options imply larger move (EM ±$${fmt(straddle.expected_move)} vs ATR range $${fmt(atrRange)}) — expect volatility expansion, wider stops`
  } else if (ratio < 0.7) {
    deviation = "tighter"
    deviationNote = `ATR range wider than expected move (ATR $${fmt(atrRange)} vs EM ±$${fmt(straddle.expected_move)}) — ATR extreme levels less likely, tighter targets`
  } else {
    deviation = "aligned"
    deviationNote = `ATR and expected move aligned — normal conditions`
  }

  // Confluence — check if EM bounds align with any ATR Fib levels
  const confluences: string[] = []
  const levels = atr.levels || {}
  for (const [key, level] of Object.entries(levels)) {
    const lvl = level as AtrLevel
    if (lvl?.price) {
      const niceName = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
      if (pctDiff(emUpper, lvl.price) <= CONFLUENCE_PCT) {
        confluences.push(`EM upper ($${fmt(emUpper)}) ≈ ${niceName} ($${fmt(lvl.price)})`)
      }
      if (pctDiff(emLower, lvl.price) <= CONFLUENCE_PCT) {
        confluences.push(`EM lower ($${fmt(emLower)}) ≈ ${niceName} ($${fmt(lvl.price)})`)
      }
    }
  }

  // Also check call/put triggers
  if (pctDiff(emUpper, atr.call_trigger) <= CONFLUENCE_PCT) {
    confluences.push(`EM upper ($${fmt(emUpper)}) ≈ Call Trigger ($${fmt(atr.call_trigger)})`)
  }
  if (pctDiff(emLower, atr.put_trigger) <= CONFLUENCE_PCT) {
    confluences.push(`EM lower ($${fmt(emLower)}) ≈ Put Trigger ($${fmt(atr.put_trigger)})`)
  }

  return {
    emRange,
    atrRange,
    emUpper,
    emLower,
    deviation,
    deviationNote,
    confluences,
  }
}

// --- ATR Room Note ---

function buildAtrNote(atrCoveredPct: number): string {
  if (atrCoveredPct >= 90) {
    return `ATR room: ${fmt(atrCoveredPct, 0)}% — exhausted, avoid new entries`
  }
  if (atrCoveredPct >= 60) {
    return `ATR room: ${fmt(atrCoveredPct, 0)}% — limited, smaller size`
  }
  return `ATR room: ${fmt(atrCoveredPct, 0)}% — plenty of room, green light`
}

// --- Scenario Generation ---

function buildScenarios(plan: InstrumentPlan): StrategyScenario[] {
  const atr = plan.daily.atr_levels
  const ps = plan.daily.price_structure
  const levels = atr.levels || {}

  // Determine current reference price — premarket price if available, else current_price
  const refPrice = ps.premarket_price ?? atr.current_price

  const goldenGateBull = (levels.golden_gate_bull as AtrLevel)?.price
  const goldenGateBear = (levels.golden_gate_bear as AtrLevel)?.price
  const midRangeBull = (levels.mid_range_bull as AtrLevel)?.price
  const midRangeBear = (levels.mid_range_bear as AtrLevel)?.price
  const mid50Bull = (levels.mid_50_bull as AtrLevel)?.price
  const mid50Bear = (levels.mid_50_bear as AtrLevel)?.price

  const ema13 = plan.daily.pivot_ribbon.ema13
  const ema21 = plan.daily.pivot_ribbon.ema21

  const scenarios: StrategyScenario[] = []

  if (refPrice > atr.call_trigger) {
    // --- BULLISH: Above Call Trigger ---
    const desc = `Price at $${fmt(refPrice)} is above Call Trigger ($${fmt(atr.call_trigger)}). GO signal for calls.`
    const setups: string[] = []
    const actions: string[] = []

    if (goldenGateBull && refPrice < goldenGateBull) {
      setups.push("Golden Gate")
      actions.push(`Watch Golden Gate Bull at $${fmt(goldenGateBull)} — break above targets Mid-Range ($${fmt(midRangeBull ?? 0)})`)
    } else if (goldenGateBull && refPrice > goldenGateBull) {
      setups.push("Trend Continuation")
      actions.push(`Already above Golden Gate ($${fmt(goldenGateBull)}) — look for continuation to Mid-Range ($${fmt(midRangeBull ?? 0)})`)
    }

    setups.push("Trend Continuation")
    actions.push(`Wait for blue candle pullback to 13/21 EMA ($${fmt(ema13)}-$${fmt(ema21)}) for entry`)

    if (ps.price_above_pdh) {
      actions.push(`Above PDH ($${fmt(ps.pdh)}) — strongly bullish structure, bias for calls`)
    }

    scenarios.push({
      label: "Call Trigger Breached",
      description: desc,
      setupsToWatch: [...new Set(setups)],
      actionItems: actions,
    })
  } else if (refPrice < atr.put_trigger) {
    // --- BEARISH: Below Put Trigger ---
    const desc = `Price at $${fmt(refPrice)} is below Put Trigger ($${fmt(atr.put_trigger)}). GO signal for puts.`
    const setups: string[] = []
    const actions: string[] = []

    if (goldenGateBear && refPrice > goldenGateBear) {
      setups.push("Golden Gate")
      actions.push(`Watch Golden Gate Bear at $${fmt(goldenGateBear)} — break below targets Mid-Range ($${fmt(midRangeBear ?? 0)})`)
    } else if (goldenGateBear && refPrice < goldenGateBear) {
      setups.push("Trend Continuation")
      actions.push(`Already below Golden Gate ($${fmt(goldenGateBear)}) — look for continuation to Mid-Range ($${fmt(midRangeBear ?? 0)})`)
    }

    setups.push("Trend Continuation")
    actions.push(`Wait for orange candle pullback to 13/21 EMA ($${fmt(ema13)}-$${fmt(ema21)}) for entry`)

    if (ps.price_below_pdl) {
      actions.push(`Below PDL ($${fmt(ps.pdl)}) — strongly bearish structure, bias for puts`)
    }

    scenarios.push({
      label: "Put Trigger Breached",
      description: desc,
      setupsToWatch: [...new Set(setups)],
      actionItems: actions,
    })
  } else {
    // --- INSIDE TRIGGER BOX (Chopzilla) ---
    const boxWidth = atr.call_trigger - atr.put_trigger
    const desc = `Price at $${fmt(refPrice)} is inside Trigger Box ($${fmt(atr.put_trigger)}-$${fmt(atr.call_trigger)}). Chopzilla territory — NO TRADE until a trigger breaks.`

    scenarios.push({
      label: "Inside Trigger Box",
      description: desc,
      setupsToWatch: [],
      actionItems: [
        `Wait for candle close above Call Trigger ($${fmt(atr.call_trigger)}) for calls`,
        `Wait for candle close below Put Trigger ($${fmt(atr.put_trigger)}) for puts`,
        `Trigger Box width: $${fmt(boxWidth)} — ${boxWidth > 3 ? "wide, stay patient" : "tight, break likely soon"}`,
      ],
    })
  }

  // --- SUPPLEMENTARY: Near Golden Gate (if not already in main scenario) ---
  if (
    goldenGateBull &&
    refPrice > atr.call_trigger &&
    Math.abs(refPrice - goldenGateBull) / goldenGateBull < 0.003
  ) {
    scenarios.push({
      label: "Golden Gate Zone",
      description: `Price near Golden Gate Bull ($${fmt(goldenGateBull)}) — key breakout level. Break above = acceleration.`,
      setupsToWatch: ["Golden Gate"],
      actionItems: [
        `If breaks above with volume → add to calls, target Mid-50 ($${fmt(mid50Bull ?? 0)})`,
        `If rejected → expect pullback to Call Trigger ($${fmt(atr.call_trigger)})`,
      ],
    })
  }
  if (
    goldenGateBear &&
    refPrice < atr.put_trigger &&
    Math.abs(refPrice - goldenGateBear) / goldenGateBear < 0.003
  ) {
    scenarios.push({
      label: "Golden Gate Zone",
      description: `Price near Golden Gate Bear ($${fmt(goldenGateBear)}) — key breakdown level. Break below = acceleration.`,
      setupsToWatch: ["Golden Gate"],
      actionItems: [
        `If breaks below with volume → add to puts, target Mid-50 ($${fmt(mid50Bear ?? 0)})`,
        `If rejected → expect bounce to Put Trigger ($${fmt(atr.put_trigger)})`,
      ],
    })
  }

  return scenarios
}

// --- Main Generator ---

/**
 * Generate strategy guidance for an instrument.
 * Pure function — no side effects.
 */
export function generateStrategyGuidance(
  plan: InstrumentPlan,
  vix: VixSnapshot,
  optionsData: InstrumentOptionsData | null,
): StrategyGuidance {
  const atr = plan.daily.atr_levels
  const ps = plan.daily.price_structure
  const refPrice = ps.premarket_price ?? atr.current_price

  // Headline
  let headline: string
  if (refPrice > atr.call_trigger) {
    headline = "Bullish — above Call Trigger"
  } else if (refPrice < atr.put_trigger) {
    headline = "Bearish — below Put Trigger"
  } else {
    headline = "Chopzilla — inside Trigger Box"
  }

  return {
    headline,
    gapReading: interpretGap(ps.gap_scenario),
    scenarios: buildScenarios(plan),
    emAtr: buildEmAtrComparison(plan, optionsData),
    vixPremkt: buildVixPremarketContext(vix),
    atrNote: buildAtrNote(atr.atr_covered_pct),
    entryReminder: "Wait for BLUE candle (bullish pullback) or ORANGE candle (bearish pullback). Never chase GREEN or RED breakout candles.",
  }
}
