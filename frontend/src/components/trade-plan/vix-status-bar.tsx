import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { VixSnapshot } from "@/lib/daily-plan-types"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

export function VixStatusBar({ vix }: { vix: VixSnapshot }) {
  const trendColor =
    vix.trend === "bullish"
      ? "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
      : vix.trend === "bearish"
        ? "bg-red-600/20 text-red-400 border-red-600/30"
        : "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"

  const phaseColor =
    vix.phase === "green"
      ? "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
      : vix.phase === "red"
        ? "bg-red-600/20 text-red-400 border-red-600/30"
        : "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"

  // VIX color: green when low (good for bulls), red when high
  const priceColor =
    vix.price < 17
      ? "text-emerald-400"
      : vix.price < 20
        ? "text-amber-400"
        : "text-red-400"

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border/50 bg-card/50 px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">VIX</span>
        <span className={cn("text-lg font-mono font-bold", priceColor)}>
          {fmt(vix.price)}
        </span>
      </div>
      {/* VIX premarket data — shows delta from close */}
      {vix.premktPrice != null && vix.price > 0 && (
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground">PM:</span>
          <span className={cn("font-mono text-sm font-medium", priceColor)}>
            {fmt(vix.premktPrice)}
          </span>
          <span className={cn("text-xs font-mono",
            // For VIX: rising = red (vol expanding), falling = green (vol contracting)
            vix.premktPrice > vix.price ? "text-red-400" : "text-emerald-400"
          )}>
            {vix.premktPrice > vix.price ? "▲" : "▼"}
            {fmt(Math.abs(vix.premktPrice - vix.price))}
          </span>
        </div>
      )}
      <Badge className={cn("text-[10px]", trendColor)}>
        {vix.trend.toUpperCase()}
      </Badge>
      <Badge className={cn("text-[10px]", phaseColor)}>
        {vix.phase.toUpperCase()}
      </Badge>
      <span className="text-xs text-muted-foreground">{vix.keyLevel}</span>
    </div>
  )
}
