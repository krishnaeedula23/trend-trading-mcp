"use client"

import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useDailyPlan } from "@/hooks/use-daily-plan"
import { useOptionsData } from "@/hooks/use-options-data"
import { VixStatusBar } from "./vix-status-bar"
import { StrategySection } from "./strategy-section"
import { DirectionalPlan } from "./directional-plan"
import { OptionsDataSection } from "./options-data-section"
import { InstrumentPanel } from "./instrument-panel"
import { TradePlanSkeleton } from "./trade-plan-skeleton"

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })
}

function sessionLabel(session: string): string {
  switch (session) {
    case "after_close":
      return "After Close"
    case "premarket":
      return "Premarket"
    case "manual":
      return "Manual"
    default:
      return session
  }
}

function sessionColor(session: string): string {
  switch (session) {
    case "after_close":
      return "bg-purple-600/20 text-purple-400 border-purple-600/30"
    case "premarket":
      return "bg-blue-600/20 text-blue-400 border-blue-600/30"
    default:
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
  }
}

export function TradePlanPage() {
  const { data, isLoading, isRefreshing, error, refresh } = useDailyPlan()
  const optionsData = useOptionsData()

  if (isLoading || (isRefreshing && !data)) {
    return <TradePlanSkeleton />
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-sm text-muted-foreground">
          Failed to load trade plan
        </p>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="size-3.5 mr-1.5" />
          Retry
        </Button>
      </div>
    )
  }

  if (!data || data.instruments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-sm text-muted-foreground">
          No trade plan data available
        </p>
        <Button variant="outline" size="sm" onClick={refresh} disabled={isRefreshing}>
          <RefreshCw className={cn("size-3.5 mr-1.5", isRefreshing && "animate-spin")} />
          {isRefreshing ? "Generating..." : "Generate Plan"}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight">
              Daily Trade Plan
            </h1>
            <Badge className={cn("text-[10px]", sessionColor(data.session))}>
              {sessionLabel(data.session)}
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{formatDate(data.fetchedAt)}</span>
            <span className="text-border">|</span>
            <span>Updated {formatTime(data.fetchedAt)}</span>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={cn("size-3.5 mr-1.5", isRefreshing && "animate-spin")} />
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {/* VIX Status Bar */}
      <VixStatusBar vix={data.vix} />

      {/* Strategy Section — game plan with EM/ATR confluence + VIX premarket */}
      <StrategySection
        instruments={data.instruments}
        vix={data.vix}
        optionsData={optionsData.data}
      />

      {/* Directional Plan */}
      <DirectionalPlan instruments={data.instruments} />

      {/* Options Data — IV, IV Rank, IV Percentile, Expected Move */}
      <OptionsDataSection data={optionsData.data} isLoading={optionsData.isLoading} />

      {/* Instrument Panels — two-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {data.instruments.map((inst) => (
          <InstrumentPanel key={inst.ticker} plan={inst} />
        ))}
      </div>
    </div>
  )
}
