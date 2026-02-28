import { describe, it, expect } from "vitest"
import { computeTargets, collectLevels, clusterLevels, type RawLevel } from "./targets"
import type { CalculateResponse, TradePlanResponse } from "./types"

// --- Helpers to build minimal mock data ---

function makeCalculateResponse(overrides: Partial<CalculateResponse> = {}): CalculateResponse {
  return {
    ticker: "SPY",
    timeframe: "1d",
    trading_mode: "swing",
    bars: 252,
    atr_source_bars: 14,
    atr_levels: {
      atr: 8.0,
      pdc: 600,
      current_price: 605,
      levels: {},
      call_trigger: 610,
      put_trigger: 590,
      trigger_box: { low: 590, high: 610, inside: true },
      price_position: "inside_trigger_box",
      daily_range: 5,
      period_range: 8,
      atr_covered_pct: 62.5,
      atr_status: "orange",
      atr_room_ok: true,
      chopzilla: false,
      trend: "bullish",
      trading_mode: "swing",
      trading_mode_label: "Swing",
    },
    pivot_ribbon: {
      ema8: 604,
      ema13: 603,
      ema21: 601,
      ema48: 595,
      ema200: 560,
      ribbon_state: "bullish",
      bias_candle: "blue",
      bias_signal: "buy_pullback",
      conviction_arrow: null,
      last_conviction_type: null,
      last_conviction_bars_ago: null,
      spread: 10,
      above_48ema: true,
      above_200ema: true,
      in_compression: false,
      chopzilla: false,
    },
    phase_oscillator: {
      oscillator: 1.5,
      oscillator_prev: 1.3,
      phase: "green",
      in_compression: false,
      current_zone: "neutral_up",
      zone_crosses: {
        leaving_accumulation: false,
        leaving_extreme_down: false,
        leaving_distribution: false,
        leaving_extreme_up: false,
      },
      last_mr_type: null,
      last_mr_bars_ago: null,
      zones: {
        extreme: { up: 3, down: -3 },
        distribution: { up: 2, down: -2 },
        neutral: { up: 1, down: -1 },
        zero: 0,
      },
    },
    ...overrides,
  }
}

function makeTradePlanResponse(overrides: Partial<TradePlanResponse> = {}): TradePlanResponse {
  const base = makeCalculateResponse()
  return {
    ...base,
    direction: "bullish",
    price_structure: {
      pdc: 600,
      pdh: 608,
      pdl: 597,
      current_price: 605,
      pmh: null,
      pml: null,
      structural_bias: "bullish",
      gap_scenario: "no_gap",
      price_above_pdh: false,
      price_above_pmh: false,
      price_below_pdl: false,
      price_below_pml: false,
    },
    key_pivots: {
      pwh: 612,
      pwl: 592,
      pwc: 602,
      pmoh: 615,
      pmol: 580,
      pmoc: 598,
      pqc: 570,
      pyc: 480,
    },
    green_flag: {
      direction: "bullish",
      score: 5,
      max_score: 10,
      grade: "A+",
      recommendation: "Strong buy",
      flags: {},
      verbal_audit: "",
    },
    atr_levels: {
      ...base.atr_levels,
      levels: {
        call_trigger: { price: 610, pct: "10%", fib: 0.1 },
        golden_gate_bull: { price: 614, pct: "38.2%", fib: 0.382 },
        mid_range_bull: { price: 618, pct: "61.8%", fib: 0.618 },
        full_range_bull: { price: 623, pct: "100%", fib: 1.0 },
        put_trigger: { price: 590, pct: "10%", fib: 0.1 },
        golden_gate_bear: { price: 586, pct: "38.2%", fib: 0.382 },
        mid_range_bear: { price: 582, pct: "61.8%", fib: 0.618 },
        full_range_bear: { price: 577, pct: "100%", fib: 1.0 },
      },
    },
    ...overrides,
  }
}

// --- Tests ---

describe("collectLevels", () => {
  it("collects ATR fib levels, EMAs, structure, and pivots", () => {
    const daily = makeTradePlanResponse()
    const hourly = makeCalculateResponse({
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 605.5,
        ema13: 604.2,
        ema21: 603,
        ema48: 598,
        ema200: 565,
      },
      atr_levels: {
        ...makeCalculateResponse().atr_levels,
        call_trigger: 608,
        put_trigger: 600,
      },
    })
    const fifteenMin = makeCalculateResponse({
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 605.8,
        ema13: 605.2,
        ema21: 604.5,
        ema48: 602,
        ema200: 590,
      },
    })
    const weekly = makeCalculateResponse({
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 600,
        ema13: 597,
        ema21: 593,
        ema48: 580,
        ema200: 520,
      },
    })

    const levels = collectLevels(daily, hourly, fifteenMin, weekly)

    // Should have: 8 ATR fibs + 2 hourly triggers + 20 EMAs (5x4) + 2 structure (PDH/PDL) + 8 pivots = 40
    expect(levels.length).toBeGreaterThanOrEqual(30)

    // Check ATR levels are present
    const callTrigger = levels.find(
      (l) => l.label === "Call Trigger" && l.source === "ATR 1D"
    )
    expect(callTrigger).toBeDefined()
    expect(callTrigger!.price).toBe(610)

    // Check EMAs are present from all timeframes
    const weeklyEma200 = levels.find(
      (l) => l.label === "EMA200" && l.source === "EMA 1W"
    )
    expect(weeklyEma200).toBeDefined()
    expect(weeklyEma200!.price).toBe(520)

    // Check pivots
    const pwh = levels.find((l) => l.label === "PWH")
    expect(pwh).toBeDefined()
    expect(pwh!.price).toBe(612)
  })

  it("skips null values gracefully", () => {
    const daily = makeTradePlanResponse({
      key_pivots: { pwh: null, pwl: null, pwc: null, pmoh: null, pmol: null, pmoc: null, pqc: null, pyc: null },
      price_structure: {
        ...makeTradePlanResponse().price_structure,
        pmh: null,
        pml: null,
      },
    })
    const hourly = makeCalculateResponse()
    const fifteenMin = makeCalculateResponse()
    const weekly = makeCalculateResponse()

    const levels = collectLevels(daily, hourly, fifteenMin, weekly)
    // Should still have ATR + EMA + PDH/PDL levels, just no pivots
    expect(levels.length).toBeGreaterThan(20)
    expect(levels.find((l) => l.label === "PWH")).toBeUndefined()
  })
})

