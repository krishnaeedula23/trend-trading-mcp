"use client"

import { useState, useEffect, useCallback } from "react"
import type {
  BreadthSnapshotSummary,
  DrillDownResponse,
  ThemeTrackerResponse,
  SectorStocksResponse,
} from "@/lib/types"

interface SelectedCell {
  scanKey: string
  date: string
}

export function useMarketMonitor() {
  const [snapshots, setSnapshots] = useState<BreadthSnapshotSummary[]>([])
  const [themeTracker, setThemeTracker] = useState<ThemeTrackerResponse | null>(null)
  const [drillDown, setDrillDown] = useState<DrillDownResponse | null>(null)
  const [sectorStocks, setSectorStocks] = useState<SectorStocksResponse | null>(null)
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null)
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [computing, setComputing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drillDownLoading, setDrillDownLoading] = useState(false)

  // Fetch snapshots + theme tracker on mount
  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [snapRes, themeRes] = await Promise.all([
          fetch("/api/market-monitor/snapshots?days=30"),
          fetch("/api/market-monitor/theme-tracker"),
        ])
        if (snapRes.ok) setSnapshots(await snapRes.json())
        if (themeRes.ok) setThemeTracker(await themeRes.json())
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Fetch drill-down when cell is selected
  const selectCell = useCallback(async (scanKey: string, date: string) => {
    setSelectedCell({ scanKey, date })
    setSelectedSector(null)
    setSectorStocks(null)
    setDrillDown(null)
    setDrillDownLoading(true)
    try {
      const res = await fetch(
        `/api/market-monitor/drill-down?scan=${encodeURIComponent(scanKey)}&date=${encodeURIComponent(date)}`
      )
      if (res.ok) setDrillDown(await res.json())
    } catch {
      // drill-down fetch failed
    } finally {
      setDrillDownLoading(false)
    }
  }, [])

  // Fetch sector stocks when sector is selected
  const selectSector = useCallback(async (sector: string, date?: string) => {
    setSelectedSector(sector)
    setSelectedCell(null)
    setDrillDown(null)
    setSectorStocks(null)
    try {
      const params = new URLSearchParams({ sector })
      if (date) params.set("date", date)
      const res = await fetch(`/api/market-monitor/sector-stocks?${params}`)
      if (res.ok) setSectorStocks(await res.json())
    } catch {
      // sector drill-down failed silently
    }
  }, [])

  // Force recompute
  const forceRecompute = useCallback(async () => {
    setComputing(true)
    setError(null)
    try {
      const res = await fetch("/api/market-monitor/compute", { method: "POST" })
      if (!res.ok) {
        setError(`Compute failed: ${res.status}`)
        return
      }
      // Reload snapshots + theme tracker
      const [snapRes, themeRes] = await Promise.all([
        fetch("/api/market-monitor/snapshots?days=30"),
        fetch("/api/market-monitor/theme-tracker"),
      ])
      if (snapRes.ok) setSnapshots(await snapRes.json())
      if (themeRes.ok) setThemeTracker(await themeRes.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compute failed")
    } finally {
      setComputing(false)
    }
  }, [])

  const closePanel = useCallback(() => {
    setSelectedCell(null)
    setSelectedSector(null)
    setDrillDown(null)
    setSectorStocks(null)
  }, [])

  const panelOpen = !!(selectedCell || selectedSector)

  return {
    snapshots,
    themeTracker,
    drillDown,
    sectorStocks,
    selectedCell,
    selectedSector,
    loading,
    computing,
    drillDownLoading,
    error,
    panelOpen,
    selectCell,
    selectSector,
    closePanel,
    forceRecompute,
  }
}
