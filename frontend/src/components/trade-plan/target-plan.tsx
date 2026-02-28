import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { Target } from "@/lib/daily-plan-types"

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

function TargetRow({
  index,
  target,
  direction,
}: {
  index: number
  target: Target
  direction: "up" | "down"
}) {
  const dirColor = direction === "up" ? "text-emerald-400" : "text-red-400"

  return (
    <div className="flex items-start justify-between gap-2 text-sm">
      <div className="flex items-start gap-2 min-w-0">
        <span className={cn("font-mono text-xs shrink-0 mt-0.5", dirColor)}>
          T{index + 1}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-medium">${fmt(target.price)}</span>
            <span className="text-xs text-muted-foreground truncate">
              {target.label}
            </span>
            {target.confluenceCount > 1 && (
              <Badge className="text-[9px] px-1 py-0 bg-purple-600/20 text-purple-400 border-purple-600/30">
                {target.confluenceCount}x
              </Badge>
            )}
          </div>
          {target.confluences.length > 0 && (
            <div className="text-[10px] text-muted-foreground mt-0.5 truncate">
              + {target.confluences.slice(0, 2).join(", ")}
              {target.confluences.length > 2 && ` +${target.confluences.length - 2} more`}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function TargetPlan({
  upside,
  downside,
}: {
  upside: Target[]
  downside: Target[]
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Upside */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-emerald-400">
          Upside Targets
        </span>
        {upside.length === 0 ? (
          <p className="text-xs text-muted-foreground">No upside levels</p>
        ) : (
          <div className="space-y-1.5">
            {upside.map((t, i) => (
              <TargetRow key={i} index={i} target={t} direction="up" />
            ))}
          </div>
        )}
      </div>

      {/* Downside */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-red-400">
          Downside Targets
        </span>
        {downside.length === 0 ? (
          <p className="text-xs text-muted-foreground">No downside levels</p>
        ) : (
          <div className="space-y-1.5">
            {downside.map((t, i) => (
              <TargetRow key={i} index={i} target={t} direction="down" />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