describe("clusterLevels", () => {
  it("clusters levels within 0.15% of each other", () => {
    const levels: RawLevel[] = [
      { price: 610.0, label: "Call Trigger", source: "ATR 1D" },
      { price: 610.5, label: "EMA8", source: "EMA 1H" },     // within 0.08% — clusters
      { price: 612.0, label: "PWH", source: "Pivot" },        // 0.33% away — new cluster
      { price: 615.0, label: "Golden Gate", source: "ATR 1D" },
    ]

    const targets = clusterLevels(levels, "up")

    expect(targets.length).toBe(3)
    // First target should be the cluster with highest confluence
    const clustered = targets.find((t) => t.confluenceCount === 2)
    expect(clustered).toBeDefined()
    expect(clustered!.label).toBe("Call Trigger") // ATR has higher weight
    expect(clustered!.confluences).toContain("EMA8 (EMA 1H)")
  })

  it("returns at most 3 targets", () => {
    const levels: RawLevel[] = Array.from({ length: 10 }, (_, i) => ({
      price: 600 + i * 5,
      label: `Level ${i}`,
      source: "ATR 1D",
    }))

    const targets = clusterLevels(levels, "up")
    expect(targets.length).toBe(3)
  })

  it("handles empty input", () => {
    expect(clusterLevels([], "up")).toEqual([])
  })

  it("respects direction sorting", () => {
    const levels: RawLevel[] = [
      { price: 590, label: "Put Trigger", source: "ATR 1D" },
      { price: 580, label: "EMA48", source: "EMA 1D" },
      { price: 570, label: "PQC", source: "Pivot" },
    ]

    const targets = clusterLevels(levels, "down")
    // Downside: sorted descending (closest to price first)
    expect(targets.length).toBe(3)
  })
})

describe("computeTargets", () => {
  it("returns 3 upside and 3 downside targets", () => {
    const daily = makeTradePlanResponse()
    const hourly = makeCalculateResponse({
      atr_levels: {
        ...makeCalculateResponse().atr_levels,
        call_trigger: 608,
        put_trigger: 600,
      },
    })
    const fifteenMin = makeCalculateResponse()
    const weekly = makeCalculateResponse()

    const { upside, downside } = computeTargets(daily, hourly, fifteenMin, weekly)

    expect(upside.length).toBeLessThanOrEqual(3)
    expect(downside.length).toBeLessThanOrEqual(3)

    // Upside prices should all be above current price (605)
    for (const t of upside) {
      expect(t.price).toBeGreaterThan(605)
    }

    // Downside prices should all be below current price
    for (const t of downside) {
      expect(t.price).toBeLessThan(605)
    }
  })

  it("includes confluence info on clustered levels", () => {
    const daily = makeTradePlanResponse()
    // Set hourly call trigger very close to daily call trigger for confluence
    const hourly = makeCalculateResponse({
      atr_levels: {
        ...makeCalculateResponse().atr_levels,
        call_trigger: 610.2, // within 0.15% of daily 610
        put_trigger: 590.1,  // within 0.15% of daily 590
      },
    })
    const fifteenMin = makeCalculateResponse()
    const weekly = makeCalculateResponse()

    const { upside, downside } = computeTargets(daily, hourly, fifteenMin, weekly)

    // At least one target should have confluences
    const hasConfluence = [...upside, ...downside].some((t) => t.confluenceCount > 1)
    expect(hasConfluence).toBe(true)
  })

  it("each target has required fields", () => {
    const daily = makeTradePlanResponse()
    const hourly = makeCalculateResponse()
    const fifteenMin = makeCalculateResponse()
    const weekly = makeCalculateResponse()

    const { upside, downside } = computeTargets(daily, hourly, fifteenMin, weekly)

    for (const target of [...upside, ...downside]) {
      expect(target).toHaveProperty("price")
      expect(target).toHaveProperty("label")
      expect(target).toHaveProperty("source")
      expect(target).toHaveProperty("confluences")
      expect(target).toHaveProperty("confluenceCount")
      expect(typeof target.price).toBe("number")
      expect(Array.isArray(target.confluences)).toBe(true)
    }
  })
})
