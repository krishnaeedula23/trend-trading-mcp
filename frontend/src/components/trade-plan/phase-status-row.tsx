import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { InstrumentPlan } from "@/lib/daily-plan-types"
import type { Phase } from "@/lib/types"

function phaseColor(phase: Phase): string {
  switch (phase) {
    case "green":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "red":
      return "bg-red-600/20 text-red-400 border-red-600/30"
    case "compression":
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
  }
}

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

export function PhaseStatusRow({ plan }: { plan: InstrumentPlan }) {
  const phases = [
    { label: "15m", phase: plan.fifteenMin.phase_oscillator },
    { label: "1H", phase: plan.hourly.phase_oscillator },
    { label: "1D", phase: plan.daily.phase_oscillator },
    { label: "1W", phase: plan.weekly.phase_oscillator },
  ]

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">Phase</span>
      {phases.map(({ label, phase }) => (
        <div key={label} className="flex items-center gap-1">
          <span className="text-[10px] font-mono text-muted-foreground">{label}:</span>
          <Badge className={cn("text-[10px] px-1.5", phaseColor(phase.phase))}>
            {phase.phase.toUpperCase()}
            {phase.phase !== "compression" && (
              <span className="ml-1 font-mono">
                {phase.oscillator > 0 ? "+" : ""}
                {fmt(phase.oscillator)}
              </span>
            )}
          </Badge>
          {phase.in_compression && phase.phase !== "compression" && (
            <span className="text-[9px] text-amber-400">SQ</span>
          )}
        </div>
      ))}
    </div>
  )
}
