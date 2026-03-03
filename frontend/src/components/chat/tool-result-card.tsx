"use client"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Loader2, Search, BarChart3, Target, List } from "lucide-react"

const TOOL_META: Record<string, { label: string; icon: typeof Search }> = {
  get_saty_indicators: { label: "Saty Indicators", icon: BarChart3 },
  run_vomy_scan: { label: "VOMY Scan", icon: Search },
  run_golden_gate_scan: { label: "Golden Gate Scan", icon: Target },
  run_momentum_scan: { label: "Momentum Scan", icon: Search },
  get_trade_plan: { label: "Trade Plan", icon: Target },
  get_cached_scan: { label: "Cached Scan", icon: Search },
  get_watchlists: { label: "Watchlists", icon: List },
  get_options_straddle: { label: "Options Straddle", icon: BarChart3 },
}

interface ToolResultCardProps {
  toolName: string
  state: string
  input: Record<string, unknown>
  output?: unknown
}

export function ToolResultCard({
  toolName,
  state,
  input,
  output,
}: ToolResultCardProps) {
  const meta = TOOL_META[toolName] ?? { label: toolName, icon: Search }
  const Icon = meta.icon

  if (state !== "output-available") {
    return (
      <Card className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        <span>Calling {meta.label}...</span>
        {Object.keys(input).length > 0 && (
          <Badge variant="secondary" className="text-xs">
            {Object.entries(input)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")}
          </Badge>
        )}
      </Card>
    )
  }

  const data = output as Record<string, unknown> | null
  const totalHits =
    (data?.total_hits as number) ?? (data?.hits as unknown[])?.length

  return (
    <Card className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <span className="font-medium">{meta.label}</span>
        {totalHits !== undefined && (
          <Badge variant="secondary">{totalHits} hits</Badge>
        )}
      </div>
    </Card>
  )
}
