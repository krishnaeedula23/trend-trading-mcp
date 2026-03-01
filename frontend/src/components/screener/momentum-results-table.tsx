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
import type { MomentumHit } from "@/lib/types"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

type SortKey = "ticker" | "last_close" | "max_pct" | "weekly" | "monthly" | "3month" | "6month"

function criterionBadge(label: string): { text: string; color: string } {
  switch (label) {
    case "weekly_10pct":
      return { text: "W+10%", color: "bg-blue-600/20 text-blue-400 border-blue-600/30" }
    case "monthly_25pct":
      return { text: "M+25%", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    case "3month_50pct":
      return { text: "3M+50%", color: "bg-purple-600/20 text-purple-400 border-purple-600/30" }
    case "6month_100pct":
      return { text: "6M+100%", color: "bg-amber-600/20 text-amber-400 border-amber-600/30" }
    default:
      return { text: label, color: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30" }
  }
}

function pctCell(value: number | null) {
  if (value == null) return <span className="text-muted-foreground">--</span>
  const color = value >= 0 ? "text-emerald-400" : "text-red-400"
  return (
    <span className={color}>
      {value > 0 ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  )
}

// --- Save as Idea button ---

function SaveButton({ hit }: { hit: MomentumHit }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: hit.ticker,
        direction: "bullish",
        timeframe: "1d",
        status: "watching",
        current_price: hit.last_close,
        tags: [
          "source:screener",
          "screener:momentum",
          ...hit.criteria_met.map((c) => `momentum:${c.label}`),
        ],
        source: "screener",
        notes: `Momentum scanner hit: ${hit.criteria_met
          .map(
            (c) =>
              `${c.label} (${c.pct_change > 0 ? "+" : ""}${c.pct_change.toFixed(1)}%)`
          )
          .join(", ")}`,
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

export function MomentumResultsTable({ hits }: { hits: MomentumHit[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("max_pct")
  const [sortAsc, setSortAsc] = useState(false)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((p) => !p)
    else {
      setSortKey(key)
      setSortAsc(false)
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
        case "max_pct":
          return dir * (a.max_pct_change - b.max_pct_change)
        case "weekly":
          return dir * ((a.weekly_pct ?? -999) - (b.weekly_pct ?? -999))
        case "monthly":
          return dir * ((a.monthly_pct ?? -999) - (b.monthly_pct ?? -999))
        case "3month":
          return dir * ((a.three_month_pct ?? -999) - (b.three_month_pct ?? -999))
        case "6month":
          return dir * ((a.six_month_pct ?? -999) - (b.six_month_pct ?? -999))
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
            <TableHead className="text-xs">Criteria</TableHead>
            <SortHeader label="Max %" k="max_pct" />
            <SortHeader label="1W" k="weekly" />
            <SortHeader label="1M" k="monthly" />
            <SortHeader label="3M" k="3month" />
            <SortHeader label="6M" k="6month" />
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((hit) => (
            <TableRow key={hit.ticker}>
              <TableCell className="font-mono text-xs font-medium">{hit.ticker}</TableCell>
              <TableCell className="text-xs">${hit.last_close.toFixed(2)}</TableCell>
              <TableCell>
                <div className="flex gap-1 flex-wrap">
                  {hit.criteria_met.map((c) => {
                    const { text, color } = criterionBadge(c.label)
                    return (
                      <Badge
                        key={c.label}
                        variant="outline"
                        className={`text-[10px] ${color}`}
                      >
                        {text}
                      </Badge>
                    )
                  })}
                </div>
              </TableCell>
              <TableCell className="text-xs font-medium text-emerald-400">
                +{hit.max_pct_change.toFixed(1)}%
              </TableCell>
              <TableCell className="text-xs">{pctCell(hit.weekly_pct)}</TableCell>
              <TableCell className="text-xs">{pctCell(hit.monthly_pct)}</TableCell>
              <TableCell className="text-xs">{pctCell(hit.three_month_pct)}</TableCell>
              <TableCell className="text-xs">{pctCell(hit.six_month_pct)}</TableCell>
              <TableCell>
                <SaveButton hit={hit} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
