"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import type { MomentumScanRequest, MomentumScanResponse, MomentumHit } from "@/lib/types"

export interface MomentumScanConfig {
  universes: string[]
  min_price: number
  custom_tickers?: string[]
}

interface UseMomentumScanReturn {
  hits: MomentumHit[]
  scanning: boolean
  response: MomentumScanResponse | null
  config: MomentumScanConfig
  error: string | null
  runScan: (config: MomentumScanConfig) => void
  cancelScan: () => void
}

const STORAGE_KEY = "momentum_scan_results"
const CONFIG_KEY = "momentum_scan_config"

const DEFAULT_CONFIG: MomentumScanConfig = {
  universes: ["sp500", "nasdaq100"],
  min_price: 4.0,
}

// --- Session storage helpers ---

function saveResponse(data: MomentumScanResponse | null) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // quota exceeded or SSR — ignore
  }
}

function loadResponse(): MomentumScanResponse | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as MomentumScanResponse
  } catch {
    return null
  }
}

function saveConfig(config: MomentumScanConfig) {
  try {
    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(config))
  } catch {
    // ignore
  }
}

function loadConfig(): MomentumScanConfig {
  try {
    const raw = sessionStorage.getItem(CONFIG_KEY)
    if (!raw) return DEFAULT_CONFIG
    return JSON.parse(raw) as MomentumScanConfig
  } catch {
    return DEFAULT_CONFIG
  }
}

// --- Hook ---

export function useMomentumScan(): UseMomentumScanReturn {
  const [hits, setHits] = useState<MomentumHit[]>([])
  const [scanning, setScanning] = useState(false)
  const [response, setResponse] = useState<MomentumScanResponse | null>(null)
  const [config, setConfig] = useState<MomentumScanConfig>(DEFAULT_CONFIG)
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
    async (newConfig: MomentumScanConfig) => {
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
        const body: MomentumScanRequest = {
          universes: newConfig.universes,
          min_price: newConfig.min_price,
          ...(newConfig.custom_tickers?.length && { custom_tickers: newConfig.custom_tickers }),
        }

        const res = await fetch("/api/screener/momentum-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Unknown error" }))
          const msg = err.error ?? `HTTP ${res.status}`
          console.error("Momentum scan failed:", msg)
          setError(msg)
          return
        }

        const data: MomentumScanResponse = await res.json()
        setHits(data.hits)
        setResponse(data)
        saveResponse(data)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        const msg = err instanceof Error ? err.message : "Network error"
        console.error("Momentum scan failed:", msg)
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
