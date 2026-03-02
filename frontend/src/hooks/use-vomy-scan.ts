"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type {
  VomyScanRequest,
  VomyScanResponse,
  VomyHit,
  VomySignalType,
  VomyTimeframe,
} from "@/lib/types"

export interface VomyScanConfig {
  universes: string[]
  timeframe: VomyTimeframe
  signal_type: VomySignalType
  min_price: number
  include_premarket: boolean
  custom_tickers?: string[]
}

interface UseVomyScanReturn {
  hits: VomyHit[]
  scanning: boolean
  response: VomyScanResponse | null
  config: VomyScanConfig
  error: string | null
  runScan: (config: VomyScanConfig) => void
  cancelScan: () => void
}

const STORAGE_KEY = "vomy_scan_results"
const CONFIG_KEY = "vomy_scan_config"

const DEFAULT_CONFIG: VomyScanConfig = {
  universes: ["sp500", "nasdaq100"],
  timeframe: "1d",
  signal_type: "both",
  min_price: 4.0,
  include_premarket: true,
}

// --- Session storage helpers ---

function saveResponse(data: VomyScanResponse | null) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResponse(): VomyScanResponse | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as VomyScanResponse
  } catch {
    return null
  }
}

function saveConfig(config: VomyScanConfig) {
  try {
    const { custom_tickers: _, ...persistable } = config
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(persistable))
  } catch {
    // ignore
  }
}

function loadConfig(): VomyScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return DEFAULT_CONFIG
    return JSON.parse(raw) as VomyScanConfig
  } catch {
    return DEFAULT_CONFIG
  }
}

// --- Hook ---

export function useVomyScan(): UseVomyScanReturn {
  const [hits, setHits] = useState<VomyHit[]>([])
  const [scanning, setScanning] = useState(false)
  const [response, setResponse] = useState<VomyScanResponse | null>(null)
  const [config, setConfig] = useState<VomyScanConfig>(DEFAULT_CONFIG)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const hydrated = useRef(false)

  // Hydrate from sessionStorage on mount
  useEffect(() => {
    if (hydrated.current) return
    hydrated.current = true
    const saved = loadResponse()
    if (saved) {
      setHits(saved.hits)
      setResponse(saved)
    }
    setConfig(loadConfig())
  }, [])

  const runScan = useCallback(
    async (newConfig: VomyScanConfig) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setConfig(newConfig)
      saveConfig(newConfig)

      setHits([])
      setResponse(null)
      setError(null)
      saveResponse(null)
      setScanning(true)

      try {
        const body: VomyScanRequest = {
          universes: newConfig.universes,
          timeframe: newConfig.timeframe,
          signal_type: newConfig.signal_type,
          min_price: newConfig.min_price,
          include_premarket: newConfig.include_premarket,
          ...(newConfig.custom_tickers?.length && { custom_tickers: newConfig.custom_tickers }),
        }

        const res = await fetch("/api/screener/vomy-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Unknown error" }))
          const msg = err.error ?? `HTTP ${res.status}`
          console.error("VOMY scan failed:", msg)
          setError(msg)
          return
        }

        const data: VomyScanResponse = await res.json()
        setHits(data.hits)
        setResponse(data)
        saveResponse(data)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        const msg = err instanceof Error ? err.message : "Network error"
        console.error("VOMY scan failed:", msg)
        setError(msg)
      } finally {
        setScanning(false)
      }
    },
    []
  )

  const cancelScan = useCallback(() => {
    abortRef.current?.abort()
    setScanning(false)
  }, [])

  return { hits, scanning, response, config, error, runScan, cancelScan }
}
