"use client"

import { useState, useRef, useCallback } from "react"
import type { TradePlanResponse } from "@/lib/types"
import { detectSetups, type DetectedSetup } from "@/lib/setups"

export interface ScanResult {
  ticker: string
  success: boolean
  data?: TradePlanResponse
  setups: DetectedSetup[]
  error?: string
}

interface UseScanReturn {
  results: ScanResult[]
  scanning: boolean
  progress: { current: number; total: number }
  startScan: (tickers: string[], timeframe: string, direction: string) => void
  cancelScan: () => void
}

const CHUNK_SIZE = 5 // Sequential trade-plan calls per chunk (not batch — no batch trade-plan endpoint)

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

export function useScan(): UseScanReturn {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const abortRef = useRef<AbortController | null>(null)

  const startScan = useCallback(
    async (tickers: string[], timeframe: string, direction: string) => {
      // Cancel any existing scan
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setResults([])
      setScanning(true)
      setProgress({ current: 0, total: tickers.length })

      const chunks = chunk(tickers, CHUNK_SIZE)
      let processed = 0

      for (const batch of chunks) {
        if (controller.signal.aborted) break

        // Fetch all tickers in the chunk concurrently
        const chunkResults = await Promise.all(
          batch.map((t) => fetchTradePlan(t, timeframe, direction, controller.signal))
        )

        if (controller.signal.aborted) break

        processed += chunkResults.length
        setResults((prev) => [...prev, ...chunkResults])
        setProgress({ current: processed, total: tickers.length })
      }

      setScanning(false)
    },
    []
  )

  const cancelScan = useCallback(() => {
    abortRef.current?.abort()
    setScanning(false)
  }, [])

  return { results, scanning, progress, startScan, cancelScan }
}
