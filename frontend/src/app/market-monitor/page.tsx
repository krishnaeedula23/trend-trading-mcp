"use client"

import { Button } from "@/components/ui/button"
import { RefreshCw } from "lucide-react"
import { useMarketMonitor } from "@/hooks/use-market-monitor"
import { BreadthHeatMap } from "@/components/market-monitor/breadth-heat-map"
import { DrillDownPanel } from "@/components/market-monitor/drill-down-panel"
import { ThemeTrackerTable } from "@/components/market-monitor/theme-tracker-table"

export default function MarketMonitorPage() {
  const monitor = useMarketMonitor()

  const lastUpdated = monitor.snapshots.length > 0
    ? monitor.snapshots[0].computed_at
    : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold">Market Monitor</h1>
          <p className="text-xs text-muted-foreground">
            Breadth of {monitor.themeTracker?.universe_size ?? "..."} stocks with $1B+ market cap
            {lastUpdated && (
              <> &middot; Updated {new Date(lastUpdated).toLocaleString()}</>
            )}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={monitor.forceRecompute}
          disabled={monitor.computing}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${monitor.computing ? "animate-spin" : ""}`} />
          {monitor.computing ? "Computing..." : "Force Recompute"}
        </Button>
      </div>

      {/* Loading state */}
      {monitor.loading && (
        <div className="text-sm text-muted-foreground text-center py-12">
          Loading breadth data...
        </div>
      )}

      {/* Error state */}
      {monitor.error && (
        <div className="text-sm text-red-400 text-center py-4">
          {monitor.error}
        </div>
      )}

      {/* Heat Map */}
      {!monitor.loading && (
        <BreadthHeatMap
          snapshots={monitor.snapshots}
          selectedCell={monitor.selectedCell}
          onCellClick={monitor.selectCell}
        />
      )}

      {/* Theme Tracker */}
      {!monitor.loading && (
        <div>
          <h2 className="text-sm font-semibold mb-2">Theme Tracker</h2>
          <ThemeTrackerTable
            data={monitor.themeTracker}
            onSectorClick={(sector) => monitor.selectSector(sector)}
            selectedSector={monitor.selectedSector}
          />
        </div>
      )}

      {/* Drill-down side panel */}
      <DrillDownPanel
        open={monitor.panelOpen}
        onClose={monitor.closePanel}
        drillDown={monitor.drillDown}
        sectorStocks={monitor.sectorStocks}
        selectedSector={monitor.selectedSector}
        loading={monitor.drillDownLoading}
      />
    </div>
  )
}
