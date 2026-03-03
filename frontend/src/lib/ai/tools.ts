import { tool } from "ai"
import { z } from "zod"
import { railwayFetch } from "../railway"
import { createServerClient } from "../supabase/server"

const satyTimeframe = z
  .enum(["1m", "5m", "15m", "1h", "4h", "1d", "1w"])
  .default("1d")
  .describe("Timeframe for analysis")

const screenerTimeframe = z
  .enum(["1h", "4h", "1d", "1w"])
  .default("1d")
  .describe("Scan timeframe")

async function safeRailwayFetch(
  path: string,
  body: Record<string, unknown>,
): Promise<unknown> {
  try {
    const res = await railwayFetch(path, body)
    return await res.json()
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error"
    return { error: true, message: `API request failed: ${message}` }
  }
}

export const tradingTools = {
  get_saty_indicators: tool({
    description:
      "Get Saty trading indicators (ATR levels, pivot ribbon, phase oscillator, green flag) for a ticker and timeframe. Use this to analyze a stock's current technical setup.",
    inputSchema: z.object({
      ticker: z.string().describe("Stock ticker symbol, e.g. AAPL"),
      timeframe: satyTimeframe,
    }),
    execute: async ({ ticker, timeframe }) => {
      return safeRailwayFetch("/api/satyland/calculate", { ticker, timeframe })
    },
  }),

  run_vomy_scan: tool({
    description:
      "Run the VOMY screener to find stocks with volume-momentum signals. Returns bullish/bearish/both hits across S&P 500 and NASDAQ 100.",
    inputSchema: z.object({
      timeframe: screenerTimeframe,
      signal_type: z
        .enum(["bullish", "bearish", "both"])
        .default("both")
        .describe("Signal direction"),
    }),
    execute: async ({ timeframe, signal_type }) => {
      return safeRailwayFetch("/api/screener/vomy-scan", {
        universes: ["sp500", "nasdaq100"],
        timeframe,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
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
      return safeRailwayFetch("/api/screener/golden-gate-scan", {
        universes: ["sp500", "nasdaq100"],
        trading_mode,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
    },
  }),

  run_momentum_scan: tool({
    description:
      "Run the momentum screener to find stocks with strong momentum across all phases.",
    inputSchema: z.object({}),
    execute: async () => {
      return safeRailwayFetch("/api/screener/momentum-scan", {
        universes: ["sp500", "nasdaq100"],
        min_price: 4.0,
      })
    },
  }),

  get_trade_plan: tool({
    description:
      "Get today's daily trade plan with ATR levels, targets, and bias for key instruments (SPY, SPX, QQQ, NQ, ES).",
    inputSchema: z.object({}),
    execute: async () => {
      try {
        const supabase = createServerClient()
        const { data, error } = await supabase
          .from("daily_trade_plans")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(1)
          .single()
        if (error || !data) {
          return { error: true, message: "No trade plan found for today." }
        }
        return data
      } catch (e) {
        const message = e instanceof Error ? e.message : "Unknown error"
        return { error: true, message: `Failed to fetch trade plan: ${message}` }
      }
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
      try {
        const supabase = createServerClient()
        const { data, error } = await supabase
          .from("cached_scans")
          .select("results, scanned_at")
          .eq("scan_key", scan_key)
          .single()
        if (error || !data) {
          return { error: true, message: `No cached scan found for key "${scan_key}".` }
        }
        return data
      } catch (e) {
        const message = e instanceof Error ? e.message : "Unknown error"
        return { error: true, message: `Failed to fetch cached scan: ${message}` }
      }
    },
  }),

  get_watchlists: tool({
    description: "Get the user's saved watchlists with ticker symbols.",
    inputSchema: z.object({}),
    execute: async () => {
      try {
        const supabase = createServerClient()
        const { data } = await supabase
          .from("watchlists")
          .select("*")
          .order("created_at", { ascending: false })
        return data ?? []
      } catch (e) {
        const message = e instanceof Error ? e.message : "Unknown error"
        return { error: true, message: `Failed to fetch watchlists: ${message}` }
      }
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
      return safeRailwayFetch("/api/options/atm-straddle", {
        ticker,
        strike_count,
      })
    },
  }),
}
