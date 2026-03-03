import { tool } from "ai"
import { z } from "zod"
import { railwayFetch } from "../railway"
import { createServerClient } from "../supabase/server"

export const tradingTools = {
  get_saty_indicators: tool({
    description:
      "Get Saty trading indicators (ATR levels, pivot ribbon, phase oscillator, green flag) for a ticker and timeframe. Use this to analyze a stock's current technical setup.",
    inputSchema: z.object({
      ticker: z.string().describe("Stock ticker symbol, e.g. AAPL"),
      timeframe: z
        .enum(["1h", "1d"])
        .default("1d")
        .describe("Timeframe for analysis"),
    }),
    execute: async ({ ticker, timeframe }) => {
      const res = await railwayFetch("/api/satyland/calculate", {
        ticker,
        timeframe,
      })
      return await res.json()
    },
  }),

  run_vomy_scan: tool({
    description:
      "Run the VOMY screener to find stocks with volume-momentum signals. Returns bullish/bearish/both hits across S&P 500 and NASDAQ 100.",
    inputSchema: z.object({
      timeframe: z
        .enum(["1h", "1d"])
        .default("1d")
        .describe("Scan timeframe"),
      signal_type: z
        .enum(["bullish", "bearish", "both"])
        .default("both")
        .describe("Signal direction"),
    }),
    execute: async ({ timeframe, signal_type }) => {
      const res = await railwayFetch("/api/screener/vomy-scan", {
        universes: ["sp500", "nasdaq100"],
        timeframe,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
      return await res.json()
    },
  }),

  run_golden_gate_scan: tool({
    description:
      "Run the Golden Gate screener to find stocks at golden gate entry levels. Supports day and multiday trading modes.",
    inputSchema: z.object({
      trading_mode: z
        .enum(["day", "multiday"])
        .default("day")
        .describe("Trading mode"),
      signal_type: z
        .enum(["golden_gate_up", "golden_gate_down", "golden_gate"])
        .default("golden_gate_up")
        .describe("Signal direction"),
    }),
    execute: async ({ trading_mode, signal_type }) => {
      const res = await railwayFetch("/api/screener/golden-gate-scan", {
        universes: ["sp500", "nasdaq100"],
        trading_mode,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
      return await res.json()
    },
  }),

  run_momentum_scan: tool({
    description:
      "Run the momentum screener to find stocks with strong momentum across all phases.",
    inputSchema: z.object({}),
    execute: async () => {
      const res = await railwayFetch("/api/screener/momentum-scan", {
        universes: ["sp500", "nasdaq100"],
        min_price: 4.0,
      })
      return await res.json()
    },
  }),

  get_trade_plan: tool({
    description:
      "Get today's daily trade plan with ATR levels, targets, and bias for key instruments (SPY, SPX, QQQ, NQ, ES).",
    inputSchema: z.object({}),
    execute: async () => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("daily_trade_plans")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(1)
        .single()
      return data
    },
  }),

  get_cached_scan: tool({
    description:
      "Get the latest pre-cached screener results from the premarket cron job. Faster than running a live scan.",
    inputSchema: z.object({
      scan_key: z
        .string()
        .describe(
          "Scan key, e.g. vomy:1d:both, golden_gate:day:golden_gate_up, momentum:default",
        ),
    }),
    execute: async ({ scan_key }) => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("cached_scans")
        .select("results, scanned_at")
        .eq("scan_key", scan_key)
        .single()
      return data
    },
  }),

  get_watchlists: tool({
    description: "Get the user's saved watchlists with ticker symbols.",
    inputSchema: z.object({}),
    execute: async () => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("watchlists")
        .select("*")
        .order("created_at", { ascending: false })
      return data ?? []
    },
  }),

  get_options_straddle: tool({
    description:
      "Get ATM straddle pricing and implied volatility for a ticker. Useful for gauging expected move.",
    inputSchema: z.object({
      ticker: z.string().describe("Stock ticker symbol"),
      strike_count: z
        .number()
        .default(10)
        .describe("Number of strikes around ATM"),
    }),
    execute: async ({ ticker, strike_count }) => {
      const res = await railwayFetch("/api/options/atm-straddle", {
        ticker,
        strike_count,
      })
      return await res.json()
    },
  }),
}
