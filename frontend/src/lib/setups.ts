// ---------------------------------------------------------------------------
// Setup Detection Engine — pure TS functions, no React.
// Maps TradePlanResponse data to well-defined Saty setups (1-9).
// ---------------------------------------------------------------------------

import type { TradePlanResponse } from "./types"

// --- Types ---

export type SetupId =
  | "trend_continuation"
  | "golden_gate"
  | "vomy"
  | "ivomy"
  | "squeeze"
  | "divergence_extreme"
  | "dip_connoisseur"

export type SetupConfidence = "strong" | "moderate" | "forming"

export interface SetupCondition {
  label: string
  met: boolean
  required: boolean
}

export interface DetectedSetup {
  id: SetupId
  name: string
  shortName: string
  number: number
  color: string
  direction: "bullish" | "bearish"
  confidence: SetupConfidence
  conditions: SetupCondition[]
  conditionsMet: number
  conditionsTotal: number
  entryZone: string
  target: string
  stop: string
  entryPrice: number | null
  targetPrice: number | null
  stopPrice: number | null
}

// --- Metadata ---

export const SETUP_META: Record<
  SetupId,
  { number: number; name: string; shortName: string; color: string }
> = {
  trend_continuation: { number: 1, name: "Trend Continuation", shortName: "Trend Cont.", color: "emerald" },
  golden_gate:        { number: 2, name: "Golden Gate",        shortName: "Golden Gate", color: "teal" },
  vomy:               { number: 3, name: "Vomy",               shortName: "Vomy",        color: "red" },
  ivomy:              { number: 4, name: "iVomy",              shortName: "iVomy",       color: "blue" },
  squeeze:            { number: 5, name: "Squeeze",            shortName: "Squeeze",     color: "purple" },
  divergence_extreme: { number: 7, name: "Divergence",         shortName: "Divergence",  color: "yellow" },
  dip_connoisseur:    { number: 9, name: "Dip Connoisseur",    shortName: "Dip Conn.",   color: "amber" },
}

// --- Helpers ---

function fmt(n: number | null | undefined): string {
  if (n == null) return "--"
  return `$${n.toFixed(2)}`
}

function calcConfidence(
  conditions: SetupCondition[]
): SetupConfidence | null {
  const required = conditions.filter((c) => c.required)
  const optional = conditions.filter((c) => !c.required)
  const requiredMet = required.filter((c) => c.met).length
  const optionalMet = optional.filter((c) => c.met).length

  // ALL required must be met — no "forming" from partial required
  if (requiredMet < required.length) return null

  // All required met
  if (optional.length === 0) return "strong"
  if (optionalMet >= Math.ceil(optional.length * 0.5)) return "strong"
  return "moderate"
}

function buildSetup(
  id: SetupId,
  direction: "bullish" | "bearish",
  conditions: SetupCondition[],
  entry: { zone: string; price: number | null },
  target: { zone: string; price: number | null },
  stop: { zone: string; price: number | null }
): DetectedSetup | null {
  const confidence = calcConfidence(conditions)
  if (!confidence) return null

  const meta = SETUP_META[id]
  return {
    id,
    name: meta.name,
    shortName: meta.shortName,
    number: meta.number,
    color: meta.color,
    direction,
    confidence,
    conditions,
    conditionsMet: conditions.filter((c) => c.met).length,
    conditionsTotal: conditions.length,
    entryZone: entry.zone,
    target: target.zone,
    stop: stop.zone,
    entryPrice: entry.price,
    targetPrice: target.price,
    stopPrice: stop.price,
  }
}

// --- Detectors ---

