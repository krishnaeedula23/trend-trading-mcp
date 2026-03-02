"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type {
  GoldenGateScanRequest,
  GoldenGateScanResponse,
  GoldenGateHit,
  GoldenGateSignalType,
  TradingMode,
} from "@/lib/types"

export interface GoldenGateScanConfig {
  universes: string[]
  trading_mode: TradingMode
  signal_type: GoldenGateSignalType
  min_price: number
  include_premarket: boolean
  custom_tickers?: string[]
}

interface UseGoldenGateScanReturn {
  hits: GoldenGateHit[]
  scanning: boolean
  response: GoldenGateScanResponse | null
  config: GoldenGateScanConfig
  error: string | null
  runScan: (config: GoldenGateScanConfig) => void
  cancelScan: () => void
}

const STORAGE_KEY = "golden_gate_scan_results"
const CONFIG_KEY = "golden_gate_scan_config"

const DEFAULT_CONFIG: GoldenGateScanConfig = {
  universes: ["sp500", "nasdaq100"],
  trading_mode: "day",
  signal_type: "golden_gate_up",
  min_price: 4.0,
  include_premarket: true,
}

// --- Session storage helpers ---

function saveResponse(data: GoldenGateScanResponse | null) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResponse(): GoldenGateScanResponse | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as GoldenGateScanResponse
  } catch {
    return null
  }
}

function saveConfig(config: GoldenGateScanConfig) {
  try {
    const { custom_tickers: _, ...persistable } = config
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(persistable))
  } catch {
    // ignore
  }
}

function loadConfig(): GoldenGateScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return DEFAULT_CONFIG
    return JSON.parse(raw) as GoldenGateScanConfig
  } catch {
    return DEFAULT_CONFIG
  }
}

// --- Hook ---

export function useGoldenGateScan(): UseGoldenGateScanReturn {
  const [hits, setHits] = useState<GoldenGateHit[]>([])
  const [scanning, setScanning] = useState(false)
  const [response, setResponse] = useState<GoldenGateScanResponse | null>(null)
  const [config, setConfig] = useState<GoldenGateScanConfig>(DEFAULT_CONFIG)
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
    async (newConfig: GoldenGateScanConfig) => {
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
        const body: GoldenGateScanRequest = {
          universes: newConfig.universes,
          trading_mode: newConfig.trading_mode,
          signal_type: newConfig.signal_type,
          min_price: newConfig.min_price,
          include_premarket: newConfig.include_premarket,
          ...(newConfig.custom_tickers?.length && { custom_tickers: newConfig.custom_tickers }),
        }

        const res = await fetch("/api/screener/golden-gate-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Unknown error" }))
          const msg = err.error ?? `HTTP ${res.status}`
          console.error("Golden Gate scan failed:", msg)
          setError(msg)
          return
        }

        const data: GoldenGateScanResponse = await res.json()
        setHits(data.hits)
        setResponse(data)
        saveResponse(data)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        const msg = err instanceof Error ? err.message : "Network error"
        console.error("Golden Gate scan failed:", msg)
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
