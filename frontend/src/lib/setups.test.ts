// ---------------------------------------------------------------------------
// Setup Detection Engine — comprehensive tests using real API data snapshots
// for NVDA, AAPL, TSLA, SPY, META (fetched 2026-02-22, 1D bullish).
// ---------------------------------------------------------------------------

import { describe, it, expect } from "vitest"
import { detectSetups, type DetectedSetup, type SetupId } from "./setups"
import type { TradePlanResponse } from "./types"

// --- Test helpers ---

function findSetup(setups: DetectedSetup[], id: SetupId): DetectedSetup | undefined {
  return setups.find((s) => s.id === id)
}

function setupIds(setups: DetectedSetup[]): SetupId[] {
  return setups.map((s) => s.id)
}

// --- Shared fixture builder ---

function makeTradePlan(overrides: Record<string, unknown> = {}): TradePlanResponse {
  const base: TradePlanResponse = {
    ticker: "TEST",
    timeframe: "1d",
    trading_mode: "swing",
    use_current_close: true,
    direction: "bullish",
    bars: 251,
    atr_source_bars: 251,
    atr_levels: {
      atr: 10,
      pdc: 100,
      current_price: 100,
      levels: {
        golden_gate_bull: { price: 103.82, pct: "+38.2%", fib: 0.382 },
        golden_gate_bear: { price: 96.18, pct: "-38.2%", fib: 0.382 },
        mid_range_bull: { price: 106.18, pct: "+61.8%", fib: 0.618 },
        mid_range_bear: { price: 93.82, pct: "-61.8%", fib: 0.618 },
        full_range_bull: { price: 110, pct: "+100%", fib: 1.0 },
        full_range_bear: { price: 90, pct: "-100%", fib: 1.0 },
      },
      call_trigger: 102.36,
      put_trigger: 97.64,
      trigger_box: { low: 97.64, high: 102.36, inside: true },
      price_position: "inside_trigger_box",
      daily_range: 5,
      period_range: 5,
      atr_covered_pct: 50,
      atr_status: "green",
      atr_room_ok: true,
      chopzilla: false,
      trend: "bullish",
      trading_mode: "swing",
      trading_mode_label: "Swing",
    },
    pivot_ribbon: {
      ema8: 101,
      ema13: 100.5,
      ema21: 100,
      ema48: 98,
      ema200: 90,
      ribbon_state: "bullish",
      bias_candle: "blue",
      bias_signal: "buy_pullback",
      conviction_arrow: null,
      last_conviction_type: "bullish_crossover",
      last_conviction_bars_ago: 5,
      spread: 3,
      above_48ema: true,
      above_200ema: true,
      in_compression: false,
      chopzilla: false,
    },
    phase_oscillator: {
      oscillator: 25,
      oscillator_prev: 20,
      phase: "green",
      in_compression: false,
      current_zone: "above_zero",
      zone_crosses: {
        leaving_accumulation: false,
        leaving_extreme_down: false,
        leaving_distribution: false,
        leaving_extreme_up: false,
      },
      last_mr_type: null,
      last_mr_bars_ago: null,
      zones: { extreme: { up: 100, down: -100 }, distribution: { up: 61.8, down: -61.8 }, neutral: { up: 23.6, down: -23.6 }, zero: 0 },
    },
    price_structure: {
      pdc: 100,
      pdh: 102,
      pdl: 98,
      current_price: 100,
      pmh: null,
      pml: null,
      structural_bias: "neutral",
      gap_scenario: "no_gap",
      price_above_pdh: false,
      price_above_pmh: false,
      price_below_pdl: false,
      price_below_pml: false,
    },
    green_flag: {
      direction: "bullish",
      score: 5,
      max_score: 10,
      grade: "A+",
      recommendation: "Great setup. Full size.",
      flags: {},
      verbal_audit: "",
    },
  }
  return deepMerge(base, overrides) as TradePlanResponse
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deepMerge(target: any, source: any): any {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key]) &&
      target[key] &&
      typeof target[key] === "object"
    ) {
      result[key] = deepMerge(target[key], source[key])
    } else {
      result[key] = source[key]
    }
  }
  return result
}

// ========================================================================
// Real ticker fixtures (from API 2026-02-22, 1D bullish)
// ========================================================================

