// ---------------------------------------------------------------------------
// Target Calculation — collects all price levels from multi-TF data,
// clusters them by proximity (confluences), and returns top 3 up/down.
// ---------------------------------------------------------------------------

import type { CalculateResponse, TradePlanResponse } from "./types"
import type { Target } from "./daily-plan-types"

// --- Level collector ---

interface RawLevel {
  price: number
  label: string
  source: string
}

/** Confluence clustering threshold — levels within this % of each other merge. */
const CONFLUENCE_PCT = 0.0015 // 0.15%

/**
 * Collect all meaningful price levels from multi-timeframe indicator data.
 */
function collectLevels(
  daily: TradePlanResponse,
  hourly: CalculateResponse,
  fifteenMin: CalculateResponse,
  weekly: CalculateResponse,
): RawLevel[] {
  const levels: RawLevel[] = []

  function add(price: number | null | undefined, label: string, source: string) {
    if (price != null && isFinite(price)) {
      levels.push({ price, label, source })
    }
  }

  // --- ATR Fibonacci levels (daily — primary) ---
  const atr = daily.atr_levels
  add(atr.call_trigger, "Call Trigger", "ATR 1D")
  add(atr.put_trigger, "Put Trigger", "ATR 1D")
  const lvls = atr.levels || {}
  add(lvls.golden_gate_bull?.price, "Golden Gate Bull", "ATR 1D")
  add(lvls.golden_gate_bear?.price, "Golden Gate Bear", "ATR 1D")
  add(lvls.mid_50_bull?.price, "Mid 50 Bull", "ATR 1D")
  add(lvls.mid_50_bear?.price, "Mid 50 Bear", "ATR 1D")
  add(lvls.mid_range_bull?.price, "Mid Range Bull", "ATR 1D")
  add(lvls.mid_range_bear?.price, "Mid Range Bear", "ATR 1D")
  add(lvls.fib_786_bull?.price, "Fib 786 Bull", "ATR 1D")
  add(lvls.fib_786_bear?.price, "Fib 786 Bear", "ATR 1D")
  add(lvls.full_range_bull?.price, "Full Range Bull", "ATR 1D")
  add(lvls.full_range_bear?.price, "Full Range Bear", "ATR 1D")

  // --- Hourly ATR triggers ---
  add(hourly.atr_levels.call_trigger, "Call Trigger", "ATR 1H")
  add(hourly.atr_levels.put_trigger, "Put Trigger", "ATR 1H")

  // --- EMAs across all timeframes ---
  const emaNames = ["ema8", "ema13", "ema21", "ema48", "ema200"] as const
  const tfData: { data: CalculateResponse; label: string }[] = [
    { data: weekly, label: "1W" },
    { data: daily, label: "1D" },
    { data: hourly, label: "1H" },
    { data: fifteenMin, label: "15m" },
  ]
  for (const { data, label } of tfData) {
    for (const ema of emaNames) {
      add(data.pivot_ribbon[ema], ema.toUpperCase(), `EMA ${label}`)
    }
  }

  // --- Price Structure (daily) ---
  const ps = daily.price_structure
  add(ps.pdh, "PDH", "Structure")
  add(ps.pdl, "PDL", "Structure")
  add(ps.pmh, "PMH", "Structure")
  add(ps.pml, "PML", "Structure")

  // --- Key Pivots ---
  const kp = daily.key_pivots
  if (kp) {
    add(kp.pwh, "PWH", "Pivot")
    add(kp.pwl, "PWL", "Pivot")
    add(kp.pwc, "PWC", "Pivot")
    add(kp.pmoh, "PMoH", "Pivot")
    add(kp.pmol, "PMoL", "Pivot")
    add(kp.pmoc, "PMoC", "Pivot")
    add(kp.pqc, "PQC", "Pivot")
    add(kp.pyc, "PYC", "Pivot")
  }

  return levels
}

/**
 * Cluster nearby levels into confluence zones.
 * Returns sorted targets with confluence info.
 */
function clusterLevels(
  levels: RawLevel[],
  direction: "up" | "down",
): Target[] {
  if (levels.length === 0) return []

  // Sort by price
  const sorted = [...levels].sort((a, b) =>
    direction === "up" ? a.price - b.price : b.price - a.price
  )

  // Group into clusters: levels within CONFLUENCE_PCT of each other
  const clusters: RawLevel[][] = []
  let current: RawLevel[] = [sorted[0]]

  for (let i = 1; i < sorted.length; i++) {
    const anchor = current[0].price
    const pctDiff = Math.abs(sorted[i].price - anchor) / anchor
    if (pctDiff <= CONFLUENCE_PCT) {
      current.push(sorted[i])
    } else {
      clusters.push(current)
      current = [sorted[i]]
    }
  }
  clusters.push(current)

  // Convert clusters to targets, sorted by confluence count desc then proximity
  const targets: Target[] = clusters.map((cluster) => {
    // Use the level with the most "weight" as the primary
    // Priority: ATR levels > Pivots > EMAs
    const primary = cluster.reduce((best, l) => {
      const weight = l.source.startsWith("ATR") ? 3 : l.source === "Structure" || l.source === "Pivot" ? 2 : 1
      const bestWeight = best.source.startsWith("ATR") ? 3 : best.source === "Structure" || best.source === "Pivot" ? 2 : 1
      return weight > bestWeight ? l : best
    })

    const confluences = cluster
      .filter((l) => l !== primary)
      .map((l) => `${l.label} (${l.source})`)

    return {
      price: primary.price,
      label: primary.label,
      source: primary.source,
      confluences,
      confluenceCount: cluster.length,
    }
  })

  // Targets are already in price-proximity order (ascending for up, descending for down)
  // from the initial sort. We keep that order — the DirectionalPlan shows T1 → T2 → T3
  // nearest to farthest from current price. Confluence info is attached but doesn't
  // change the ordering.
  return targets.slice(0, 3)
}

/**
 * Compute 3 upside + 3 downside targets with confluence detection.
 */
export function computeTargets(
  daily: TradePlanResponse,
  hourly: CalculateResponse,
  fifteenMin: CalculateResponse,
  weekly: CalculateResponse,
): { upside: Target[]; downside: Target[] } {
  const currentPrice = daily.atr_levels.current_price
  const allLevels = collectLevels(daily, hourly, fifteenMin, weekly)

  const upside = allLevels.filter((l) => l.price > currentPrice)
  const downside = allLevels.filter((l) => l.price < currentPrice)

  return {
    upside: clusterLevels(upside, "up"),
    downside: clusterLevels(downside, "down"),
  }
}

// Export for testing
export { collectLevels, clusterLevels, CONFLUENCE_PCT }
export type { RawLevel }