function detectTrendContinuation(d: TradePlanResponse): DetectedSetup | null {
  const { atr_levels: atr, pivot_ribbon: ribbon, phase_oscillator: phase } = d
  const isBullish = ribbon.ribbon_state === "bullish"
  const isBearish = ribbon.ribbon_state === "bearish"
  if (!isBullish && !isBearish) return null

  const dir = isBullish ? "bullish" as const : "bearish" as const
  const pullbackCandle = isBullish ? "blue" : "orange"
  const pullback = ribbon.bias_candle === pullbackCandle
  const phaseFiring = isBullish
    ? phase.phase === "green"
    : phase.phase === "red"

  const conditions: SetupCondition[] = [
    { label: `Ribbon stacked ${dir}`, met: true, required: true },
    { label: pullback ? `${isBullish ? "Blue" : "Orange"} pullback candle` : "Pullback candle needed", met: pullback, required: true },
    { label: `Phase firing ${isBullish ? "green" : "red"}`, met: phaseFiring, required: true },
    { label: "ATR room available", met: atr.atr_room_ok, required: true },
    { label: "Above 48 EMA", met: ribbon.above_48ema, required: false },
    { label: "Above 200 EMA", met: ribbon.above_200ema, required: false },
    { label: "No chopzilla", met: !atr.chopzilla, required: false },
  ]

  const entryLow = Math.min(ribbon.ema13, ribbon.ema21)
  const entryHigh = Math.max(ribbon.ema13, ribbon.ema21)
  const targetLevel = isBullish
    ? atr.levels?.mid_range_bull
    : atr.levels?.mid_range_bear

  return buildSetup(
    "trend_continuation",
    dir,
    conditions,
    { zone: `EMA 13/21 bounce (${fmt(entryLow)}–${fmt(entryHigh)})`, price: isBullish ? entryLow : entryHigh },
    { zone: `Mid-Range 61.8% (${fmt(targetLevel?.price)})`, price: targetLevel?.price ?? null },
    { zone: `${isBullish ? "Below" : "Above"} 48 EMA (${fmt(ribbon.ema48)})`, price: ribbon.ema48 }
  )
}

function detectGoldenGate(d: TradePlanResponse): DetectedSetup | null {
  const { atr_levels: atr, pivot_ribbon: ribbon, phase_oscillator: phase } = d
  const pos = atr.price_position

  // Only trigger when price is specifically at or just past the golden gate level
  const isBullGG = pos === "above_golden_gate"
  const isBearGG = pos === "below_golden_gate"

  if (!isBullGG && !isBearGG) return null

  const dir = isBullGG ? "bullish" as const : "bearish" as const
  const ribbonStacked = dir === "bullish"
    ? ribbon.ribbon_state === "bullish"
    : ribbon.ribbon_state === "bearish"
  const phaseFiring = dir === "bullish"
    ? phase.phase === "green"
    : phase.phase === "red"

  const conditions: SetupCondition[] = [
    { label: `Price ${dir === "bullish" ? "above" : "below"} Golden Gate`, met: true, required: true },
    { label: `Ribbon stacked ${dir}`, met: ribbonStacked, required: true },
    { label: `Phase firing ${dir === "bullish" ? "green" : "red"}`, met: phaseFiring, required: true },
    { label: "ATR room available", met: atr.atr_room_ok, required: false },
    { label: "No chopzilla", met: !atr.chopzilla, required: false },
  ]

  const ggLevel = dir === "bullish"
    ? atr.levels?.golden_gate_bull
    : atr.levels?.golden_gate_bear
  const targetLevel = dir === "bullish"
    ? atr.levels?.mid_range_bull
    : atr.levels?.mid_range_bear

  return buildSetup(
    "golden_gate",
    dir,
    conditions,
    { zone: `Pullback to ribbon after GG break (${fmt(ggLevel?.price)})`, price: ggLevel?.price ?? null },
    { zone: `Mid-Range 61.8% (${fmt(targetLevel?.price)})`, price: targetLevel?.price ?? null },
    { zone: `Reclaim of Golden Gate (${fmt(ggLevel?.price)})`, price: ggLevel?.price ?? null }
  )
}

