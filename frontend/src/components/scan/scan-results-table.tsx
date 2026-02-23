"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import { ArrowUpDown, Save, Loader2, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
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
import type { Grade, Phase, RibbonState } from "@/lib/types"
import { SETUP_META, type DetectedSetup, type SetupId } from "@/lib/setups"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"
import type { ScanResult } from "@/hooks/use-scan"

// --- Filters ---

type GradeFilter = "A+" | "A" | "B" | "skip"
type SortKey = "grade" | "setups" | "ticker" | "price"

const GRADE_ORDER: Record<string, number> = { "A+": 0, A: 1, B: 2, skip: 3 }

const ALL_SETUP_IDS: SetupId[] = [
  "trend_continuation", "golden_gate", "vomy", "ivomy",
  "squeeze", "divergence_extreme", "dip_connoisseur",
]

// --- Color helpers ---

function gradeStyle(grade: Grade): string {
  switch (grade) {
    case "A+": return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "A":  return "bg-blue-600/20 text-blue-400 border-blue-600/30"
    case "B":  return "bg-yellow-600/20 text-yellow-400 border-yellow-600/30"
    case "skip": return "bg-red-600/20 text-red-400 border-red-600/30"
  }
}

function biasColor(candle: string | null): string {
  switch (candle) {
    case "green":  return "bg-emerald-500"
    case "blue":   return "bg-blue-500"
    case "orange": return "bg-orange-500"
    case "red":    return "bg-red-500"
    default:       return "bg-zinc-500"
  }
}

function phaseText(phase: Phase | null): { label: string; color: string } {
  switch (phase) {
    case "green":       return { label: "GREEN", color: "text-emerald-400" }
    case "red":         return { label: "RED", color: "text-red-400" }
    case "compression": return { label: "COMP", color: "text-zinc-400" }
    default:            return { label: "--", color: "text-muted-foreground" }
  }
}

function setupBadgeColor(color: string): string {
  const map: Record<string, string> = {
    emerald: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
    teal:    "bg-teal-600/20 text-teal-400 border-teal-600/30",
    red:     "bg-red-600/20 text-red-400 border-red-600/30",
    blue:    "bg-blue-600/20 text-blue-400 border-blue-600/30",
    purple:  "bg-purple-600/20 text-purple-400 border-purple-600/30",
    yellow:  "bg-yellow-600/20 text-yellow-400 border-yellow-600/30",
    amber:   "bg-amber-600/20 text-amber-400 border-amber-600/30",
  }
  return map[color] ?? "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
}

// --- Save button per row ---

