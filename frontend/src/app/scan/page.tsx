"use client"

import { ScanControls } from "@/components/scan/scan-controls"
import { ScanResultsTable } from "@/components/scan/scan-results-table"
import { useWatchlists } from "@/hooks/use-watchlists"
import { useScan } from "@/hooks/use-scan"
import { useState } from "react"

export default function ScanPage() {
  const { watchlists, isLoading: watchlistsLoading } = useWatchlists()
  const { results, scanning, progress, startScan, cancelScan } = useScan()
  const [lastTf, setLastTf] = useState("1d")
  const [lastDir, setLastDir] = useState("bullish")

  function handleScan(tickers: string[], timeframe: string, direction: string) {
    setLastTf(timeframe)
    setLastDir(direction)
    startScan(tickers, timeframe, direction)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Scan</h1>
        <p className="text-xs text-muted-foreground">
          Scan watchlists for setup matches across your tickers
        </p>
      </div>

      {watchlistsLoading ? (
        <div className="rounded-lg border border-border/50 bg-card/30 p-4">
          <p className="text-xs text-muted-foreground">Loading watchlists...</p>
        </div>
      ) : watchlists.length === 0 ? (
        <div className="rounded-lg border border-border/50 bg-card/30 p-4">
          <p className="text-xs text-muted-foreground">
            No watchlists found. Create a watchlist first to start scanning.
          </p>
        </div>
      ) : (
        <>
          <ScanControls
            watchlists={watchlists}
            scanning={scanning}
            progress={progress}
            onScan={handleScan}
            onCancel={cancelScan}
          />

          <ScanResultsTable
            results={results}
            timeframe={lastTf}
            direction={lastDir}
          />
        </>
      )}
    </div>
  )
}
