// ---------------------------------------------------------------------------
// Premarket screener scan runner — called by the daily cron route.
// Runs each scan config against Railway, upserts results into cached_scans.
// ---------------------------------------------------------------------------

import { railwayFetch } from "./railway"
import { createServerClient } from "./supabase/server"

interface ScanConfig {
  scan_type: string
  scan_key: string
  path: string
  body: Record<string, unknown>
}

const SCAN_CONFIGS: ScanConfig[] = [
  {
    scan_type: "vomy",
    scan_key: "vomy:1h:both",
    path: "/api/screener/vomy-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      timeframe: "1h",
      signal_type: "both",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "vomy",
    scan_key: "vomy:1d:both",
    path: "/api/screener/vomy-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      timeframe: "1d",
      signal_type: "both",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "golden_gate",
    scan_key: "golden_gate:day:golden_gate_up",
    path: "/api/screener/golden-gate-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      trading_mode: "day",
      signal_type: "golden_gate_up",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "golden_gate",
    scan_key: "golden_gate:multiday:golden_gate_up",
    path: "/api/screener/golden-gate-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      trading_mode: "multiday",
      signal_type: "golden_gate_up",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "momentum",
    scan_key: "momentum:default",
    path: "/api/screener/momentum-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      min_price: 4.0,
    },
  },
]

export interface ScanResult {
  scan_key: string
  success: boolean
  total_hits?: number
  error?: string
  duration_ms: number
}

/**
 * Run all screener scans in parallel, upsert results to Supabase.
 * Returns a summary of each scan's outcome.
 */
export async function runAllScans(): Promise<ScanResult[]> {
  const supabase = createServerClient()

  const results = await Promise.all(
    SCAN_CONFIGS.map(async (config): Promise<ScanResult> => {
      const start = Date.now()
      try {
        const res = await railwayFetch(config.path, config.body)
        const data = await res.json()

        const { error } = await supabase.from("cached_scans").upsert(
          {
            scan_type: config.scan_type,
            scan_key: config.scan_key,
            results: data,
            scanned_at: new Date().toISOString(),
          },
          { onConflict: "scan_key" },
        )

        if (error) {
          return {
            scan_key: config.scan_key,
            success: false,
            error: `Supabase: ${error.message}`,
            duration_ms: Date.now() - start,
          }
        }
        return {
          scan_key: config.scan_key,
          success: true,
          total_hits: data.total_hits ?? data.hits?.length ?? 0,
          duration_ms: Date.now() - start,
        }
      } catch (err) {
        return {
          scan_key: config.scan_key,
          success: false,
          error: String(err),
          duration_ms: Date.now() - start,
        }
      }
    }),
  )

  return results
}
