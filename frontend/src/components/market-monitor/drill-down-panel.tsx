"use client"

import { useEffect, useState } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { DrillDownResponse, SectorStocksResponse, DrillDownTicker } from "@/lib/types"
import Link from "next/link"

interface DrillDownPanelProps {
  open: boolean
  onClose: () => void
  drillDown: DrillDownResponse | null
  sectorStocks: SectorStocksResponse | null
  selectedSector: string | null
  loading?: boolean
}

function ScanLabel({ scanKey }: { scanKey: string }) {
  const labels: Record<string, string> = {
    "4pct_up_1d": "\u25B2 4% Daily",
    "4pct_down_1d": "\u25BC 4% Daily",
    "25pct_up_20d": "\u25B2 25% Monthly",
    "25pct_down_20d": "\u25BC 25% Monthly",
    "50pct_up_20d": "\u25B2 50% Monthly",
    "50pct_down_20d": "\u25BC 50% Monthly",
    "13pct_up_34d": "\u25B2 13% Intermediate",
    "13pct_down_34d": "\u25BC 13% Intermediate",
    "25pct_up_65d": "\u25B2 25% Quarterly",
    "25pct_down_65d": "\u25BC 25% Quarterly",
  }
  return <span>{labels[scanKey] ?? scanKey}</span>
}

function TickerRow({ ticker, selected, onSelect }: {
  ticker: DrillDownTicker
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-md transition-colors
        ${selected ? "bg-accent" : "hover:bg-muted"}`}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono font-medium">{ticker.symbol}</span>
        <Badge variant="outline" className="text-[10px]">{ticker.sector}</Badge>
      </div>
      {ticker.close > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-muted-foreground">${ticker.close.toFixed(2)}</span>
          <span className={ticker.pct_change >= 0 ? "text-emerald-400" : "text-red-400"}>
            {ticker.pct_change >= 0 ? "+" : ""}{ticker.pct_change.toFixed(1)}%
          </span>
        </div>
      )}
    </button>
  )
}

export function DrillDownPanel({ open, onClose, drillDown, sectorStocks, selectedSector, loading }: DrillDownPanelProps) {
  const [selectedIdx, setSelectedIdx] = useState(0)

  const tickers = drillDown?.tickers ?? sectorStocks?.stocks ?? []
  const title = drillDown
    ? `${drillDown.date} \u2014 ${drillDown.count} stocks`
    : selectedSector
    ? `${selectedSector} \u2014 ${tickers.length} stocks`
    : ""

  // Reset selection when data changes
  useEffect(() => setSelectedIdx(0), [drillDown, sectorStocks])

  // Arrow key navigation
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIdx((i) => Math.min(i + 1, tickers.length - 1))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIdx((i) => Math.max(i - 1, 0))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, tickers.length])

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-[420px] sm:w-[420px] sm:max-w-[420px] p-0">
        <SheetHeader className="px-4 pt-4 pb-2">
          <SheetTitle className="text-sm">
            {drillDown && <ScanLabel scanKey={drillDown.scan_key} />}
            {selectedSector && selectedSector}
          </SheetTitle>
          <p className="text-xs text-muted-foreground">{title}</p>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-80px)]">
          <div className="px-2 pb-4 space-y-0.5">
            {tickers.map((ticker, idx) => (
              <div key={ticker.symbol}>
                <TickerRow
                  ticker={ticker}
                  selected={idx === selectedIdx}
                  onSelect={() => setSelectedIdx(idx)}
                />
                {idx === selectedIdx && (
                  <div className="px-3 py-2 mb-1 rounded-md bg-muted/50 space-y-2">
                    <Link
                      href={`/analyze/${ticker.symbol}`}
                      className="text-xs text-blue-400 hover:underline"
                    >
                      Open full analysis &rarr;
                    </Link>
                  </div>
                )}
              </div>
            ))}
            {tickers.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                {loading ? "Loading..." : "No stocks found"}
              </p>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
