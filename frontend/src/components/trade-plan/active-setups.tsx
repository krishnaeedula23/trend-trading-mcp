import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { detectSetups, SETUP_META, type DetectedSetup } from "@/lib/setups"
import type { InstrumentPlan } from "@/lib/daily-plan-types"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

const CONFIDENCE_COLOR: Record<string, string> = {
  strong: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
  moderate: "bg-amber-600/20 text-amber-400 border-amber-600/30",
  forming: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30",
}

function SetupBadge({ setup }: { setup: DetectedSetup }) {
  const meta = SETUP_META[setup.id]
  return (
    <div className="flex items-center justify-between text-sm py-1">
      <div className="flex items-center gap-2">
        <Badge
          variant="outline"
          className={cn("text-[10px]", `border-${meta.color}-600/30 text-${meta.color}-400`)}
        >
          #{meta.number} {meta.shortName}
        </Badge>
        <Badge className={cn("text-[9px] px-1 py-0", CONFIDENCE_COLOR[setup.confidence])}>
          {setup.confidence.toUpperCase()}
        </Badge>
        <span className="text-xs text-muted-foreground capitalize">
          {setup.direction}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs font-mono">
        {setup.entryPrice != null && (
          <span>E: ${fmt(setup.entryPrice)}</span>
        )}
        {setup.targetPrice != null && (
          <span className="text-emerald-400">T: ${fmt(setup.targetPrice)}</span>
        )}
        {setup.stopPrice != null && (
          <span className="text-red-400">S: ${fmt(setup.stopPrice)}</span>
        )}
      </div>
    </div>
  )
}

export function ActiveSetups({ plan }: { plan: InstrumentPlan }) {
  const setups = detectSetups(plan.daily)

  if (setups.length === 0) {
    return (
      <div className="text-xs text-muted-foreground py-1">
        No active setups detected
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      <span className="text-xs font-semibold text-muted-foreground">Active Setups</span>
      {setups.map((setup) => (
        <SetupBadge key={setup.id} setup={setup} />
      ))}
    </div>
  )
}