function SaveButton({ result }: { result: ScanResult }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  if (!result.data) return null
  const setup = result.setups[0] // Save the strongest setup

  async function handleSave() {
    if (!result.data) return
    setSaving(true)
    try {
      await createIdea({
        ticker: result.data.ticker,
        direction: (setup?.direction ?? result.data.direction) as "bullish" | "bearish",
        timeframe: result.data.timeframe,
        status: "watching",
        grade: result.data.green_flag.grade,
        ribbon_state: result.data.pivot_ribbon.ribbon_state,
        bias_candle: result.data.pivot_ribbon.bias_candle,
        phase: result.data.phase_oscillator.phase,
        atr_status: result.data.atr_levels.atr_status,
        score: result.data.green_flag.score,
        current_price: result.data.atr_levels.current_price,
        call_trigger: result.data.atr_levels.call_trigger,
        put_trigger: result.data.atr_levels.put_trigger,
        entry_price: setup?.entryPrice ?? null,
        stop_loss: setup?.stopPrice ?? null,
        target_1: setup?.targetPrice ?? null,
        tags: setup ? [`setup:${setup.id}`] : [],
        source: "scan",
        indicator_snapshot: result.data as unknown as Record<string, unknown>,
      })
      setSaved(true)
      toast.success(`${result.ticker} saved as idea`)
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

interface ScanResultsTableProps {
  results: ScanResult[]
  timeframe: string
  direction: string
}

export function ScanResultsTable({
  results,
  timeframe,
  direction,
}: ScanResultsTableProps) {
  const [gradeFilters, setGradeFilters] = useState<Set<GradeFilter>>(
    new Set(["A+", "A"])
  )
  const [setupFilters, setSetupFilters] = useState<Set<SetupId>>(new Set())
  const [sortKey, setSortKey] = useState<SortKey>("grade")
  const [sortAsc, setSortAsc] = useState(true)

  // Only successful results
  const successful = results.filter((r) => r.success && r.data)

  // Apply filters
  const filtered = useMemo(() => {
    let list = successful

    // Grade filter
    if (gradeFilters.size > 0) {
      list = list.filter((r) => gradeFilters.has(r.data!.green_flag.grade as GradeFilter))
    }

    // Setup filter
    if (setupFilters.size > 0) {
      list = list.filter((r) =>
        r.setups.some((s) => setupFilters.has(s.id))
      )
    }

    return list
  }, [successful, gradeFilters, setupFilters])

  // Sort
  const sorted = useMemo(() => {
    const items = [...filtered]
    items.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case "grade":
          cmp =
            (GRADE_ORDER[a.data!.green_flag.grade] ?? 99) -
            (GRADE_ORDER[b.data!.green_flag.grade] ?? 99)
          break
        case "setups":
          cmp = b.setups.length - a.setups.length
          break
        case "ticker":
          cmp = a.ticker.localeCompare(b.ticker)
          break
        case "price":
          cmp =
            (a.data!.atr_levels.current_price ?? 0) -
            (b.data!.atr_levels.current_price ?? 0)
          break
      }
      return sortAsc ? cmp : -cmp
    })
    return items
  }, [filtered, sortKey, sortAsc])

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  function toggleGrade(g: GradeFilter) {
    setGradeFilters((prev) => {
      const next = new Set(prev)
      if (next.has(g)) next.delete(g)
      else next.add(g)
      return next
    })
  }

  function toggleSetup(id: SetupId) {
    setSetupFilters((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const failedCount = results.filter((r) => !r.success).length

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {/* Grade filters */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground mr-1">Grade:</span>
          {(["A+", "A", "B", "skip"] as GradeFilter[]).map((g) => (
            <button
              key={g}
              onClick={() => toggleGrade(g)}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-medium border transition-colors",
                gradeFilters.has(g)
                  ? gradeStyle(g)
                  : "border-border/50 text-muted-foreground hover:text-foreground"
              )}
            >
              {g === "skip" ? "SKIP" : g}
            </button>
          ))}
        </div>

        {/* Setup filters */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground mr-1">Setup:</span>
          {ALL_SETUP_IDS.map((id) => {
            const meta = SETUP_META[id]
            return (
              <button
                key={id}
                onClick={() => toggleSetup(id)}
                className={cn(
                  "rounded px-2 py-0.5 text-[10px] font-medium border transition-colors",
                  setupFilters.has(id)
                    ? setupBadgeColor(meta.color)
                    : "border-border/50 text-muted-foreground hover:text-foreground"
                )}
              >
                {meta.shortName}
              </button>
            )
          })}
        </div>
      </div>

      {/* Count */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>
          Showing {sorted.length} of {successful.length} results
        </span>
        {failedCount > 0 && (
          <Badge variant="outline" className="text-[10px] text-red-400 border-red-600/30">
            {failedCount} failed
          </Badge>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-16">
                <Button variant="ghost" size="sm" className="h-6 px-1 text-[10px] gap-1" onClick={() => toggleSort("ticker")}>
                  Ticker <ArrowUpDown className="size-3" />
                </Button>
              </TableHead>
              <TableHead className="w-16">
                <Button variant="ghost" size="sm" className="h-6 px-1 text-[10px] gap-1" onClick={() => toggleSort("grade")}>
                  Grade <ArrowUpDown className="size-3" />
                </Button>
              </TableHead>
              <TableHead>
                <Button variant="ghost" size="sm" className="h-6 px-1 text-[10px] gap-1" onClick={() => toggleSort("setups")}>
                  Setups <ArrowUpDown className="size-3" />
                </Button>
              </TableHead>
              <TableHead className="w-12">Bias</TableHead>
              <TableHead className="w-16">Phase</TableHead>
              <TableHead className="w-20 text-right">
                <Button variant="ghost" size="sm" className="h-6 px-1 text-[10px] gap-1 ml-auto" onClick={() => toggleSort("price")}>
                  Price <ArrowUpDown className="size-3" />
                </Button>
              </TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-xs text-muted-foreground py-8">
                  {results.length === 0
                    ? "Run a scan to see results"
                    : "No results match the current filters"}
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((r) => {
                const d = r.data!
                const phase = phaseText(d.phase_oscillator.phase)
                return (
                  <TableRow key={r.ticker} className="group">
                    <TableCell className="font-mono font-semibold text-sm">
                      <Link
                        href={`/analyze/${r.ticker}?tf=${timeframe}&dir=${direction}`}
                        className="hover:text-primary transition-colors"
                      >
                        {r.ticker}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("text-[10px]", gradeStyle(d.green_flag.grade))}>
                        {d.green_flag.grade === "skip" ? "SKIP" : d.green_flag.grade}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.setups.length === 0 ? (
                          <span className="text-[10px] text-muted-foreground">--</span>
                        ) : (
                          r.setups.map((s) => (
                            <Badge
                              key={s.id}
                              className={cn("text-[10px]", setupBadgeColor(s.color))}
                            >
                              {s.shortName}
                            </Badge>
                          ))
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className={cn("size-3 rounded-full", biasColor(d.pivot_ribbon.bias_candle))} />
                    </TableCell>
                    <TableCell>
                      <span className={cn("text-xs font-mono", phase.color)}>
                        {phase.label}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      ${d.atr_levels.current_price.toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <SaveButton result={r} />
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
