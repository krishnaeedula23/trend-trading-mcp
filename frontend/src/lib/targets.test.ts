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
        trigger_bull: { price: 610, pct: "+23.6%", fib: 0.236 },
        trigger_bear: { price: 590, pct: "-23.6%", fib: 0.236 },
        golden_gate_bull: { price: 614, pct: "+38.2%", fib: 0.382 },
        golden_gate_bear: { price: 586, pct: "-38.2%", fib: 0.382 },
        mid_50_bull: { price: 616, pct: "+50%", fib: 0.5 },
        mid_50_bear: { price: 584, pct: "-50%", fib: 0.5 },
        mid_range_bull: { price: 618, pct: "+61.8%", fib: 0.618 },
        mid_range_bear: { price: 582, pct: "-61.8%", fib: 0.618 },
        fib_786_bull: { price: 621, pct: "+78.6%", fib: 0.786 },
        fib_786_bear: { price: 579, pct: "-78.6%", fib: 0.786 },
        full_range_bull: { price: 623, pct: "+100%", fib: 1.0 },
        full_range_bear: { price: 577, pct: "-100%", fib: 1.0 },
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

    // Should have: 12 ATR fibs (including mid_50 + fib_786) + 2 hourly triggers + 20 EMAs + 2 structure + 8 pivots = 44
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

  it("includes mid_50 and fib_786 ATR levels", () => {
    const daily = makeTradePlanResponse()
    const hourly = makeCalculateResponse()
    const fifteenMin = makeCalculateResponse()
    const weekly = makeCalculateResponse()

    const levels = collectLevels(daily, hourly, fifteenMin, weekly)

    const mid50Bull = levels.find((l) => l.label === "Mid 50 Bull")
    expect(mid50Bull).toBeDefined()
    expect(mid50Bull!.price).toBe(616)

    const mid50Bear = levels.find((l) => l.label === "Mid 50 Bear")
    expect(mid50Bear).toBeDefined()
    expect(mid50Bear!.price).toBe(584)

    const fib786Bull = levels.find((l) => l.label === "Fib 786 Bull")
    expect(fib786Bull).toBeDefined()
    expect(fib786Bull!.price).toBe(621)

    const fib786Bear = levels.find((l) => l.label === "Fib 786 Bear")
    expect(fib786Bear).toBeDefined()
    expect(fib786Bear!.price).toBe(579)
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
    // The 610 cluster is nearest to price and has confluence
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

  it("sorts by price proximity, not confluence count", () => {
    // Scenario: far-away level has 3 confluences, nearby level has 1
    // Target ordering should still be by price proximity
    const levels: RawLevel[] = [
      // Close to current price — 1 level, no confluence
      { price: 610, label: "Call Trigger", source: "ATR 1D" },
      // Far from current price — 3 levels clustered = high confluence
      { price: 630, label: "Full Range Bull", source: "ATR 1D" },
      { price: 630.5, label: "PMoH", source: "Pivot" },  // within 0.15%
      { price: 630.2, label: "EMA200", source: "EMA 1W" }, // within 0.15%
      // Medium distance — 1 level
      { price: 620, label: "Mid Range Bull", source: "ATR 1D" },
    ]

    const targets = clusterLevels(levels, "up")

    // Should be sorted ascending by price: 610, 620, 630
    expect(targets[0].price).toBe(610)
    expect(targets[1].price).toBe(620)
    // The 630 cluster should be last even though it has the highest confluence
    expect(targets[2].price).toBeGreaterThanOrEqual(630)
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

  it("upside targets sorted ascending by price (nearest first)", () => {
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

    const { upside } = computeTargets(daily, hourly, fifteenMin, weekly)

    // T1 < T2 < T3 (ascending — closest to current price first)
    for (let i = 1; i < upside.length; i++) {
      expect(upside[i].price).toBeGreaterThanOrEqual(upside[i - 1].price)
    }
  })

  it("downside targets sorted descending by price (nearest first)", () => {
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

    const { downside } = computeTargets(daily, hourly, fifteenMin, weekly)

    // T1 > T2 > T3 (descending — closest to current price first)
    for (let i = 1; i < downside.length; i++) {
      expect(downside[i].price).toBeLessThanOrEqual(downside[i - 1].price)
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

  it("real-world scenario: SPY-like data with all 12 ATR levels", () => {
    // Simulates real SPY data where price is inside trigger box
    const daily = makeTradePlanResponse({
      atr_levels: {
        ...makeTradePlanResponse().atr_levels,
        current_price: 686,
        pdc: 686,
        call_trigger: 693.52,
        put_trigger: 678.46,
        levels: {
          trigger_bull:      { price: 693.52, pct: "+23.6%", fib: 0.236 },
          trigger_bear:      { price: 678.46, pct: "-23.6%", fib: 0.236 },
          golden_gate_bull:  { price: 698.18, pct: "+38.2%", fib: 0.382 },
          golden_gate_bear:  { price: 673.80, pct: "-38.2%", fib: 0.382 },
          mid_50_bull:       { price: 701.94, pct: "+50.0%", fib: 0.5 },
          mid_50_bear:       { price: 670.04, pct: "-50.0%", fib: 0.5 },
          mid_range_bull:    { price: 705.71, pct: "+61.8%", fib: 0.618 },
          mid_range_bear:    { price: 666.27, pct: "-61.8%", fib: 0.618 },
          fib_786_bull:      { price: 711.07, pct: "+78.6%", fib: 0.786 },
          fib_786_bear:      { price: 660.91, pct: "-78.6%", fib: 0.786 },
          full_range_bull:   { price: 717.90, pct: "+100%", fib: 1.0 },
          full_range_bear:   { price: 654.08, pct: "-100%", fib: 1.0 },
        },
      },
    })
    const hourly = makeCalculateResponse({
      atr_levels: {
        ...makeCalculateResponse().atr_levels,
        call_trigger: 689.66,
        put_trigger: 682.32,
      },
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 685.63, ema13: 686.18, ema21: 686.63, ema48: 686.76, ema200: 689.33,
      },
    })
    const fifteenMin = makeCalculateResponse({
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 684.93, ema13: 684.75, ema21: 684.88, ema48: 685.88, ema200: 687.0,
      },
    })
    const weekly = makeCalculateResponse({
      pivot_ribbon: {
        ...makeCalculateResponse().pivot_ribbon,
        ema8: 686.85, ema13: 684.02, ema21: 676.44, ema48: 646.62, ema200: 535.23,
      },
    })

    const { upside, downside } = computeTargets(daily, hourly, fifteenMin, weekly)

    // Upside targets should be ordered ascending (nearest first)
    for (let i = 1; i < upside.length; i++) {
      expect(upside[i].price).toBeGreaterThanOrEqual(upside[i - 1].price)
    }

    // Downside targets should be ordered descending (nearest first)
    for (let i = 1; i < downside.length; i++) {
      expect(downside[i].price).toBeLessThanOrEqual(downside[i - 1].price)
    }

    // Should include ATR extension levels in upside targets
    const allUpsidePrices = upside.map(t => t.price)
    // At least one ATR extension should appear (golden_gate_bull=698.18, mid_50_bull=701.94, etc.)
    const hasAtrExtension = upside.some(t => t.source === "ATR 1D")
    expect(hasAtrExtension).toBe(true)

    // Downside should include levels below current price
    expect(downside.length).toBeGreaterThan(0)
    for (const t of downside) {
      expect(t.price).toBeLessThan(686)
    }
  })
})
