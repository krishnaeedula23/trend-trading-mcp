"use client"

import { useState, useMemo } from "react"
import { ArrowUpDown, Save, Loader2, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { GoldenGateHit, GoldenGateSignalType, AtrStatus, Trend } from "@/lib/types"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

type SortKey = "ticker" | "last_close" | "distance" | "atr_covered" | "gate" | "trend"

// --- Badge helpers ---

function signalBadge(signal: GoldenGateSignalType): { text: string; color: string } {
  switch (signal) {
    case "golden_gate":
      return { text: "Golden Gate", color: "bg-amber-600/20 text-amber-400 border-amber-600/30" }
    case "call_trigger":
      return { text: "Call Trigger", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    case "put_trigger":
      return { text: "Put Trigger", color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
}

function directionBadge(direction: "bullish" | "bearish"): { text: string; color: string } {
  switch (direction) {
    case "bullish":
      return { text: "Bull", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    case "bearish":
      return { text: "Bear", color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
}

function atrStatusBadge(status: AtrStatus): { text: string; color: string } {
  switch (status) {
    case "green":
      return { text: "Room", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    case "orange":
      return { text: "Warning", color: "bg-amber-600/20 text-amber-400 border-amber-600/30" }
    case "red":
      return { text: "Extended", color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
}

function trendColor(trend: Trend): string {
  switch (trend) {
    case "bullish":
      return "text-emerald-400"
    case "bearish":
      return "text-red-400"
    case "neutral":
      return "text-zinc-400"
  }
}

function trendLabel(trend: Trend): string {
  switch (trend) {
    case "bullish":
      return "Bull"
    case "bearish":
      return "Bear"
    case "neutral":
      return "Neutral"
  }
}

// --- Save as Idea button ---

function SaveButton({ hit }: { hit: GoldenGateHit }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: hit.ticker,
        direction: hit.direction,
        timeframe: "1d",
        status: "watching",
        current_price: hit.last_close,
        tags: [
          "source:screener",
          "screener:golden_gate",
          `signal:${hit.signal}`,
          `atr:${hit.atr_status}`,
        ],
        source: "screener",
        notes: `Golden Gate scanner hit: ${hit.signal} ${hit.direction} — gate $${hit.gate_level.toFixed(2)}, dist ${hit.distance_pct > 0 ? "+" : ""}${hit.distance_pct.toFixed(1)}%, ATR ${hit.atr_covered_pct.toFixed(0)}% (${hit.atr_status})`,
      })
      setSaved(true)
      toast.success(`${hit.ticker} saved as idea`)
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Button
      size="sm"
      variant="ghost"
      className="h-7 w-7 p-0"
      disabled={saving || saved}
      onClick={handleSave}
      title={saved ? "Saved" : "Save as idea"}
    >
      {saving ? (
        <Loader2 className="size-3.5 animate-spin" />
      ) : saved ? (
        <CheckCircle2 className="size-3.5 text-emerald-400" />
      ) : (
        <Save className="size-3.5" />
      )}
    </Button>
  )
}

// --- Main table ---

export function GoldenGateResultsTable({ hits }: { hits: GoldenGateHit[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("distance")
  const [sortAsc, setSortAsc] = useState(true)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((p) => !p)
    else {
      setSortKey(key)
      // Default ascending for distance (closest first), descending for others
      setSortAsc(key === "distance")
    }
  }

  const sorted = useMemo(() => {
    const arr = [...hits]
    const dir = sortAsc ? 1 : -1
    arr.sort((a, b) => {
      switch (sortKey) {
        case "ticker":
          return dir * a.ticker.localeCompare(b.ticker)
        case "last_close":
          return dir * (a.last_close - b.last_close)
        case "distance":
          return dir * (Math.abs(a.distance_pct) - Math.abs(b.distance_pct))
        case "atr_covered":
          return dir * (a.atr_covered_pct - b.atr_covered_pct)
        case "gate":
          return dir * (a.gate_level - b.gate_level)
        case "trend": {
          const order: Record<Trend, number> = { bullish: 0, neutral: 1, bearish: 2 }
          return dir * (order[a.trend] - order[b.trend])
        }
        default:
          return 0
      }
    })
    return arr
  }, [hits, sortKey, sortAsc])

  if (hits.length === 0) return null

  const SortHeader = ({ label, k }: { label: string; k: SortKey }) => (
    <TableHead className="cursor-pointer select-none" onClick={() => toggleSort(k)}>
      <div className="flex items-center gap-1 text-xs">
        {label}
        <ArrowUpDown className="size-3 text-muted-foreground" />
      </div>
    </TableHead>
  )

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortHeader label="Ticker" k="ticker" />
            <SortHeader label="Price" k="last_close" />
            <TableHead className="text-xs">Signal</TableHead>
            <SortHeader label="Gate" k="gate" />
            <SortHeader label="Dist %" k="distance" />
            <SortHeader label="ATR %" k="atr_covered" />
            <TableHead className="text-xs">ATR</TableHead>
            <SortHeader label="Trend" k="trend" />
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((hit) => {
            const sig = signalBadge(hit.signal)
            const dir = directionBadge(hit.direction)
            const atr = atrStatusBadge(hit.atr_status)
            const distColor = hit.distance_pct >= 0 ? "text-emerald-400" : "text-red-400"

            return (
              <TableRow key={hit.ticker}>
                <TableCell className="font-mono text-xs font-medium">{hit.ticker}</TableCell>
                <TableCell className="text-xs">${hit.last_close.toFixed(2)}</TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    <Badge variant="outline" className={`text-[10px] ${sig.color}`}>
                      {sig.text}
                    </Badge>
                    <Badge variant="outline" className={`text-[10px] ${dir.color}`}>
                      {dir.text}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs">${hit.gate_level.toFixed(2)}</TableCell>
                <TableCell className={`text-xs font-medium ${distColor}`}>
                  {hit.distance_pct > 0 ? "+" : ""}
                  {hit.distance_pct.toFixed(1)}%
                </TableCell>
                <TableCell className="text-xs">{hit.atr_covered_pct.toFixed(0)}%</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${atr.color}`}>
                    {atr.text}
                  </Badge>
                </TableCell>
                <TableCell className={`text-xs font-medium ${trendColor(hit.trend)}`}>
                  {trendLabel(hit.trend)}
                </TableCell>
                <TableCell>
                  <SaveButton hit={hit} />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
