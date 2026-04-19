"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useSwingIdeas } from "@/hooks/use-swing-ideas"
import type { SwingIdea } from "@/lib/types"

interface IdeasListProps {
  status: "active" | "watching"
}

function computeRR(idea: SwingIdea): string {
  const { entry_zone_low, entry_zone_high, stop_price, first_target } = idea
  if (first_target === null || stop_price === null || stop_price === undefined) return "—"
  const midpoint =
    entry_zone_low !== null && entry_zone_high !== null
      ? (entry_zone_low + entry_zone_high) / 2
      : entry_zone_low ?? entry_zone_high
  if (midpoint === null) return "—"
  const risk = midpoint - stop_price
  if (risk <= 0) return "—"
  const reward = first_target - midpoint
  return `${(reward / risk).toFixed(1)}R`
}

function formatEntry(idea: SwingIdea): string {
  const { entry_zone_low: low, entry_zone_high: high } = idea
  if (low !== null && high !== null) return `${low.toFixed(0)}–${high.toFixed(0)}`
  if (low !== null) return low.toFixed(0)
  if (high !== null) return high.toFixed(0)
  return "—"
}

function formatTargets(idea: SwingIdea): string {
  const { first_target: t1, second_target: t2 } = idea
  if (t1 === null) return "—"
  if (t2 !== null) return `${t1.toFixed(0)}/${t2.toFixed(0)}`
  return t1.toFixed(0)
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/15 text-green-400 border-green-500/30",
  watching: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  exited: "bg-muted text-muted-foreground",
  invalidated: "bg-red-500/15 text-red-400 border-red-500/30",
}

function IdeaRow({ idea }: { idea: SwingIdea }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr
        className="border-b border-border/30 hover:bg-card/40 cursor-pointer text-xs"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-3 py-2">
          <Badge
            variant="outline"
            className={`text-[9px] ${STATUS_COLORS[idea.status] ?? ""}`}
          >
            {idea.status}
          </Badge>
        </td>
        <td className="px-3 py-2 text-muted-foreground">{idea.cycle_stage}</td>
        <td className="px-3 py-2 font-mono font-semibold">{idea.ticker}</td>
        <td className="px-3 py-2 text-center">{idea.confluence_score}/10</td>
        <td className="px-3 py-2">{formatEntry(idea)}</td>
        <td className="px-3 py-2">{idea.stop_price.toFixed(0)}</td>
        <td className="px-3 py-2">{formatTargets(idea)}</td>
        <td className="px-3 py-2 text-center">{computeRR(idea)}</td>
        <td className="px-3 py-2 text-center text-muted-foreground">
          {expanded ? <ChevronDown className="size-3 inline" /> : <ChevronRight className="size-3 inline" />}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/30 bg-card/20">
          <td colSpan={9} className="px-4 py-3 text-xs">
            <div className="space-y-2">
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">Thesis:</span>{" "}
                {idea.base_thesis ?? "No thesis yet — Plan 3"}
              </p>
              <p className="text-muted-foreground text-[10px]">
                Stage evolution — coming Plan 4
              </p>
              <div className="flex gap-2 pt-1">
                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={(e) => { e.stopPropagation() }}>
                  View Detail
                </Button>
                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={(e) => { e.stopPropagation() }}>
                  Add Note
                </Button>
                <Button size="sm" variant="outline" className="h-6 text-[10px] text-red-400 border-red-500/30 hover:bg-red-500/10" onClick={(e) => { e.stopPropagation() }}>
                  Mark Invalidated
                </Button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function IdeasList({ status }: IdeasListProps) {
  const { ideas, loading, error, refresh } = useSwingIdeas(status)

  if (loading && ideas.length === 0) {
    return (
      <div className="space-y-1">
        <Skeleton className="h-8" />
        <Skeleton className="h-8" />
        <Skeleton className="h-8" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 rounded border border-border/40 bg-card/30 p-4 text-xs text-red-400">
        <span>{error}</span>
        <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={refresh}>
          <RefreshCw className="size-3 mr-1" /> Retry
        </Button>
      </div>
    )
  }

  if (ideas.length === 0) {
    return (
      <div className="rounded border border-border/50 bg-card/30 p-8 text-center">
        <p className="text-sm text-muted-foreground">
          No ideas yet — pipeline will populate on next pre-market run.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded border border-border/40 overflow-x-auto">
      <table className="w-full text-xs">
        <caption className="sr-only">
          {status === "active" ? "Active swing ideas" : "Watching swing ideas"} — ranked by confluence score
        </caption>
        <thead>
          <tr className="border-b border-border/40 text-[10px] text-muted-foreground uppercase tracking-wide">
            <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Stage</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Ticker</th>
            <th scope="col" className="px-3 py-2 text-center font-medium">Conf</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Entry</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Stop</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Targets</th>
            <th scope="col" className="px-3 py-2 text-center font-medium">R:R</th>
            <th scope="col" className="px-3 py-2 text-center font-medium w-8">
              <span className="sr-only">Expand row</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ideas.map((idea) => (
            <IdeaRow key={idea.id} idea={idea} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
