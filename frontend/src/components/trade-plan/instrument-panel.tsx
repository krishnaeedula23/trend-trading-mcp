import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { GradeBadge } from "@/components/ideas/grade-badge"
import type { InstrumentPlan } from "@/lib/daily-plan-types"
import { MtfEmaGrid } from "./mtf-ema-grid"
import { PhaseStatusRow } from "./phase-status-row"
import { TargetPlan } from "./target-plan"
import { KeyLevelsSection } from "./key-levels-section"
import { ActiveSetups } from "./active-setups"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

function ribbonColor(state: string): string {
  switch (state) {
    case "bullish":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "bearish":
      return "bg-red-600/20 text-red-400 border-red-600/30"
    default:
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
  }
}

function atrStatusColor(status: string): string {
  switch (status) {
    case "green":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "orange":
      return "bg-amber-600/20 text-amber-400 border-amber-600/30"
    case "red":
      return "bg-red-600/20 text-red-400 border-red-600/30"
    default:
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
  }
}

export function InstrumentPanel({ plan }: { plan: InstrumentPlan }) {
  const atr = plan.daily.atr_levels
  const ribbon = plan.daily.pivot_ribbon
  const greenFlag = plan.daily.green_flag

  return (
    <Card className="border-border/50 bg-card/50">
      <CardContent className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight">
              {plan.displayName}
            </span>
            <span className="text-lg font-mono font-medium text-foreground">
              ${fmt(atr.current_price)}
            </span>
            {greenFlag && (
              <GradeBadge grade={greenFlag.grade} size="sm" />
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <Badge className={cn("text-[10px]", ribbonColor(ribbon.ribbon_state))}>
              {ribbon.ribbon_state.toUpperCase()}
            </Badge>
            <Badge className={cn("text-[10px]", atrStatusColor(atr.atr_status))}>
              ATR {atr.atr_status.toUpperCase()}
            </Badge>
          </div>
        </div>

        {/* Phase Status */}
        <PhaseStatusRow plan={plan} />

        <div className="h-px bg-border/30" />

        {/* Multi-Timeframe EMA Grid */}
        <div>
          <span className="text-xs font-semibold text-muted-foreground">
            Multi-Timeframe EMAs
          </span>
          <MtfEmaGrid plan={plan} />
        </div>

        <div className="h-px bg-border/30" />

        {/* Targets */}
        <TargetPlan
          upside={plan.targets.upside}
          downside={plan.targets.downside}
        />

        <div className="h-px bg-border/30" />

        {/* Key Levels */}
        <KeyLevelsSection plan={plan} />

        <div className="h-px bg-border/30" />

        {/* Active Setups */}
        <ActiveSetups plan={plan} />

        {/* Open Gaps */}
        {plan.daily.open_gaps && plan.daily.open_gaps.length > 0 && (
          <>
            <div className="h-px bg-border/30" />
            <div className="space-y-1">
              <span className="text-xs font-semibold text-muted-foreground">
                Open Gaps
              </span>
              {plan.daily.open_gaps.map((gap, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground capitalize">
                    {gap.type} gap
                  </span>
                  <span className="font-mono text-xs">
                    ${fmt(gap.gap_low)} – ${fmt(gap.gap_high)}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
