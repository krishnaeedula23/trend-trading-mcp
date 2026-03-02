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
import type { VomyHit, AtrStatus, Trend } from "@/lib/types"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

type SortKey = "ticker" | "last_close" | "distance" | "atr_covered" | "ema13" | "trend" | "conviction"

// --- Badge helpers ---

function signalBadge(signal: "vomy" | "ivomy"): { text: string; color: string } {
  switch (signal) {
    case "vomy":
      return { text: "VOMY", color: "bg-red-600/20 text-red-400 border-red-600/30" }
    case "ivomy":
      return { text: "iVOMY", color: "bg-teal-600/20 text-teal-400 border-teal-600/30" }
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

function convictionBadge(hit: VomyHit): { text: string; color: string } | null {
  if (!hit.conviction_type) return null
  const bars = hit.conviction_bars_ago ?? 0
  if (hit.conviction_confirmed) {
    if (hit.conviction_type === "bullish_crossover") {
      return { text: `Conv \u2191 (${bars}b)`, color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    }
    return { text: `Conv \u2193 (${bars}b)`, color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
  const arrow = hit.conviction_type === "bullish_crossover" ? "\u2191" : "\u2193"
  return { text: `${arrow} (${bars}b)`, color: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30" }
}

// --- Save as Idea button ---

function SaveButton({ hit }: { hit: VomyHit }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: hit.ticker,
        direction: hit.signal === "ivomy" ? "bullish" : "bearish",
        timeframe: hit.timeframe,
        status: "watching",
        current_price: hit.last_close,
        tags: [
          "source:screener",
          "screener:vomy",
          `signal:${hit.signal}`,
          `atr:${hit.atr_status}`,
          ...(hit.conviction_confirmed ? ["conviction:confirmed"] : []),
        ],
        source: "screener",
        notes: `${hit.signal.toUpperCase()} scanner hit — EMA ribbon flip on ${hit.timeframe}, dist ${hit.distance_from_ema48_pct > 0 ? "+" : ""}${hit.distance_from_ema48_pct.toFixed(1)}% from EMA48, ATR ${hit.atr_covered_pct.toFixed(0)}% (${hit.atr_status})${hit.conviction_confirmed ? `, conviction ${hit.conviction_type === "bullish_crossover" ? "↑" : "↓"} ${hit.conviction_bars_ago}b ago` : ""}`,
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

export function VomyResultsTable({ hits }: { hits: VomyHit[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("distance")
  const [sortAsc, setSortAsc] = useState(true)
  const [convictionOnly, setConvictionOnly] = useState(false)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((p) => !p)
    else {
      setSortKey(key)
      setSortAsc(key === "distance")
    }
  }

  const filtered = useMemo(() => {
    if (!convictionOnly) return hits
    return hits.filter((h) => h.conviction_confirmed)
  }, [hits, convictionOnly])

  const sorted = useMemo(() => {
    const arr = [...filtered]
    const dir = sortAsc ? 1 : -1
    arr.sort((a, b) => {
      switch (sortKey) {
        case "ticker":
          return dir * a.ticker.localeCompare(b.ticker)
        case "last_close":
          return dir * (a.last_close - b.last_close)
        case "distance":
          return dir * (Math.abs(a.distance_from_ema48_pct) - Math.abs(b.distance_from_ema48_pct))
        case "atr_covered":
          return dir * (a.atr_covered_pct - b.atr_covered_pct)
        case "ema13":
          return dir * (a.ema13 - b.ema13)
        case "trend": {
          const order: Record<Trend, number> = { bullish: 0, neutral: 1, bearish: 2 }
          return dir * (order[a.trend] - order[b.trend])
        }
        case "conviction": {
          const aConf = a.conviction_confirmed ? 0 : 1
          const bConf = b.conviction_confirmed ? 0 : 1
          if (aConf !== bConf) return dir * (aConf - bConf)
          return dir * ((a.conviction_bars_ago ?? 99) - (b.conviction_bars_ago ?? 99))
        }
        default:
          return 0
      }
    })
    return arr
  }, [filtered, sortKey, sortAsc])

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
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <Button
          size="sm"
          variant={convictionOnly ? "default" : "outline"}
          className="h-6 text-[10px]"
          onClick={() => setConvictionOnly((p) => !p)}
        >
          Conviction Only
        </Button>
        {convictionOnly && (
          <span className="text-[10px] text-muted-foreground">
            {filtered.length} of {hits.length} hits
          </span>
        )}
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortHeader label="Ticker" k="ticker" />
            <SortHeader label="Price" k="last_close" />
            <TableHead className="text-xs">Signal</TableHead>
            <SortHeader label="EMA13" k="ema13" />
            <TableHead className="text-xs">EMA21</TableHead>
            <TableHead className="text-xs">EMA34</TableHead>
            <TableHead className="text-xs">EMA48</TableHead>
            <SortHeader label="Dist %" k="distance" />
            <SortHeader label="ATR %" k="atr_covered" />
            <TableHead className="text-xs">ATR</TableHead>
            <SortHeader label="Conviction" k="conviction" />
            <SortHeader label="Trend" k="trend" />
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((hit) => {
            const sig = signalBadge(hit.signal as "vomy" | "ivomy")
            const atr = atrStatusBadge(hit.atr_status)
            const conv = convictionBadge(hit)
            const distColor = hit.distance_from_ema48_pct >= 0 ? "text-emerald-400" : "text-red-400"

            return (
              <TableRow key={hit.ticker}>
                <TableCell className="font-mono text-xs font-medium">{hit.ticker}</TableCell>
                <TableCell className="text-xs">${hit.last_close.toFixed(2)}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${sig.color}`}>
                    {sig.text}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{hit.ema13.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema21.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema34.toFixed(2)}</TableCell>
                <TableCell className="font-mono text-xs">{hit.ema48.toFixed(2)}</TableCell>
                <TableCell className={`text-xs font-medium ${distColor}`}>
                  {hit.distance_from_ema48_pct > 0 ? "+" : ""}
                  {hit.distance_from_ema48_pct.toFixed(1)}%
                </TableCell>
                <TableCell className="text-xs">{hit.atr_covered_pct.toFixed(0)}%</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-[10px] ${atr.color}`}>
                    {atr.text}
                  </Badge>
                </TableCell>
                <TableCell>
                  {conv ? (
                    <Badge variant="outline" className={`text-[10px] ${conv.color}`}>
                      {conv.text}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">&mdash;</span>
                  )}
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
