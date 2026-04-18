"use client"

import { useCallback, useEffect, useState } from "react"
import type {
  SwingUniverseListResponse,
  SwingUniverseTicker,
  SwingUniverseUploadResponse,
} from "@/lib/types"

interface UseSwingUniverseReturn {
  tickers: SwingUniverseTicker[]
  sourceSummary: Record<string, number>
  activeCount: number
  latestBatchAt: string | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  addTicker: (ticker: string) => Promise<void>
  removeTicker: (ticker: string) => Promise<void>
  uploadCsv: (file: File, mode: "replace" | "add") => Promise<SwingUniverseUploadResponse>
}

export function useSwingUniverse(): UseSwingUniverseReturn {
  const [tickers, setTickers] = useState<SwingUniverseTicker[]>([])
  const [sourceSummary, setSourceSummary] = useState<Record<string, number>>({})
  const [activeCount, setActiveCount] = useState(0)
  const [latestBatchAt, setLatestBatchAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/swing/universe", { cache: "no-store" })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: SwingUniverseListResponse = await res.json()
      setTickers(data.tickers)
      setSourceSummary(data.source_summary)
      setActiveCount(data.active_count)
      setLatestBatchAt(data.latest_batch_at)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load universe")
    } finally {
      setLoading(false)
    }
  }, [])

  const addTicker = useCallback(async (ticker: string) => {
    const res = await fetch("/api/swing/universe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    await refresh()
  }, [refresh])

  const removeTicker = useCallback(async (ticker: string) => {
    const res = await fetch(`/api/swing/universe/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    await refresh()
  }, [refresh])

  const uploadCsv = useCallback(async (file: File, mode: "replace" | "add"): Promise<SwingUniverseUploadResponse> => {
    const form = new FormData()
    form.append("file", file)
    form.append("mode", mode)
    const res = await fetch("/api/swing/universe/upload", { method: "POST", body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || err.error || `HTTP ${res.status}`)
    }
    const data: SwingUniverseUploadResponse = await res.json()
    await refresh()
    return data
  }, [refresh])

  useEffect(() => { void refresh() }, [refresh])

  return { tickers, sourceSummary, activeCount, latestBatchAt, loading, error, refresh, addTicker, removeTicker, uploadCsv }
}