const NVDA = makeTradePlan({
  ticker: "NVDA",
  atr_levels: {
    atr: 23.704, pdc: 189.82, current_price: 189.82,
    levels: {
      golden_gate_bull: { price: 198.87, pct: "+38.2%", fib: 0.382 },
      golden_gate_bear: { price: 180.77, pct: "-38.2%", fib: 0.382 },
      mid_range_bull: { price: 204.47, pct: "+61.8%", fib: 0.618 },
      mid_range_bear: { price: 175.17, pct: "-61.8%", fib: 0.618 },
      full_range_bull: { price: 213.52, pct: "+100%", fib: 1.0 },
      full_range_bear: { price: 166.12, pct: "-100%", fib: 1.0 },
    },
    call_trigger: 195.41, put_trigger: 184.23,
    trigger_box: { low: 184.23, high: 195.41, inside: true },
    price_position: "inside_trigger_box",
    atr_covered_pct: 95.5, atr_status: "red", atr_room_ok: false, chopzilla: true,
    trend: "bullish",
  },
  pivot_ribbon: {
    ema8: 187.14, ema13: 186.55, ema21: 186.11, ema48: 185.43, ema200: 172.78,
    ribbon_state: "bullish", bias_candle: "gray", bias_signal: "compression",
    conviction_arrow: null, last_conviction_type: "bullish_crossover", last_conviction_bars_ago: 7,
    spread: 1.71, above_48ema: true, above_200ema: true,
    in_compression: true, chopzilla: false,
  },
  phase_oscillator: {
    oscillator: 14.58, oscillator_prev: 8.74, phase: "compression",
    in_compression: true, current_zone: "above_zero",
    zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
    last_mr_type: "leaving_distribution", last_mr_bars_ago: 73,
  },
  green_flag: { direction: "bullish", score: 4, max_score: 10, grade: "A" },
  mtf_phases: {
    "1w": {
      oscillator: 13.02, oscillator_prev: 8.21, phase: "compression",
      in_compression: true, current_zone: "above_zero",
      zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
      last_mr_type: "leaving_distribution", last_mr_bars_ago: 15,
    },
  },
})

const AAPL = makeTradePlan({
  ticker: "AAPL",
  atr_levels: {
    atr: 24.55, pdc: 264.58, current_price: 264.58,
    levels: {
      golden_gate_bull: { price: 273.96, pct: "+38.2%", fib: 0.382 },
      golden_gate_bear: { price: 255.20, pct: "-38.2%", fib: 0.382 },
      mid_range_bull: { price: 279.75, pct: "+61.8%", fib: 0.618 },
      mid_range_bear: { price: 249.41, pct: "-61.8%", fib: 0.618 },
      full_range_bull: { price: 289.13, pct: "+100%", fib: 1.0 },
      full_range_bear: { price: 240.03, pct: "-100%", fib: 1.0 },
    },
    call_trigger: 270.37, put_trigger: 258.79,
    trigger_box: { low: 258.79, high: 270.37, inside: true },
    price_position: "inside_trigger_box",
    atr_covered_pct: 103.7, atr_status: "red", atr_room_ok: false, chopzilla: true,
    trend: "bearish",
  },
  pivot_ribbon: {
    ema8: 264.59, ema13: 265.01, ema21: 264.87, ema48: 264.87, ema200: 250.67,
    ribbon_state: "chopzilla", bias_candle: "orange", bias_signal: "short_pullback",
    conviction_arrow: null, last_conviction_type: "bullish_crossover", last_conviction_bars_ago: 10,
    spread: -0.28, above_48ema: false, above_200ema: true,
    in_compression: false, chopzilla: true,
  },
  phase_oscillator: {
    oscillator: -8.53, oscillator_prev: -15.58, phase: "red",
    in_compression: false, current_zone: "below_zero",
    zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
    last_mr_type: "leaving_distribution", last_mr_bars_ago: 8,
  },
  green_flag: { direction: "bullish", score: 1, max_score: 10, grade: "skip" },
})

