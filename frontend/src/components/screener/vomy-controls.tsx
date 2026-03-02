"use client"

import { useState } from "react"
import { Play, Square, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type {
  VomyScanResponse,
  VomySignalType,
  VomyTimeframe,
  Watchlist,
} from "@/lib/types"

interface VomyControlsProps {
  scanning: boolean
  response: VomyScanResponse | null
  error: string | null
  watchlists: Watchlist[]
  initialUniverses: string[]
  initialMinPrice: number
  initialTimeframe: VomyTimeframe
  initialSignalType: VomySignalType
  initialIncludePremarket: boolean
  onScan: (config: {
    universes: string[]
    timeframe: VomyTimeframe
    signal_type: VomySignalType
    min_price: number
    include_premarket: boolean
    custom_tickers?: string[]
  }) => void
  onCancel: () => void
}

const UNIVERSE_OPTIONS = [
  { key: "sp500", label: "S&P 500" },
  { key: "nasdaq100", label: "Nasdaq 100" },
  { key: "russell2000", label: "Russell 2000" },
] as const

const TIMEFRAME_OPTIONS: { key: VomyTimeframe; label: string }[] = [
  { key: "1h", label: "1H" },
  { key: "4h", label: "4H" },
  { key: "1d", label: "Daily" },
  { key: "1w", label: "Weekly" },
]

const SIGNAL_TYPE_OPTIONS: { key: VomySignalType; label: string }[] = [
  { key: "both", label: "Both" },
  { key: "vomy", label: "VOMY" },
  { key: "ivomy", label: "iVOMY" },
]

const SIGNAL_LABEL: Record<VomySignalType, string> = {
  both: "VOMY + iVOMY",
  vomy: "VOMY",
  ivomy: "iVOMY",
}

const TF_LABEL: Record<VomyTimeframe, string> = {
  "1h": "1H",
  "4h": "4H",
  "1d": "Daily",
  "1w": "Weekly",
}

export function VomyControls({
  scanning,
  response,
  error,
  watchlists,
  initialUniverses,
  initialMinPrice,
  initialTimeframe,
  initialSignalType,
  initialIncludePremarket,
  onScan,
  onCancel,
}: VomyControlsProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initialUniverses))
  const [selectedWatchlists, setSelectedWatchlists] = useState<Set<string>>(new Set())
  const [minPrice, setMinPrice] = useState(initialMinPrice)
  const [timeframe, setTimeframe] = useState<VomyTimeframe>(initialTimeframe)
  const [signalType, setSignalType] = useState<VomySignalType>(initialSignalType)
  const [includePremarket, setIncludePremarket] = useState(initialIncludePremarket)

  function toggleUniverse(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleWatchlist(id: string) {
    setSelectedWatchlists((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleRun() {
    if (selected.size === 0 && selectedWatchlists.size === 0) return

    const customTickers = watchlists
      .filter((w) => selectedWatchlists.has(w.id))
      .flatMap((w) => w.tickers)
    const unique = [...new Set(customTickers)]

    onScan({
      universes: Array.from(selected),
      timeframe,
      signal_type: signalType,
      min_price: minPrice,
      include_premarket: includePremarket,
      ...(unique.length > 0 && { custom_tickers: unique }),
    })
  }

  const sourceLabels = [
    ...UNIVERSE_OPTIONS.filter((u) => selected.has(u.key)).map((u) => u.label),
    ...watchlists.filter((w) => selectedWatchlists.has(w.id)).map((w) => w.name),
  ].join(" + ")

  const showPremarket = timeframe === "1h" || timeframe === "4h"

  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* Signal Type */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Signal</Label>
          <div className="flex gap-1.5">
            {SIGNAL_TYPE_OPTIONS.map((s) => (
              <Button
                key={s.key}
                size="sm"
                variant={signalType === s.key ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => setSignalType(s.key)}
                disabled={scanning}
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Timeframe */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Timeframe</Label>
          <div className="flex gap-1.5">
            {TIMEFRAME_OPTIONS.map((tf) => (
              <Button
                key={tf.key}
                size="sm"
                variant={timeframe === tf.key ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => setTimeframe(tf.key)}
                disabled={scanning}
              >
                {tf.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Universe toggles */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Universe</Label>
          <div className="flex gap-1.5">
            {UNIVERSE_OPTIONS.map((u) => (
              <Button
                key={u.key}
                size="sm"
                variant={selected.has(u.key) ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => toggleUniverse(u.key)}
                disabled={scanning}
              >
                {u.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Watchlist toggles */}
        {watchlists.length > 0 && (
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Watchlists</Label>
            <div className="flex gap-1.5 flex-wrap">
              {watchlists.map((w) => (
                <Button
                  key={w.id}
                  size="sm"
                  variant={selectedWatchlists.has(w.id) ? "default" : "outline"}
                  className="h-7 text-xs"
                  onClick={() => toggleWatchlist(w.id)}
                  disabled={scanning}
                >
                  {w.name}
                  <span className="ml-1 text-muted-foreground">({w.tickers.length})</span>
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Min price */}
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Min Price</Label>
          <Input
            type="number"
            value={minPrice}
            onChange={(e) => setMinPrice(Number(e.target.value))}
            className="h-7 w-20 text-xs"
            min={0}
            step={1}
            disabled={scanning}
          />
        </div>

        {/* Pre-Market toggle (intraday only) */}
        {showPremarket && (
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Pre-Market</Label>
            <Button
              size="sm"
              variant={includePremarket ? "default" : "outline"}
              className="h-7 text-xs"
              onClick={() => setIncludePremarket((p) => !p)}
              disabled={scanning}
            >
              {includePremarket ? "On" : "Off"}
            </Button>
          </div>
        )}

        {/* Run / Cancel */}
        <div className="flex gap-2">
          {scanning ? (
            <Button size="sm" variant="destructive" className="h-7 text-xs" onClick={onCancel}>
              <Square className="mr-1 size-3" /> Cancel
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={handleRun}
              disabled={selected.size === 0 && selectedWatchlists.size === 0}
            >
              <Play className="mr-1 size-3" /> Run Scan
            </Button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {scanning && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          Scanning {sourceLabels} for {SIGNAL_LABEL[signalType]} ({TF_LABEL[timeframe]})...
        </div>
      )}
      {error && !scanning && (
        <div className="flex items-center gap-2 text-xs text-red-400">
          <AlertCircle className="size-3" />
          Scan failed: {error}
        </div>
      )}
      {response && !scanning && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>{response.total_hits} hits</span>
          <span>&middot;</span>
          <span>{response.total_scanned} scanned</span>
          <span>&middot;</span>
          <span>{response.skipped_low_price} below ${minPrice}</span>
          <span>&middot;</span>
          <span>{response.total_errors} errors</span>
          <span>&middot;</span>
          <span>{response.scan_duration_seconds}s</span>
        </div>
      )}
    </div>
  )
}
