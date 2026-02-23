"use client"

import { useState } from "react"
import { Radar, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Watchlist } from "@/lib/types"

const TIMEFRAMES = [
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1H" },
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
]

const DIRECTIONS = [
  { value: "bullish", label: "Bullish" },
  { value: "bearish", label: "Bearish" },
]

interface ScanControlsProps {
  watchlists: Watchlist[]
  scanning: boolean
  progress: { current: number; total: number }
  onScan: (tickers: string[], timeframe: string, direction: string) => void
  onCancel: () => void
}

export function ScanControls({
  watchlists,
  scanning,
  progress,
  onScan,
  onCancel,
}: ScanControlsProps) {
  const [selectedWatchlist, setSelectedWatchlist] = useState<string>("all")
  const [timeframe, setTimeframe] = useState("1d")
  const [direction, setDirection] = useState("bullish")

  const allTickers = Array.from(
    new Set(watchlists.flatMap((w) => w.tickers))
  )

  const tickers =
    selectedWatchlist === "all"
      ? allTickers
      : watchlists.find((w) => w.id === selectedWatchlist)?.tickers ?? []

  function handleScan() {
    if (tickers.length === 0) return
    onScan(tickers, timeframe, direction)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* Watchlist picker */}
        <Select value={selectedWatchlist} onValueChange={setSelectedWatchlist}>
          <SelectTrigger className="w-40 h-9 text-xs">
            <SelectValue placeholder="Watchlist" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Watchlists</SelectItem>
            {watchlists.map((w) => (
              <SelectItem key={w.id} value={w.id}>
                {w.name} ({w.tickers.length})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Timeframe */}
        <Select value={timeframe} onValueChange={setTimeframe}>
          <SelectTrigger className="w-20 h-9 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIMEFRAMES.map((tf) => (
              <SelectItem key={tf.value} value={tf.value}>
                {tf.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Direction */}
        <Select value={direction} onValueChange={setDirection}>
          <SelectTrigger className="w-24 h-9 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIRECTIONS.map((d) => (
              <SelectItem key={d.value} value={d.value}>
                {d.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Scan / Cancel button */}
        {scanning ? (
          <Button
            size="sm"
            variant="destructive"
            className="gap-1.5 h-9"
            onClick={onCancel}
          >
            <X className="size-3.5" />
            Cancel
          </Button>
        ) : (
          <Button
            size="sm"
            className="gap-1.5 h-9"
            onClick={handleScan}
            disabled={tickers.length === 0}
          >
            <Radar className="size-3.5" />
            Scan {tickers.length} tickers
          </Button>
        )}
      </div>

      {/* Progress bar */}
      {scanning && progress.total > 0 && (
        <div className="space-y-1">
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{
                width: `${(progress.current / progress.total) * 100}%`,
              }}
            />
          </div>
          <p className="text-[10px] text-muted-foreground">
            Scanning {progress.current} of {progress.total}...
          </p>
        </div>
      )}
    </div>
  )
}