function detectVomy(d: TradePlanResponse): DetectedSetup | null {
  const { pivot_ribbon: ribbon, phase_oscillator: phase, atr_levels: atr } = d

  // Bearish/chopzilla ribbon, below 48 EMA, orange pullback (short setup)
  const ribbonBearish = ribbon.ribbon_state === "bearish" || ribbon.ribbon_state === "chopzilla"
  const below48 = !ribbon.above_48ema
  const orangeCandle = ribbon.bias_candle === "orange"

  const conditions: SetupCondition[] = [
    { label: "Ribbon bearish or chopzilla", met: ribbonBearish, required: true },
    { label: "Below 48 EMA", met: below48, required: true },
    { label: "Orange pullback candle", met: orangeCandle, required: true },
    {
      label: "Recent bearish crossover",
      met: ribbon.last_conviction_type === "bearish_crossover" && (ribbon.last_conviction_bars_ago ?? 999) <= 10,
      required: false,
    },
    { label: "Phase firing red", met: phase.phase === "red", required: false },
  ]

  const targetLevel = atr.levels?.mid_range_bear

  return buildSetup(
    "vomy",
    "bearish",
    conditions,
    { zone: `Rally to EMA 13 fails (${fmt(ribbon.ema13)})`, price: ribbon.ema13 },
    { zone: `Mid-Range Bear (${fmt(targetLevel?.price)})`, price: targetLevel?.price ?? null },
    { zone: `Above 21 EMA (${fmt(ribbon.ema21)})`, price: ribbon.ema21 }
  )
}

function detectIvomy(d: TradePlanResponse): DetectedSetup | null {
  const { pivot_ribbon: ribbon, phase_oscillator: phase, atr_levels: atr } = d

  // Chopzilla ribbon (transitioning, NOT already fully bullish), above 48 EMA, blue pullback
  // If ribbon is already "bullish", that's Trend Continuation, not iVomy
  const ribbonTransitioning = ribbon.ribbon_state === "chopzilla"
  const above48 = ribbon.above_48ema
  const blueCandle = ribbon.bias_candle === "blue"

  const conditions: SetupCondition[] = [
    { label: "Ribbon transitioning (chopzilla)", met: ribbonTransitioning, required: true },
    { label: "Above 48 EMA", met: above48, required: true },
    { label: "Blue pullback candle", met: blueCandle, required: true },
    {
      label: "Recent bullish crossover",
      met: ribbon.last_conviction_type === "bullish_crossover" && (ribbon.last_conviction_bars_ago ?? 999) <= 10,
      required: false,
    },
    { label: "Phase firing green", met: phase.phase === "green", required: false },
  ]

  const targetLevel = atr.levels?.mid_range_bull

  return buildSetup(
    "ivomy",
    "bullish",
    conditions,
    { zone: `Pullback to EMA 13 holds (${fmt(ribbon.ema13)})`, price: ribbon.ema13 },
    { zone: `Mid-Range Bull (${fmt(targetLevel?.price)})`, price: targetLevel?.price ?? null },
    { zone: `Below 21 EMA (${fmt(ribbon.ema21)})`, price: ribbon.ema21 }
  )
}

function detectSqueeze(d: TradePlanResponse): DetectedSetup | null {
  const { pivot_ribbon: ribbon, phase_oscillator: phase, atr_levels: atr, mtf_phases: mtfPhases } = d

  const phaseCompressed = phase.in_compression
  const ribbonCompressed = ribbon.in_compression
  // Need at least one compression source
  if (!phaseCompressed && !ribbonCompressed) return null

  // Nested squeeze: all MTF timeframes also in compression
  const nestedSqueeze = mtfPhases
    ? Object.values(mtfPhases).every((p) => p.in_compression)
    : false

  const conditions: SetupCondition[] = [
    { label: "Phase in compression", met: phaseCompressed, required: true },
    { label: "Ribbon in compression", met: ribbonCompressed, required: true },
    { label: "No ATR chopzilla", met: !atr.chopzilla, required: false },
    { label: "Nested squeeze (MTF compressed)", met: nestedSqueeze, required: false },
    { label: "Ribbon not folded", met: ribbon.ribbon_state !== "chopzilla", required: false },
  ]

  // Direction based on ribbon state; if chopzilla use 48 EMA as tiebreaker
  let dir: "bullish" | "bearish"
  if (ribbon.ribbon_state === "bullish") dir = "bullish"
  else if (ribbon.ribbon_state === "bearish") dir = "bearish"
  else dir = ribbon.above_48ema ? "bullish" : "bearish"

  const nextLevel = dir === "bullish"
    ? atr.levels?.golden_gate_bull ?? atr.levels?.mid_range_bull
    : atr.levels?.golden_gate_bear ?? atr.levels?.mid_range_bear

  return buildSetup(
    "squeeze",
    dir,
    conditions,
    { zone: `Compression break (${fmt(atr.current_price)})`, price: atr.current_price },
    { zone: `Next ATR level (${fmt(nextLevel?.price)})`, price: nextLevel?.price ?? null },
    { zone: `Opposite side of ribbon (${fmt(ribbon.ema21)})`, price: ribbon.ema21 }
  )
}