const TSLA = makeTradePlan({
  ticker: "TSLA",
  atr_levels: {
    atr: 71.80, pdc: 411.82, current_price: 411.82,
    levels: {
      golden_gate_bull: { price: 439.25, pct: "+38.2%", fib: 0.382 },
      golden_gate_bear: { price: 384.39, pct: "-38.2%", fib: 0.382 },
      mid_range_bull: { price: 456.19, pct: "+61.8%", fib: 0.618 },
      mid_range_bear: { price: 367.45, pct: "-61.8%", fib: 0.618 },
      full_range_bull: { price: 483.62, pct: "+100%", fib: 1.0 },
      full_range_bear: { price: 340.02, pct: "-100%", fib: 1.0 },
    },
    call_trigger: 428.76, put_trigger: 394.88,
    trigger_box: { low: 394.88, high: 428.76, inside: true },
    price_position: "inside_trigger_box",
    atr_covered_pct: 68.0, atr_status: "green", atr_room_ok: true, chopzilla: true,
    trend: "bearish",
  },
  pivot_ribbon: {
    ema8: 414.31, ema13: 416.69, ema21: 420.92, ema48: 429.08, ema200: 397.71,
    ribbon_state: "bearish", bias_candle: "gray", bias_signal: "compression",
    conviction_arrow: null, last_conviction_type: "bearish_crossover", last_conviction_bars_ago: 22,
    spread: -14.78, above_48ema: false, above_200ema: true,
    in_compression: true, chopzilla: false,
  },
  phase_oscillator: {
    oscillator: -21.58, oscillator_prev: -22.61, phase: "compression",
    in_compression: true, current_zone: "below_zero",
    zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
    last_mr_type: "leaving_distribution", last_mr_bars_ago: 43,
  },
  green_flag: { direction: "bullish", score: 3, max_score: 10, grade: "B" },
  mtf_phases: {
    "1w": {
      oscillator: -5.91, oscillator_prev: -2.03, phase: "compression",
      in_compression: true, current_zone: "below_zero",
      zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
      last_mr_type: "leaving_distribution", last_mr_bars_ago: 15,
    },
  },
})

const SPY = makeTradePlan({
  ticker: "SPY",
  atr_levels: {
    atr: 31.91, pdc: 689.43, current_price: 689.43,
    levels: {
      golden_gate_bull: { price: 701.62, pct: "+38.2%", fib: 0.382 },
      golden_gate_bear: { price: 677.24, pct: "-38.2%", fib: 0.382 },
      mid_range_bull: { price: 709.15, pct: "+61.8%", fib: 0.618 },
      mid_range_bear: { price: 669.71, pct: "-61.8%", fib: 0.618 },
      full_range_bull: { price: 721.34, pct: "+100%", fib: 1.0 },
      full_range_bear: { price: 657.52, pct: "-100%", fib: 1.0 },
    },
    call_trigger: 696.96, put_trigger: 681.90,
    trigger_box: { low: 681.90, high: 696.96, inside: true },
    price_position: "inside_trigger_box",
    atr_covered_pct: 66.9, atr_status: "green", atr_room_ok: true, chopzilla: true,
    trend: "neutral",
  },
  pivot_ribbon: {
    ema8: 686.59, ema13: 687.16, ema21: 687.63, ema48: 685.57, ema200: 654.10,
    ribbon_state: "chopzilla", bias_candle: "gray", bias_signal: "compression",
    conviction_arrow: null, last_conviction_type: "bullish_crossover", last_conviction_bars_ago: 195,
    spread: 1.02, above_48ema: true, above_200ema: true,
    in_compression: true, chopzilla: true,
  },
  phase_oscillator: {
    oscillator: -2.55, oscillator_prev: -12.64, phase: "compression",
    in_compression: true, current_zone: "below_zero",
    zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
    last_mr_type: "leaving_distribution", last_mr_bars_ago: 76,
  },
  green_flag: { direction: "bullish", score: 4, max_score: 10, grade: "A" },
  mtf_phases: {
    "1w": {
      oscillator: 29.31, oscillator_prev: 29.03, phase: "compression",
      in_compression: true, current_zone: "neutral_up",
      zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
      last_mr_type: "leaving_distribution", last_mr_bars_ago: 14,
    },
  },
})

