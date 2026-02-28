// ---------------------------------------------------------------------------
// Daily Plan Generation — shared logic between the generate route and cron.
// Fetches multi-TF data from Railway, computes targets, writes to Supabase.
// ---------------------------------------------------------------------------

import { calculateIndicators, getTradePlan } from "./railway"
import { computeTargets } from "./targets"
import { createServerClient } from "./supabase/server"
import { INSTRUMENTS, VIX_TICKER } from "./daily-plan-types"
import type {
  DailyPlanData,
  DailyPlanRow,
  InstrumentPlan,
  VixSnapshot,
} from "./daily-plan-types"
import type { CalculateResponse, TradePlanResponse } from "./types"

function getSession(): string {
  const hourUTC = new Date().getUTCHours()
  // 13:00 UTC = 8AM ET (premarket), 21:30 UTC = 4:30PM ET (after close)
  return hourUTC < 18 ? "premarket" : "after_close"
}

function buildVixSnapshot(vixData: CalculateResponse): VixSnapshot {
  const price = vixData.atr_levels.current_price
  let keyLevel: string
  if (price < 14) keyLevel = "Below 14 — very low vol, complacent"
  else if (price < 17) keyLevel = "Below 17 — bullish bias"
  else if (price < 20) keyLevel = "17-20 — neutral, watch for expansion"
  else if (price < 25) keyLevel = "20-25 — elevated, bearish bias"
  else keyLevel = "Above 25 — fear, expect volatility"

  return {
    price,
    atrStatus: vixData.atr_levels.atr_status,
    trend: vixData.atr_levels.trend,
    phase: vixData.phase_oscillator.phase,
    keyLevel,
  }
}

interface GenerateResult {
  data: DailyPlanData
  errors: { ticker: string; error: string }[]
}

/**
 * Fetch all multi-TF data for SPY/SPX + VIX, compute targets, write to Supabase.
 */
export async function generateDailyPlan(
  session?: string,
): Promise<GenerateResult> {
  const resolvedSession = session ?? getSession()
  const now = new Date().toISOString()
  const errors: { ticker: string; error: string }[] = []

  // Always use current close — plan is generated when market is closed
  // (after close or premarket), so the last bar is settled.
  const ucc = { use_current_close: true }

  // --- Fetch VIX ---
  let vix: VixSnapshot = {
    price: 0,
    atrStatus: "orange",
    trend: "neutral",
    phase: "compression",
    keyLevel: "N/A",
  }
  try {
    const vixData = await calculateIndicators(VIX_TICKER, "1d", ucc)
    vix = buildVixSnapshot(vixData)
  } catch (err) {
    errors.push({ ticker: VIX_TICKER, error: String(err) })
  }

  // --- Fetch instruments in parallel ---
  const instrumentPlans: InstrumentPlan[] = []

  const instrumentPromises = INSTRUMENTS.map(async (inst) => {
    try {
      // 4 parallel calls per instrument — use_current_close=true since
      // the plan is always generated when market is closed.
      const [daily, hourly, fifteenMin, weekly] = await Promise.all([
        getTradePlan(inst.ticker, "1d", "bullish", vix.price || undefined, ucc),
        calculateIndicators(inst.ticker, "1h", ucc),
        calculateIndicators(inst.ticker, "15m", ucc),
        calculateIndicators(inst.ticker, "1w", ucc),
      ])

      const targets = computeTargets(
        daily as TradePlanResponse,
        hourly,
        fifteenMin,
        weekly,
      )

      return {
        ticker: inst.ticker,
        displayName: inst.displayName,
        daily: daily as TradePlanResponse,
        hourly,
        fifteenMin,
        weekly,
        targets,
      } satisfies InstrumentPlan
    } catch (err) {
      errors.push({ ticker: inst.ticker, error: String(err) })
      return null
    }
  })

  const results = await Promise.all(instrumentPromises)
  for (const r of results) {
    if (r) instrumentPlans.push(r)
  }

  // --- Write to Supabase ---
  const supabase = createServerClient()

  // Delete today's rows for same session to prevent duplicates
  const today = new Date().toISOString().slice(0, 10) // YYYY-MM-DD
  for (const plan of instrumentPlans) {
    await supabase
      .from("daily_trade_plans")
      .delete()
      .eq("ticker", plan.ticker)
      .eq("session", resolvedSession)
      .gte("fetched_at", `${today}T00:00:00Z`)
      .lt("fetched_at", `${today}T23:59:59Z`)
  }

  // Insert fresh rows
  for (const plan of instrumentPlans) {
    const { error } = await supabase.from("daily_trade_plans").insert({
      ticker: plan.ticker,
      display_name: plan.displayName,
      session: resolvedSession,
      fetched_at: now,
      daily: plan.daily,
      hourly: plan.hourly,
      fifteen_min: plan.fifteenMin,
      weekly: plan.weekly,
      vix,
      targets: plan.targets,
    })
    if (error) {
      errors.push({ ticker: plan.ticker, error: `Supabase: ${error.message}` })
    }
  }

  const data: DailyPlanData = {
    instruments: instrumentPlans,
    vix,
    session: resolvedSession,
    fetchedAt: now,
  }

  return { data, errors }
}

/**
 * Read the latest daily plan from Supabase.
 */
export async function readDailyPlan(): Promise<DailyPlanData | null> {
  const supabase = createServerClient()

  // Get latest row per ticker, ordered by fetched_at desc
  const { data: rows, error } = await supabase
    .from("daily_trade_plans")
    .select("*")
    .order("fetched_at", { ascending: false })
    .limit(10) // safe upper bound

  if (error || !rows || rows.length === 0) return null

  // De-duplicate: keep only the latest row per ticker
  const seen = new Set<string>()
  const latest: DailyPlanRow[] = []
  for (const row of rows as DailyPlanRow[]) {
    if (!seen.has(row.ticker)) {
      seen.add(row.ticker)
      latest.push(row)
    }
  }

  if (latest.length === 0) return null

  const instruments: InstrumentPlan[] = latest.map((row) => ({
    ticker: row.ticker,
    displayName: row.display_name,
    daily: row.daily,
    hourly: row.hourly,
    fifteenMin: row.fifteen_min,
    weekly: row.weekly,
    targets: row.targets ?? { upside: [], downside: [] },
  }))

  return {
    instruments,
    vix: latest[0].vix ?? {
      price: 0,
      atrStatus: "orange",
      trend: "neutral",
      phase: "compression",
      keyLevel: "N/A",
    },
    session: latest[0].session,
    fetchedAt: latest[0].fetched_at,
  }
}