function detectDivergenceExtreme(d: TradePlanResponse): DetectedSetup | null {
  const { phase_oscillator: phase, pivot_ribbon: ribbon, atr_levels: atr } = d

  const extremeZones = new Set(["extreme_up", "extreme_down", "distribution", "accumulation"])
  const inExtreme = extremeZones.has(phase.current_zone)
  const hasMR = phase.last_mr_type != null
  const mrRecent = (phase.last_mr_bars_ago ?? 999) <= 5

  // All three are required
  if (!inExtreme || !hasMR || !mrRecent) return null

  // Direction based on zone
  const bottomZones = new Set(["extreme_down", "accumulation"])
  const dir = bottomZones.has(phase.current_zone) ? "bullish" as const : "bearish" as const

  // Phase reversing direction
  const phaseReversing = dir === "bullish"
    ? phase.oscillator > phase.oscillator_prev
    : phase.oscillator < phase.oscillator_prev

  const conditions: SetupCondition[] = [
    { label: `In extreme zone (${phase.current_zone.replace(/_/g, " ")})`, met: inExtreme, required: true },
    { label: "Mean reversion signal present", met: hasMR, required: true },
    { label: `Mean reversion recent (${phase.last_mr_bars_ago ?? "--"}b ago)`, met: mrRecent, required: true },
    { label: "Phase reversing direction", met: phaseReversing, required: false },
  ]

  return buildSetup(
    "divergence_extreme",
    dir,
    conditions,
    { zone: `Mean reversion bar (${fmt(atr.current_price)})`, price: atr.current_price },
    { zone: `Return to 21 EMA (${fmt(ribbon.ema21)})`, price: ribbon.ema21 },
    { zone: "New extreme", price: null }
  )
}

function detectDipConnoisseur(d: TradePlanResponse): DetectedSetup | null {
  const { atr_levels: atr, phase_oscillator: phase, pivot_ribbon: ribbon } = d

  const belowMidRange = atr.price_position === "below_mid_range"
    || atr.price_position === "below_full_range"

  if (!belowMidRange) return null

  const leavingAccum = phase.zone_crosses.leaving_accumulation
    || phase.zone_crosses.leaving_extreme_down
  const phaseReversal = phase.oscillator > phase.oscillator_prev

  // Need at least one confirmation signal beyond just being below mid-range
  const conditions: SetupCondition[] = [
    { label: "Price below mid-range or full-range", met: belowMidRange, required: true },
    { label: "Leaving accumulation / extreme down", met: leavingAccum, required: true },
    { label: "Phase reversing upward", met: phaseReversal, required: false },
  ]

  const ggLevel = atr.levels?.golden_gate_bull
  const midLevel = atr.levels?.mid_range_bull

  return buildSetup(
    "dip_connoisseur",
    "bullish",
    conditions,
    { zone: `Ribbon stabilization (${fmt(ribbon.ema13)})`, price: ribbon.ema13 },
    { zone: `Golden Gate / Mid-Range (${fmt(ggLevel?.price ?? midLevel?.price)})`, price: ggLevel?.price ?? midLevel?.price ?? null },
    { zone: "New low / below Full Range", price: atr.levels?.full_range_bear?.price ?? null }
  )
}

// --- Main Entry ---

const DETECTORS: Array<(d: TradePlanResponse) => DetectedSetup | null> = [
  detectTrendContinuation,
  detectGoldenGate,
  detectVomy,
  detectIvomy,
  detectSqueeze,
  detectDivergenceExtreme,
  detectDipConnoisseur,
]

export function detectSetups(data: TradePlanResponse): DetectedSetup[] {
  return DETECTORS
    .map((fn) => fn(data))
    .filter((s): s is DetectedSetup => s != null)
    .sort((a, b) => {
      // Strong first, then moderate
      const order = { strong: 0, moderate: 1, forming: 2 }
      return order[a.confidence] - order[b.confidence]
    })
}