const META = makeTradePlan({
  ticker: "META",
  atr_levels: {
    atr: 84.73, pdc: 655.66, current_price: 655.66,
    levels: {
      golden_gate_bull: { price: 688.03, pct: "+38.2%", fib: 0.382 },
      golden_gate_bear: { price: 623.29, pct: "-38.2%", fib: 0.382 },
      mid_range_bull: { price: 708.02, pct: "+61.8%", fib: 0.618 },
      mid_range_bear: { price: 603.30, pct: "-61.8%", fib: 0.618 },
      full_range_bull: { price: 740.39, pct: "+100%", fib: 1.0 },
      full_range_bear: { price: 570.93, pct: "-100%", fib: 1.0 },
    },
    call_trigger: 675.66, put_trigger: 635.66,
    trigger_box: { low: 635.66, high: 675.66, inside: true },
    price_position: "inside_trigger_box",
    atr_covered_pct: 109.9, atr_status: "red", atr_room_ok: false, chopzilla: true,
    trend: "neutral",
  },
  pivot_ribbon: {
    ema8: 652.80, ema13: 656.74, ema21: 658.78, ema48: 659.51, ema200: 673.31,
    ribbon_state: "bearish", bias_candle: "orange", bias_signal: "short_pullback",
    conviction_arrow: null, last_conviction_type: "bearish_crossover", last_conviction_bars_ago: 2,
    spread: -6.71, above_48ema: false, above_200ema: false,
    in_compression: false, chopzilla: false,
  },
  phase_oscillator: {
    oscillator: -15.48, oscillator_prev: -25.95, phase: "red",
    in_compression: false, current_zone: "below_zero",
    zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
    last_mr_type: "leaving_distribution", last_mr_bars_ago: 12,
  },
  green_flag: { direction: "bullish", score: 0, max_score: 10, grade: "skip" },
})

// ========================================================================
// Tests
// ========================================================================

