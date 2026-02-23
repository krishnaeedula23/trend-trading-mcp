"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type { TradePlanResponse } from "@/lib/types"
import { detectSetups, type DetectedSetup } from "@/lib/setups"

export interface ScanResult {
  ticker: string
  success: boolean
  data?: TradePlanResponse
  setups: DetectedSetup[]
  error?: string
}

interface ScanConfig {
  timeframe: string
  direction: string
}

interface UseScanReturn {
  results: ScanResult[]
  scanning: boolean
  progress: { current: number; total: number }
  config: ScanConfig
  startScan: (tickers: string[], timeframe: string, direction: string) => void
  cancelScan: () => void
}

const CHUNK_SIZE = 5
const STORAGE_KEY = "scan_results"
const CONFIG_KEY = "scan_config"

// --- Session storage helpers ---

function saveResults(results: ScanResult[]) {
  try {
    // Strip full TradePlanResponse.data to keep storage small — keep only what the table needs
    const slim = results.map((r) => ({
      ticker: r.ticker,
      success: r.success,
      data: r.data
        ? {
            ticker: r.data.ticker,
            timeframe: r.data.timeframe,
            direction: r.data.direction,
            atr_levels: r.data.atr_levels,
            pivot_ribbon: r.data.pivot_ribbon,
            phase_oscillator: r.data.phase_oscillator,
            green_flag: r.data.green_flag,
          }
        : undefined,
      setups: r.setups,
      error: r.error,
    }))
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(slim))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResults(): ScanResult[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as ScanResult[]
  } catch {
    return []
  }
}

function saveConfig(config: ScanConfig) {
  try {
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(config))
  } catch {
    // ignore
  }
}

function loadConfig(): ScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return { timeframe: "1d", direction: "bullish" }
    return JSON.parse(raw) as ScanConfig
  } catch {
    return { timeframe: "1d", direction: "bullish" }
  }
}

// --- Fetching ---

async function fetchTradePlan(
  ticker: string,
  timeframe: string,
  direction: string,
  signal: AbortSignal
): Promise<ScanResult> {
  try {
    const res = await fetch("/api/satyland/trade-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, timeframe, direction }),
      signal,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Unknown error" }))
      return { ticker, success: false, setups: [], error: err.error ?? `HTTP ${res.status}` }
    }
    const data: TradePlanResponse = await res.json()
    const setups = detectSetups(data)
    return { ticker, success: true, data, setups }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return { ticker, success: false, setups: [], error: "Cancelled" }
    }
    return { ticker, success: false, setups: [], error: String(err) }
  }
}

function chunk<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = []
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size))
  }
  return chunks
}

// --- Hook ---

export function useScan(): UseScanReturn {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [config, setConfig] = useState<ScanConfig>({ timeframe: "1d", direction: "bullish" })
  const abortRef = useRef<AbortController | null>(null)
  const hydrated = useRef(false)

  // Hydrate from sessionStorage on mount
  useEffect(() => {
    if (hydrated.current) return
    hydrated.current = true
    const saved = loadResults()
    if (saved.length > 0) setResults(saved)
    setConfig(loadConfig())
  }, [])

  const startScan = useCallback(
    async (tickers: string[], timeframe: string, direction: string) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const newConfig = { timeframe, direction }
      setConfig(newConfig)
      saveConfig(newConfig)

      setResults([])
      saveResults([])
      setScanning(true)
      setProgress({ current: 0, total: tickers.length })

      const chunks = chunk(tickers, CHUNK_SIZE)
      let processed = 0
      let allResults: ScanResult[] = []

      for (const batch of chunks) {
        if (controller.signal.aborted) break

        const chunkResults = await Promise.all(
          batch.map((t) => fetchTradePlan(t, timeframe, direction, controller.signal))
        )

        if (controller.signal.aborted) break

        processed += chunkResults.length
        allResults = [...allResults, ...chunkResults]
        setResults(allResults)
        setProgress({ current: processed, total: tickers.length })
      }

      saveResults(allResults)
      setScanning(false)
    },
    []
  )

  const cancelScan = useCallback(() => {
    abortRef.current?.abort()
    setScanning(false)
    // Save whatever we have so far
    setResults((prev) => {
      saveResults(prev)
      return prev
    })
  }, [])

  return { results, scanning, progress, config, startScan, cancelScan }
}
