import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { InstrumentPlan } from "@/lib/daily-plan-types"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

function LevelRow({
  label,
  value,
  color,
}: {
  label: string
  value: number | null | undefined
  color?: string
}) {
  if (value == null) return null
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono font-medium", color ?? "text-foreground")}>
        ${fmt(value)}
      </span>
    </div>
  )
}

export function KeyLevelsSection({ plan }: { plan: InstrumentPlan }) {
  const atr = plan.daily.atr_levels
  const ps = plan.daily.price_structure
  const kp = plan.daily.key_pivots

  return (
    <div className="space-y-3">
      {/* ATR Triggers */}
      <div className="space-y-1">
        <span className="text-xs font-semibold text-muted-foreground">ATR Triggers</span>
        <LevelRow label="Call Trigger" value={atr.call_trigger} color="text-emerald-400" />
        <LevelRow label="Put Trigger" value={atr.put_trigger} color="text-red-400" />
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Trigger Box</span>
          <Badge
            variant="outline"
            className={cn(
              "text-[10px]",
              atr.trigger_box.inside
                ? "text-amber-400 border-amber-600/30"
                : "text-zinc-400 border-zinc-600/30"
            )}
          >
            {atr.trigger_box.inside ? "INSIDE" : "OUTSIDE"}
          </Badge>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">ATR Covered</span>
          <span
            className={cn(
              "font-mono text-xs",
              atr.atr_covered_pct >= 90
                ? "text-red-400"
                : atr.atr_covered_pct >= 60
                  ? "text-amber-400"
                  : "text-emerald-400"
            )}
          >
            {fmt(atr.atr_covered_pct, 1)}%
          </span>
        </div>
      </div>

      <div className="h-px bg-border/30" />

      {/* Price Structure */}
      <div className="space-y-1">
        <span className="text-xs font-semibold text-muted-foreground">Price Structure</span>
        <LevelRow label="PDH" value={ps.pdh} />
        <LevelRow label="PDL" value={ps.pdl} />
        <LevelRow label="PDC" value={ps.pdc} color="text-amber-400" />
      </div>

      <div className="h-px bg-border/30" />

      {/* Key Pivots */}
      {kp && (
        <div className="space-y-1">
          <span className="text-xs font-semibold text-muted-foreground">Key Pivots</span>
          <LevelRow label="PWH" value={kp.pwh} />
          <LevelRow label="PWL" value={kp.pwl} />
          <LevelRow label="PWC" value={kp.pwc} color="text-amber-400" />
          <LevelRow label="PMo H" value={kp.pmoh} />
          <LevelRow label="PMo L" value={kp.pmol} />
          <LevelRow label="PMo C" value={kp.pmoc} color="text-amber-400" />
          <LevelRow label="PQC" value={kp.pqc} color="text-amber-400" />
          <LevelRow label="PYC" value={kp.pyc} color="text-amber-400" />
        </div>
      )}
    </div>
  )
}
