"use client"

import { ScanControls } from "@/components/scan/scan-controls"
import { ScanResultsTable } from "@/components/scan/scan-results-table"
import { useWatchlists } from "@/hooks/use-watchlists"
import { useScan } from "@/hooks/use-scan"

export default function ScanPage() {
  const { watchlists, isLoading: watchlistsLoading } = useWatchlists()
  const { results, scanning, progress, config, startScan, cancelScan } = useScan()

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
            initialTimeframe={config.timeframe}
            initialDirection={config.direction}
            onScan={startScan}
            onCancel={cancelScan}
          />

          <ScanResultsTable
            results={results}
            timeframe={config.timeframe}
            direction={config.direction}
          />
        </>
      )}
    </div>
  )
}
