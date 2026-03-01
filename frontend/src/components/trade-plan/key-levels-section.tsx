import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { InstrumentPlan } from "@/lib/daily-plan-types"
import type { StructuralBias, GapScenario } from "@/lib/types"

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

function biasLabel(bias: StructuralBias): string {
  switch (bias) {
    case "strongly_bullish": return "Strong Bull"
    case "bullish": return "Bullish"
    case "neutral": return "Neutral"
    case "bearish": return "Bearish"
    case "strongly_bearish": return "Strong Bear"
  }
}

function biasColor(bias: StructuralBias): string {
  switch (bias) {
    case "strongly_bullish": return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "bullish": return "bg-emerald-600/15 text-emerald-300 border-emerald-600/20"
    case "neutral": return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
    case "bearish": return "bg-red-600/15 text-red-300 border-red-600/20"
    case "strongly_bearish": return "bg-red-600/20 text-red-400 border-red-600/30"
  }
}

function gapLabel(gap: GapScenario): string {
  switch (gap) {
    case "gap_above_pdh": return "Gap Above PDH"
    case "gap_below_pdl": return "Gap Below PDL"
    case "gap_up_inside_range": return "Gap Up (Inside)"
    case "gap_down_inside_range": return "Gap Down (Inside)"
    case "no_gap": return "No Gap"
  }
}

function gapColor(gap: GapScenario): string {
  switch (gap) {
    case "gap_above_pdh": return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "gap_below_pdl": return "bg-red-600/20 text-red-400 border-red-600/30"
    case "gap_up_inside_range": return "bg-emerald-600/10 text-emerald-300 border-emerald-600/20"
    case "gap_down_inside_range": return "bg-red-600/10 text-red-300 border-red-600/20"
    case "no_gap": return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
  }
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
        {/* Premarket levels — cyan, auto-hide when null (SPX/after-close) */}
        <LevelRow label="PMH" value={ps.pmh} color="text-cyan-400" />
        <LevelRow label="PML" value={ps.pml} color="text-cyan-400" />
        {/* Premarket current price */}
        <LevelRow label="PM Price" value={ps.premarket_price} color="text-cyan-300" />
        {/* Structural Bias */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Bias</span>
          <Badge variant="outline" className={cn("text-[10px]", biasColor(ps.structural_bias))}>
            {biasLabel(ps.structural_bias)}
          </Badge>
        </div>
        {/* Gap Scenario */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Gap</span>
          <Badge variant="outline" className={cn("text-[10px]", gapColor(ps.gap_scenario))}>
            {gapLabel(ps.gap_scenario)}
          </Badge>
        </div>
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