describe("detectSetups", () => {
  // --- NVDA: bullish ribbon, gray candle, compression ---
  describe("NVDA — bullish ribbon, gray candle, double compression", () => {
    const setups = detectSetups(NVDA)

    it("should NOT detect Trend Continuation (gray candle, no ATR room, phase compression)", () => {
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })

    it("should detect Squeeze (both phase and ribbon compressed)", () => {
      const sq = findSetup(setups, "squeeze")
      expect(sq).toBeDefined()
      expect(sq!.direction).toBe("bullish")
    })

    it("should NOT detect iVomy (ribbon is bullish, not chopzilla)", () => {
      expect(findSetup(setups, "ivomy")).toBeUndefined()
    })

    it("should NOT detect Vomy (ribbon is bullish, not bearish/chopzilla)", () => {
      expect(findSetup(setups, "vomy")).toBeUndefined()
    })

    it("should NOT detect Golden Gate (price inside trigger box)", () => {
      expect(findSetup(setups, "golden_gate")).toBeUndefined()
    })

    it("should NOT detect Divergence (mr_bars_ago=73, way too old)", () => {
      expect(findSetup(setups, "divergence_extreme")).toBeUndefined()
    })

    it("should NOT detect Dip Connoisseur (price not below mid-range)", () => {
      expect(findSetup(setups, "dip_connoisseur")).toBeUndefined()
    })

    it("squeeze entry price should be near current price ($189.82)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.entryPrice).toBeCloseTo(189.82, 0)
    })

    it("squeeze target should be golden gate bull ($198.87)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.targetPrice).toBeCloseTo(198.87, 0)
    })
  })

  // --- AAPL: chopzilla, orange candle, below 48 EMA ---
  describe("AAPL — chopzilla ribbon, orange candle, red phase", () => {
    const setups = detectSetups(AAPL)

    it("should detect Vomy (chopzilla + below 48 EMA + orange candle)", () => {
      const v = findSetup(setups, "vomy")
      expect(v).toBeDefined()
      expect(v!.direction).toBe("bearish")
    })

    it("should NOT detect iVomy (below 48 EMA → fails required)", () => {
      expect(findSetup(setups, "ivomy")).toBeUndefined()
    })

    it("should NOT detect Trend Continuation (ribbon is chopzilla, not bullish/bearish)", () => {
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })

    it("should NOT detect Squeeze (no compression)", () => {
      expect(findSetup(setups, "squeeze")).toBeUndefined()
    })

    it("vomy entry should reference EMA 13 near $265", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.entryPrice).toBeCloseTo(265.01, 0)
    })

    it("vomy stop should reference EMA 21 near $264.87", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.stopPrice).toBeCloseTo(264.87, 0)
    })

    it("vomy target should be mid-range bear near $249.41", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.targetPrice).toBeCloseTo(249.41, 0)
    })

    it("vomy should have strong confidence (red phase meets 50%+ optional threshold)", () => {
      const v = findSetup(setups, "vomy")!
      // last_conviction_type is bullish_crossover (not bearish) → optional not met
      // phase is red → 1 of 2 optional met = 50% → meets ceil(2*0.5)=1 threshold → strong
      expect(v.confidence).toBe("strong")
    })
  })

  // --- TSLA: bearish ribbon, gray candle, double compression ---
  describe("TSLA — bearish ribbon, gray candle, double compression", () => {
    const setups = detectSetups(TSLA)

    it("should detect Squeeze (both phase and ribbon compressed)", () => {
      const sq = findSetup(setups, "squeeze")
      expect(sq).toBeDefined()
    })

    it("squeeze direction should be bearish (below 48 EMA)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.direction).toBe("bearish")
    })

    it("should NOT detect Vomy (gray candle, not orange)", () => {
      expect(findSetup(setups, "vomy")).toBeUndefined()
    })

    it("should NOT detect Trend Continuation (ribbon bearish but no orange candle or red phase)", () => {
      // Bearish trend cont needs orange candle + red phase, but bias is gray and phase is compression
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })

    it("should NOT detect iVomy (ribbon bearish, not chopzilla; below 48 EMA)", () => {
      expect(findSetup(setups, "ivomy")).toBeUndefined()
    })

    it("squeeze target should be golden gate bear near $384.39", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.targetPrice).toBeCloseTo(384.39, 0)
    })

    it("squeeze entry should be near current price ($411.82)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.entryPrice).toBeCloseTo(411.82, 0)
    })
  })

  // --- SPY: chopzilla ribbon, gray, double compression ---
  describe("SPY — chopzilla ribbon, double compression", () => {
    const setups = detectSetups(SPY)

    it("should detect Squeeze (phase + ribbon both compressed)", () => {
      const sq = findSetup(setups, "squeeze")
      expect(sq).toBeDefined()
    })

    it("squeeze direction should be bullish (above 48 EMA)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.direction).toBe("bullish")
    })

    it("should NOT detect Trend Continuation (ribbon is chopzilla)", () => {
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })

    it("should NOT detect Vomy (gray candle, not orange)", () => {
      expect(findSetup(setups, "vomy")).toBeUndefined()
    })

    it("should NOT detect iVomy (gray candle, not blue)", () => {
      expect(findSetup(setups, "ivomy")).toBeUndefined()
    })

    it("squeeze target should be golden gate bull near $701.62", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.targetPrice).toBeCloseTo(701.62, 0)
    })

    it("squeeze stop should be near EMA 21 ($687.63)", () => {
      const sq = findSetup(setups, "squeeze")!
      expect(sq.stopPrice).toBeCloseTo(687.63, 0)
    })
  })

  // --- META: bearish ribbon, orange candle, red phase ---
  describe("META — bearish ribbon, orange candle, red phase", () => {
    const setups = detectSetups(META)

    it("should detect Vomy (bearish ribbon + below 48 EMA + orange candle)", () => {
      const v = findSetup(setups, "vomy")
      expect(v).toBeDefined()
      expect(v!.direction).toBe("bearish")
    })

    it("vomy should have strong confidence (recent crossover + red phase)", () => {
      const v = findSetup(setups, "vomy")!
      // bearish_crossover 2 bars ago → met, phase red → met → 2/2 optional → strong
      expect(v.confidence).toBe("strong")
    })

    it("should NOT detect Trend Continuation (ribbon bearish, but no atr_room and atr chopzilla)", () => {
      // Bearish trend cont needs orange candle (✓), red phase (✓), ATR room (✗) — fails required
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })

    it("should NOT detect iVomy (ribbon bearish, not chopzilla; below 48 EMA)", () => {
      expect(findSetup(setups, "ivomy")).toBeUndefined()
    })

    it("should NOT detect Squeeze (no compression)", () => {
      expect(findSetup(setups, "squeeze")).toBeUndefined()
    })

    it("vomy entry (EMA 13) should be near $656.74", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.entryPrice).toBeCloseTo(656.74, 0)
    })

    it("vomy target (mid-range bear) should be near $603.30", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.targetPrice).toBeCloseTo(603.30, 0)
    })

    it("vomy stop (EMA 21) should be near $658.78", () => {
      const v = findSetup(setups, "vomy")!
      expect(v.stopPrice).toBeCloseTo(658.78, 0)
    })
  })

  // --- Price sanity checks ---
  describe("price sanity — entry/target/stop must be reasonable vs current_price", () => {
    const allFixtures = [
      { name: "NVDA", data: NVDA },
      { name: "AAPL", data: AAPL },
      { name: "TSLA", data: TSLA },
      { name: "SPY", data: SPY },
      { name: "META", data: META },
    ]

    for (const { name, data } of allFixtures) {
      it(`${name}: all setup prices within 50% of current price`, () => {
        const setups = detectSetups(data)
        const price = data.atr_levels.current_price

        for (const s of setups) {
          if (s.entryPrice != null) {
            expect(s.entryPrice).toBeGreaterThan(price * 0.5)
            expect(s.entryPrice).toBeLessThan(price * 1.5)
          }
          if (s.targetPrice != null) {
            expect(s.targetPrice).toBeGreaterThan(price * 0.5)
            expect(s.targetPrice).toBeLessThan(price * 1.5)
          }
          if (s.stopPrice != null) {
            expect(s.stopPrice).toBeGreaterThan(price * 0.5)
            expect(s.stopPrice).toBeLessThan(price * 1.5)
          }
        }
      })
    }
  })

  // --- Confidence calculation ---
  describe("confidence calculation", () => {
    it("all required met + all optional met → strong", () => {
      const ideal = makeTradePlan({
        pivot_ribbon: {
          ribbon_state: "bullish", bias_candle: "blue", above_48ema: true, above_200ema: true,
          in_compression: false, chopzilla: false,
        },
        phase_oscillator: { phase: "green", in_compression: false },
        atr_levels: { atr_room_ok: true, chopzilla: false },
      })
      const setups = detectSetups(ideal)
      const tc = findSetup(setups, "trend_continuation")
      expect(tc).toBeDefined()
      expect(tc!.confidence).toBe("strong")
    })

    it("all required met + 0 optional → moderate", () => {
      const partial = makeTradePlan({
        pivot_ribbon: {
          ribbon_state: "bullish", bias_candle: "blue", above_48ema: false, above_200ema: false,
          in_compression: false, chopzilla: false,
        },
        phase_oscillator: { phase: "green", in_compression: false },
        atr_levels: { atr_room_ok: true, chopzilla: true },
      })
      const setups = detectSetups(partial)
      const tc = findSetup(setups, "trend_continuation")
      expect(tc).toBeDefined()
      expect(tc!.confidence).toBe("moderate")
    })

    it("missing required → no setup returned", () => {
      const bad = makeTradePlan({
        pivot_ribbon: {
          ribbon_state: "bullish", bias_candle: "gray", // no pullback
          in_compression: false, chopzilla: false,
        },
        phase_oscillator: { phase: "compression", in_compression: false }, // not firing
        atr_levels: { atr_room_ok: false, chopzilla: false }, // no room
      })
      const setups = detectSetups(bad)
      expect(findSetup(setups, "trend_continuation")).toBeUndefined()
    })
  })

  // --- Mutual exclusivity ---
  describe("mutual exclusivity", () => {
    it("Trend Continuation and iVomy should not both fire", () => {
      // Trend Cont needs bullish ribbon; iVomy needs chopzilla ribbon — can't both be true
      const bullish = makeTradePlan({
        pivot_ribbon: {
          ribbon_state: "bullish", bias_candle: "blue", above_48ema: true,
          in_compression: false, chopzilla: false,
        },
        phase_oscillator: { phase: "green", in_compression: false },
        atr_levels: { atr_room_ok: true, chopzilla: false },
      })
      const setups = detectSetups(bullish)
      const hasTc = findSetup(setups, "trend_continuation") != null
      const hasIvomy = findSetup(setups, "ivomy") != null
      expect(hasTc && hasIvomy).toBe(false)
    })

    it("Vomy and iVomy should not both fire", () => {
      // Vomy needs bearish/chopzilla + below 48; iVomy needs chopzilla + above 48
      for (const fixture of [NVDA, AAPL, TSLA, SPY, META]) {
        const setups = detectSetups(fixture)
        const hasVomy = findSetup(setups, "vomy") != null
        const hasIvomy = findSetup(setups, "ivomy") != null
        expect(hasVomy && hasIvomy).toBe(false)
      }
    })
  })

  // --- Edge cases ---
  describe("edge cases", () => {
    it("empty levels should not crash", () => {
      const noLevels = makeTradePlan({
        atr_levels: { levels: {} },
        pivot_ribbon: { ribbon_state: "bullish", bias_candle: "blue" },
        phase_oscillator: { phase: "green" },
      })
      expect(() => detectSetups(noLevels)).not.toThrow()
    })

    it("null MTF data should not crash squeeze detector", () => {
      const noMtf = makeTradePlan({
        pivot_ribbon: { in_compression: true },
        phase_oscillator: { in_compression: true },
      })
      // @ts-expect-error - testing null MTF
      noMtf.mtf_phases = undefined
      expect(() => detectSetups(noMtf)).not.toThrow()
    })

    it("should return setups sorted by confidence (strong first)", () => {
      // Create a scenario with both a strong and moderate setup
      const dual = makeTradePlan({
        pivot_ribbon: {
          ribbon_state: "bullish", bias_candle: "blue", above_48ema: true, above_200ema: true,
          in_compression: true, chopzilla: false,
        },
        phase_oscillator: { phase: "green", in_compression: true },
        atr_levels: { atr_room_ok: true, chopzilla: false },
      })
      const setups = detectSetups(dual)
      if (setups.length >= 2) {
        const order = { strong: 0, moderate: 1, forming: 2 }
        for (let i = 0; i < setups.length - 1; i++) {
          expect(order[setups[i].confidence]).toBeLessThanOrEqual(order[setups[i + 1].confidence])
        }
      }
    })
  })

  // --- Specific setup: Squeeze with nested ---
  describe("Squeeze — nested MTF squeeze detection", () => {
    it("should flag nested squeeze when all MTF phases are compressed", () => {
      const nested = makeTradePlan({
        pivot_ribbon: { ribbon_state: "bullish", in_compression: true, above_48ema: true, chopzilla: false },
        phase_oscillator: { phase: "compression", in_compression: true },
        atr_levels: { chopzilla: false },
        mtf_phases: {
          "1w": {
            oscillator: 5, oscillator_prev: 4, phase: "compression",
            in_compression: true, current_zone: "above_zero",
            zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
            last_mr_type: null, last_mr_bars_ago: null,
          },
        },
      })
      const sq = findSetup(detectSetups(nested), "squeeze")!
      expect(sq).toBeDefined()
      const nestedCond = sq.conditions.find((c) => c.label.includes("Nested"))
      expect(nestedCond?.met).toBe(true)
    })

    it("should NOT flag nested squeeze when MTF is not compressed", () => {
      const notNested = makeTradePlan({
        pivot_ribbon: { ribbon_state: "bullish", in_compression: true, above_48ema: true, chopzilla: false },
        phase_oscillator: { phase: "compression", in_compression: true },
        atr_levels: { chopzilla: false },
        mtf_phases: {
          "1w": {
            oscillator: 30, oscillator_prev: 28, phase: "green",
            in_compression: false, current_zone: "neutral_up",
            zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
            last_mr_type: null, last_mr_bars_ago: null,
          },
        },
      })
      const sq = findSetup(detectSetups(notNested), "squeeze")!
      expect(sq).toBeDefined()
      const nestedCond = sq.conditions.find((c) => c.label.includes("Nested"))
      expect(nestedCond?.met).toBe(false)
    })
  })

  // --- Divergence Extreme ---
  describe("Divergence Extreme", () => {
    it("should detect when in extreme zone with recent mean reversion", () => {
      const divergence = makeTradePlan({
        phase_oscillator: {
          oscillator: -80, oscillator_prev: -85, phase: "red",
          in_compression: false, current_zone: "extreme_down",
          last_mr_type: "leaving_extreme_down", last_mr_bars_ago: 2,
          zone_crosses: { leaving_accumulation: false, leaving_extreme_down: true, leaving_distribution: false, leaving_extreme_up: false },
        },
        pivot_ribbon: { ribbon_state: "bearish", in_compression: false },
      })
      const d = findSetup(detectSetups(divergence), "divergence_extreme")
      expect(d).toBeDefined()
      expect(d!.direction).toBe("bullish") // extreme_down → bullish reversal
    })

    it("should NOT detect when mean reversion is too old (>5 bars)", () => {
      const old = makeTradePlan({
        phase_oscillator: {
          oscillator: -60, oscillator_prev: -65, phase: "red",
          in_compression: false, current_zone: "accumulation",
          last_mr_type: "leaving_accumulation", last_mr_bars_ago: 10, // too old
        },
      })
      expect(findSetup(detectSetups(old), "divergence_extreme")).toBeUndefined()
    })

    it("should NOT detect when zone is neutral (not extreme)", () => {
      const neutral = makeTradePlan({
        phase_oscillator: {
          oscillator: 5, oscillator_prev: 3, phase: "green",
          in_compression: false, current_zone: "above_zero",
          last_mr_type: "leaving_distribution", last_mr_bars_ago: 2,
        },
      })
      expect(findSetup(detectSetups(neutral), "divergence_extreme")).toBeUndefined()
    })
  })

  // --- Dip Connoisseur ---
  describe("Dip Connoisseur", () => {
    it("should detect when price below mid-range AND leaving accumulation", () => {
      const dip = makeTradePlan({
        atr_levels: {
          price_position: "below_mid_range", current_price: 92,
          levels: {
            golden_gate_bull: { price: 103.82, pct: "+38.2%", fib: 0.382 },
            mid_range_bull: { price: 106.18, pct: "+61.8%", fib: 0.618 },
            full_range_bear: { price: 90, pct: "-100%", fib: 1.0 },
          },
        },
        phase_oscillator: {
          oscillator: -50, oscillator_prev: -55,
          current_zone: "accumulation",
          zone_crosses: { leaving_accumulation: true, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
        },
      })
      const dc = findSetup(detectSetups(dip), "dip_connoisseur")
      expect(dc).toBeDefined()
      expect(dc!.direction).toBe("bullish")
    })

    it("should NOT detect when price is below mid-range but NOT leaving accumulation", () => {
      const noDip = makeTradePlan({
        atr_levels: { price_position: "below_mid_range" },
        phase_oscillator: {
          zone_crosses: { leaving_accumulation: false, leaving_extreme_down: false, leaving_distribution: false, leaving_extreme_up: false },
        },
      })
      expect(findSetup(detectSetups(noDip), "dip_connoisseur")).toBeUndefined()
    })

    it("should NOT detect when price is inside trigger box", () => {
      const inside = makeTradePlan({
        atr_levels: { price_position: "inside_trigger_box" },
      })
      expect(findSetup(detectSetups(inside), "dip_connoisseur")).toBeUndefined()
    })
  })

  // --- Count checks for real data ---
  describe("real data — total setup counts", () => {
    it("NVDA should have exactly 1 setup (squeeze only)", () => {
      expect(detectSetups(NVDA)).toHaveLength(1)
      expect(setupIds(detectSetups(NVDA))).toEqual(["squeeze"])
    })

    it("AAPL should have exactly 1 setup (vomy only)", () => {
      expect(detectSetups(AAPL)).toHaveLength(1)
      expect(setupIds(detectSetups(AAPL))).toEqual(["vomy"])
    })

    it("TSLA should have exactly 1 setup (squeeze only)", () => {
      expect(detectSetups(TSLA)).toHaveLength(1)
      expect(setupIds(detectSetups(TSLA))).toEqual(["squeeze"])
    })

    it("SPY should have exactly 1 setup (squeeze only)", () => {
      expect(detectSetups(SPY)).toHaveLength(1)
      expect(setupIds(detectSetups(SPY))).toEqual(["squeeze"])
    })

    it("META should have exactly 1 setup (vomy only)", () => {
      expect(detectSetups(META)).toHaveLength(1)
      expect(setupIds(detectSetups(META))).toEqual(["vomy"])
    })
  })
})
