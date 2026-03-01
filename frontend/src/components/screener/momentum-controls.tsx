"use client"

import { useState } from "react"
import { Play, Square, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { MomentumScanResponse } from "@/lib/types"

interface MomentumControlsProps {
  scanning: boolean
  response: MomentumScanResponse | null
  error: string | null
  initialUniverses: string[]
  initialMinPrice: number
  onScan: (config: { universes: string[]; min_price: number }) => void
  onCancel: () => void
}

const UNIVERSE_OPTIONS = [
  { key: "sp500", label: "S&P 500" },
  { key: "nasdaq100", label: "Nasdaq 100" },
  { key: "russell2000", label: "Russell 2000" },
] as const

export function MomentumControls({
  scanning,
  response,
  error,
  initialUniverses,
  initialMinPrice,
  onScan,
  onCancel,
}: MomentumControlsProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initialUniverses))
  const [minPrice, setMinPrice] = useState(initialMinPrice)

  function toggleUniverse(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function handleRun() {
    if (selected.size === 0) return
    onScan({ universes: Array.from(selected), min_price: minPrice })
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-4">
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
              disabled={selected.size === 0}
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
          Scanning {Array.from(selected).join(" + ")} universe...
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
          <span>{response.total_scanned} scanned</span>
          <span>{response.skipped_low_price} below ${minPrice}</span>
          <span>{response.total_errors} errors</span>
          <span>{response.scan_duration_seconds}s</span>
        </div>
      )}
    </div>
  )
}
