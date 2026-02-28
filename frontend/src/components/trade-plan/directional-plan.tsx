import { cn } from "@/lib/utils"
import type { InstrumentPlan } from "@/lib/daily-plan-types"

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

export function DirectionalPlan({
  instruments,
}: {
  instruments: InstrumentPlan[]
}) {
  if (instruments.length === 0) return null

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-2">
      {/* Upside */}
      <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
        <span className="text-sm font-semibold text-emerald-400 w-20 shrink-0">
          Upside
        </span>
        <div className="flex flex-wrap gap-x-6 gap-y-1">
          {instruments.map((inst) => {
            const entry = inst.daily.atr_levels.call_trigger
            const targets = inst.targets.upside
            return (
              <div key={inst.ticker} className="flex items-center gap-1.5 text-sm">
                <span className="font-medium">{inst.displayName}</span>
                <span className="font-mono text-emerald-400">
                  ${fmt(entry)}c
                </span>
                {targets.map((t, i) => (
                  <span key={i} className="text-muted-foreground">
                    <span className="text-xs mx-0.5">{"\u2192"}</span>
                    <span className={cn(
                      "font-mono",
                      t.confluenceCount > 1 ? "text-emerald-300 font-semibold" : "text-foreground"
                    )}>
                      {fmt(t.price)}
                    </span>
                  </span>
                ))}
              </div>
            )
          })}
        </div>
      </div>

      {/* Downside */}
      <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
        <span className="text-sm font-semibold text-red-400 w-20 shrink-0">
          Downside
        </span>
        <div className="flex flex-wrap gap-x-6 gap-y-1">
          {instruments.map((inst) => {
            const entry = inst.daily.atr_levels.put_trigger
            const targets = inst.targets.downside
            return (
              <div key={inst.ticker} className="flex items-center gap-1.5 text-sm">
                <span className="font-medium">{inst.displayName}</span>
                <span className="font-mono text-red-400">
                  ${fmt(entry)}p
                </span>
                {targets.map((t, i) => (
                  <span key={i} className="text-muted-foreground">
                    <span className="text-xs mx-0.5">{"\u2192"}</span>
                    <span className={cn(
                      "font-mono",
                      t.confluenceCount > 1 ? "text-red-300 font-semibold" : "text-foreground"
                    )}>
                      {fmt(t.price)}
                    </span>
                  </span>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
