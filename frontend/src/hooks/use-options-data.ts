// ---------------------------------------------------------------------------
// useOptionsData — fetches ATM straddle (Schwab) + IV metrics (VIX) for
// SPY and SPX. Each fetch catches errors independently for graceful degradation.
// ---------------------------------------------------------------------------

import useSWR from "swr"
import type { AtmStraddle, IvMetrics } from "@/lib/types"

export interface InstrumentOptionsData {
  straddle: AtmStraddle | null
  iv: IvMetrics | null
}

export interface OptionsData {
  spy: InstrumentOptionsData
  spx: InstrumentOptionsData
}

/**
 * Fetch a single endpoint, returning null on any error (graceful degradation).
 */
async function safeFetch<T>(url: string, body: unknown): Promise<T | null> {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

async function fetchOptionsData(): Promise<OptionsData> {
  // 4 parallel fetches — each independent, null on failure
  const [spyStraddle, spxStraddle, spyIv, spxIv] = await Promise.all([
    safeFetch<AtmStraddle>("/api/options/atm-straddle", { ticker: "SPY" }),
    safeFetch<AtmStraddle>("/api/options/atm-straddle", { ticker: "$SPX" }),
    safeFetch<IvMetrics>("/api/options/iv-metrics", { ticker: "SPY" }),
    safeFetch<IvMetrics>("/api/options/iv-metrics", { ticker: "SPX" }),
  ])

  return {
    spy: { straddle: spyStraddle, iv: spyIv },
    spx: { straddle: spxStraddle, iv: spxIv },
  }
}

export function useOptionsData() {
  const { data, error, isLoading } = useSWR<OptionsData>(
    "options-data",
    fetchOptionsData,
    {
      refreshInterval: 60_000, // 60s
      revalidateOnFocus: true,
      errorRetryCount: 2,
    },
  )

  // Available if we got at least one piece of data
  const available = data
    ? Boolean(
        data.spy.straddle ||
          data.spy.iv ||
          data.spx.straddle ||
          data.spx.iv,
      )
    : false

  return {
    data: data ?? null,
    isLoading,
    error,
    available,
  }
}
