"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type {
  TradePlanResponse,
  AtrStatus,
  RibbonState,
  Phase,
  StructuralBias,
  ConvictionArrow,
  MtfRibbonEntry,
  MtfPhaseEntry,
  MeanReversionType,
  OpenGap,
} from "@/lib/types"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

// --- Color helpers ---

function atrStatusColor(status: AtrStatus): string {
  switch (status) {
    case "green":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "orange":
      return "bg-amber-600/20 text-amber-400 border-amber-600/30"
    case "red":
      return "bg-red-600/20 text-red-400 border-red-600/30"
  }
}

function ribbonStateColor(state: RibbonState): string {
  switch (state) {
    case "bullish":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "bearish":
      return "bg-red-600/20 text-red-400 border-red-600/30"
    case "chopzilla":
      return "bg-yellow-600/20 text-yellow-400 border-yellow-600/30"
  }
}

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

function biasColor(candle: string): string {
  switch (candle) {
    case "green":
      return "bg-emerald-500"
    case "blue":
      return "bg-blue-500"
    case "orange":
      return "bg-orange-500"
    case "red":
      return "bg-red-500"
    default:
      return "bg-zinc-500"
  }
}

function structuralBiasColor(bias: StructuralBias): string {
  switch (bias) {
    case "strongly_bullish":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "bullish":
      return "bg-emerald-600/15 text-emerald-300 border-emerald-600/20"
    case "neutral":
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
    case "bearish":
      return "bg-red-600/15 text-red-300 border-red-600/20"
    case "strongly_bearish":
      return "bg-red-600/20 text-red-400 border-red-600/30"
  }
}

function formatLabel(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

// --- Sub-components ---

function DataRow({
  label,
  value,
  className,
}: {
  label: string
  value: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-center justify-between text-sm", className)}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  )
}

// --- Cards ---

const MODE_ATR_LABEL: Record<string, string> = {
  day: "Daily ATR(14)",
  multiday: "Weekly ATR(14)",
  swing: "Monthly ATR(14)",
  position: "Quarterly ATR(14)",
}

const MODE_PDC_LABEL: Record<string, string> = {
  day: "Prev Day Close",
  multiday: "Prev Week Close",
  swing: "Prev Month Close",
  position: "Prev Quarter Close",
}

const MODE_PDC_LABEL_CC: Record<string, string> = {
  day: "Day Close",
  multiday: "Week Close",
  swing: "Month Close",
  position: "Quarter Close",
}

function atrCoveredColor(pct: number): string {
  if (pct >= 90) return "text-red-400"
  if (pct >= 60) return "text-amber-400"
  return "text-emerald-400"
}

function getNextTarget(
  atr: TradePlanResponse["atr_levels"]
): { label: string; price: number; color: string } | null {
  const levels = atr.levels
  if (!levels) return null

  switch (atr.price_position) {
    case "above_call_trigger":
      return levels.golden_gate_bull
        ? { label: "Golden Gate ↑", price: levels.golden_gate_bull.price, color: "text-teal-400" }
        : null
    case "above_golden_gate":
      return levels.mid_range_bull
        ? { label: "Mid-Range ↑", price: levels.mid_range_bull.price, color: "text-blue-400" }
        : null
    case "above_mid_range":
      return levels.full_range_bull
        ? { label: "Full Range ↑", price: levels.full_range_bull.price, color: "text-purple-400" }
        : null
    case "below_put_trigger":
      return levels.golden_gate_bear
        ? { label: "Golden Gate ↓", price: levels.golden_gate_bear.price, color: "text-teal-400" }
        : null
    case "below_golden_gate":
      return levels.mid_range_bear
        ? { label: "Mid-Range ↓", price: levels.mid_range_bear.price, color: "text-blue-400" }
        : null
    case "below_mid_range":
      return levels.full_range_bear
        ? { label: "Full Range ↓", price: levels.full_range_bear.price, color: "text-purple-400" }
        : null
    default:
      return null
  }
}

function AtrCard({ data }: { data: TradePlanResponse }) {
  const atr = data.atr_levels
  const ucc = data.use_current_close
  const modeLabel = atr.trading_mode_label || "Day"
  const atrLabel = MODE_ATR_LABEL[atr.trading_mode] || "ATR(14)"
  const pdcLabel = ucc
    ? (MODE_PDC_LABEL_CC[atr.trading_mode] || "Close")
    : (MODE_PDC_LABEL[atr.trading_mode] || "PDC")
  const levels = atr.levels || {}
  const nextTarget = getNextTarget(atr)

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{modeLabel} Levels</CardTitle>
          <div className="flex items-center gap-1.5">
            {ucc && (
              <Badge className="text-[10px] bg-blue-600/20 text-blue-400 border-blue-600/30">
                CURRENT CLOSE
              </Badge>
            )}
            <Badge className={cn("text-[10px]", atrStatusColor(atr.atr_status))}>
              {atr.atr_status.toUpperCase()}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow label="Price" value={`$${fmt(atr.current_price)}`} />
        <DataRow label={pdcLabel} value={`$${fmt(atr.pdc)}`} />
        <DataRow label={atrLabel} value={fmt(atr.atr)} />
        <DataRow
          label="ATR Covered"
          value={
            <span className={cn("font-mono", atrCoveredColor(atr.atr_covered_pct))}>
              {fmt(atr.atr_covered_pct, 1)}%
            </span>
          }
        />
        <div className="my-2 h-px bg-border/50" />
        <DataRow
          label="Call Trigger"
          value={
            <span className="text-emerald-400">${fmt(atr.call_trigger)}</span>
          }
        />
        <DataRow
          label="Put Trigger"
          value={<span className="text-red-400">${fmt(atr.put_trigger)}</span>}
        />
        <div className="my-2 h-px bg-border/50" />
        {levels.golden_gate_bull && (
          <DataRow
            label="Golden Gate ↑"
            value={<span className="text-teal-400">${fmt(levels.golden_gate_bull.price)}</span>}
          />
        )}
        {levels.golden_gate_bear && (
          <DataRow
            label="Golden Gate ↓"
            value={<span className="text-orange-400">${fmt(levels.golden_gate_bear.price)}</span>}
          />
        )}
        {nextTarget && (
          <>
            <div className="my-2 h-px bg-border/50" />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground flex items-center gap-1">
                <span className="text-primary">→</span> Next Target
              </span>
              <span className={cn("font-mono font-semibold", nextTarget.color)}>
                {nextTarget.label} ${fmt(nextTarget.price)}
              </span>
            </div>
          </>
        )}
        <div className="my-2 h-px bg-border/50" />
        {levels.mid_range_bull && (
          <DataRow
            label="Mid-Range ↑"
            value={<span className="text-blue-400">${fmt(levels.mid_range_bull.price)}</span>}
          />
        )}
        {levels.mid_range_bear && (
          <DataRow
            label="Mid-Range ↓"
            value={<span className="text-blue-400">${fmt(levels.mid_range_bear.price)}</span>}
          />
        )}
        {levels.full_range_bull && (
          <DataRow
            label="Full Range ↑"
            value={<span className="text-purple-400">${fmt(levels.full_range_bull.price)}</span>}
          />
        )}
        {levels.full_range_bear && (
          <DataRow
            label="Full Range ↓"
            value={<span className="text-purple-400">${fmt(levels.full_range_bear.price)}</span>}
          />
        )}
        <div className="my-2 h-px bg-border/50" />
        <DataRow label="Trend" value={formatLabel(atr.trend)} />
        <DataRow
          label="Trigger Box"
          value={
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
          }
        />
      </CardContent>
    </Card>
  )
}

function RibbonCard({ data }: { data: TradePlanResponse }) {
  const ribbon = data.pivot_ribbon
  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Pivot Ribbon</CardTitle>
          <Badge
            className={cn("text-[10px]", ribbonStateColor(ribbon.ribbon_state))}
          >
            {ribbon.ribbon_state.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow
          label="Bias Candle"
          value={
            <div className="flex items-center gap-2">
              <div className={cn("size-3 rounded-full", biasColor(ribbon.bias_candle))} />
              <span className="capitalize">{ribbon.bias_candle}</span>
            </div>
          }
        />
        <div className="my-2 h-px bg-border/50" />
        <DataRow label="EMA 8" value={fmt(ribbon.ema8)} />
        <DataRow label="EMA 13" value={fmt(ribbon.ema13)} />
        <DataRow label="EMA 21" value={fmt(ribbon.ema21)} />
        <DataRow label="EMA 48" value={fmt(ribbon.ema48)} />
        <DataRow label="EMA 200" value={fmt(ribbon.ema200)} />
        <div className="my-2 h-px bg-border/50" />
        <DataRow
          label="Above 200 EMA"
          value={
            <Badge
              variant="outline"
              className={cn(
                "text-[10px]",
                ribbon.above_200ema
                  ? "text-emerald-400 border-emerald-600/30"
                  : "text-red-400 border-red-600/30"
              )}
            >
              {ribbon.above_200ema ? "YES" : "NO"}
            </Badge>
          }
        />
        <DataRow
          label="Compression"
          value={
            ribbon.in_compression ? (
              <Badge className="text-[10px] bg-amber-600/20 text-amber-400 border-amber-600/30">
                COMPRESSED
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">No</span>
            )
          }
        />
        <DataRow
          label="13/48 Conviction"
          value={convictionLabel(ribbon.last_conviction_type, ribbon.last_conviction_bars_ago)}
        />
        {data.mtf_ribbons && Object.keys(data.mtf_ribbons).length > 0 && (
          <>
            <div className="my-2 h-px bg-border/50" />
            <MtfRibbonRow
              currentTf={data.timeframe}
              currentState={ribbon.ribbon_state}
              mtfRibbons={data.mtf_ribbons}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

const TF_LABELS: Record<string, string> = {
  "1m": "1m", "5m": "5m", "15m": "15m",
  "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W",
}

function mtfDotColor(state: RibbonState): string {
  switch (state) {
    case "bullish":
      return "bg-emerald-500"
    case "bearish":
      return "bg-red-500"
    case "chopzilla":
      return "bg-yellow-500"
  }
}

function phaseDotColor(phase: Phase): string {
  switch (phase) {
    case "green":
      return "bg-emerald-500"
    case "red":
      return "bg-red-500"
    case "compression":
      return "bg-zinc-400"
  }
}

function meanReversionLabel(mrType: MeanReversionType | null, barsAgo: number | null): React.ReactNode {
  if (!mrType || barsAgo == null) {
    return <span className="text-xs text-muted-foreground">None</span>
  }
  const isBottom = mrType === "leaving_accumulation" || mrType === "leaving_extreme_down"
  const label = isBottom
    ? (mrType === "leaving_extreme_down" ? "EXT BOT" : "ACCUM")
    : (mrType === "leaving_extreme_up" ? "EXT TOP" : "DIST")
  const barsText = barsAgo === 0 ? "now" : `${barsAgo}b ago`
  return (
    <Badge className="text-[10px] bg-yellow-600/20 text-yellow-400 border-yellow-600/30">
      {label} {barsText}
    </Badge>
  )
}

function MtfRibbonRow({
  currentTf,
  currentState,
  mtfRibbons,
}: {
  currentTf: string
  currentState: RibbonState
  mtfRibbons: Record<string, MtfRibbonEntry>
}) {
  const entries = [
    { tf: currentTf, state: currentState, isCurrent: true },
    ...Object.entries(mtfRibbons).map(([tf, r]) => ({
      tf,
      state: r.ribbon_state,
      isCurrent: false,
    })),
  ]

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">MTF</span>
      <div className="flex items-center gap-1">
        {entries.map(({ tf, state, isCurrent }) => (
          <div
            key={tf}
            className={cn(
              "flex items-center gap-1 rounded px-1.5 py-0.5",
              isCurrent ? "ring-1 ring-primary/40 bg-primary/5" : "bg-muted/30"
            )}
          >
            <div className={cn("size-2 rounded-full", mtfDotColor(state))} />
            <span className="text-[10px] font-mono">{TF_LABELS[tf] ?? tf}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function convictionLabel(arrow: ConvictionArrow, barsAgo: number | null): React.ReactNode {
  if (!arrow || barsAgo == null) {
    return <span className="text-xs text-muted-foreground">None</span>
  }
  const label = arrow === "bullish_crossover" ? "BULL" : "BEAR"
  const barsText = barsAgo === 0 ? "now" : `${barsAgo}b ago`
  const colors = arrow === "bullish_crossover"
    ? "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    : "bg-red-600/20 text-red-400 border-red-600/30"
  return (
    <Badge className={cn("text-[10px]", colors)}>
      {label} {barsText}
    </Badge>
  )
}

function PhaseCard({ data }: { data: TradePlanResponse }) {
  const phase = data.phase_oscillator
  const mtfPhases = data.mtf_phases
  const hasMtf = mtfPhases && Object.keys(mtfPhases).length > 0

  // Nested squeeze: current TF + all higher TFs in compression
  const nestedSqueeze = hasMtf
    && phase.in_compression
    && Object.values(mtfPhases).every((p) => p.in_compression)

  // Distribution confluence: current + all MTF in distribution or extreme_up
  const distZones = new Set(["distribution", "extreme_up"])
  const accumZones = new Set(["accumulation", "extreme_down"])
  const allDistribution = hasMtf
    && distZones.has(phase.current_zone)
    && Object.values(mtfPhases).every((p) => distZones.has(p.current_zone))
  const allAccumulation = hasMtf
    && accumZones.has(phase.current_zone)
    && Object.values(mtfPhases).every((p) => accumZones.has(p.current_zone))

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Phase Oscillator</CardTitle>
          <Badge className={cn("text-[10px]", phaseColor(phase.phase))}>
            {phase.phase.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow
          label="Oscillator"
          value={
            <span
              className={cn(
                "font-mono",
                phase.oscillator > 0 ? "text-emerald-400" : "text-red-400"
              )}
            >
              {phase.oscillator > 0 ? "+" : ""}
              {fmt(phase.oscillator)}
            </span>
          }
        />
        <DataRow label="Zone" value={formatLabel(phase.current_zone)} />
        <DataRow
          label="Compression"
          value={
            phase.in_compression ? (
              <Badge className="text-[10px] bg-amber-600/20 text-amber-400 border-amber-600/30">
                SQUEEZED
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">No</span>
            )
          }
        />
        <DataRow
          label="Mean Reversion"
          value={meanReversionLabel(phase.last_mr_type, phase.last_mr_bars_ago)}
        />
        {hasMtf && (
          <>
            <div className="my-2 h-px bg-border/50" />
            <MtfPhaseRow
              currentTf={data.timeframe}
              currentPhase={phase.phase}
              mtfPhases={mtfPhases}
            />
            {nestedSqueeze && (
              <div className="flex justify-end">
                <Badge className="text-[10px] bg-purple-600/20 text-purple-400 border-purple-600/30">
                  NESTED SQUEEZE
                </Badge>
              </div>
            )}
            {allDistribution && (
              <div className="flex justify-end">
                <Badge className="text-[10px] bg-yellow-600/20 text-yellow-400 border-yellow-600/30">
                  MTF DISTRIBUTION
                </Badge>
              </div>
            )}
            {allAccumulation && (
              <div className="flex justify-end">
                <Badge className="text-[10px] bg-yellow-600/20 text-yellow-400 border-yellow-600/30">
                  MTF ACCUMULATION
                </Badge>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function MtfPhaseRow({
  currentTf,
  currentPhase,
  mtfPhases,
}: {
  currentTf: string
  currentPhase: Phase
  mtfPhases: Record<string, MtfPhaseEntry>
}) {
  const entries = [
    { tf: currentTf, phase: currentPhase, osc: null as number | null, isCurrent: true },
    ...Object.entries(mtfPhases).map(([tf, p]) => ({
      tf,
      phase: p.phase,
      osc: p.oscillator,
      isCurrent: false,
    })),
  ]

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">MTF</span>
      <div className="flex items-center gap-1">
        {entries.map(({ tf, phase, osc, isCurrent }) => (
          <div
            key={tf}
            className={cn(
              "flex items-center gap-1 rounded px-1.5 py-0.5",
              isCurrent ? "ring-1 ring-primary/40 bg-primary/5" : "bg-muted/30"
            )}
            title={osc != null ? `${fmt(osc)}` : undefined}
          >
            <div className={cn("size-2 rounded-full", phaseDotColor(phase))} />
            <span className="text-[10px] font-mono">{TF_LABELS[tf] ?? tf}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function getPivotAlignment(
  ps: TradePlanResponse["price_structure"],
  kp: TradePlanResponse["key_pivots"],
): { label: string; color: string; greenCount: number; total: number } {
  // Check stacking: PDC >= PWC >= PMoC >= PQC >= PYC
  const pivots: (number | null | undefined)[] = [
    ps.pdc, kp?.pwc, kp?.pmoc, kp?.pqc, kp?.pyc,
  ]
  const valid = pivots.filter((v): v is number => v != null)
  if (valid.length < 2) return { label: "N/A", color: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30", greenCount: 0, total: 0 }

  let greenCount = 0
  for (let i = 0; i < valid.length - 1; i++) {
    if (valid[i] >= valid[i + 1]) greenCount++
  }
  const total = valid.length - 1

  if (greenCount === total) {
    return { label: "ALIGNED", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30", greenCount, total }
  }
  if (greenCount === 0) {
    return { label: "BEARISH", color: "bg-red-600/20 text-red-400 border-red-600/30", greenCount, total }
  }
  return { label: "CHOPPY", color: "bg-amber-600/20 text-amber-400 border-amber-600/30", greenCount, total }
}

function PriceStructureCard({ data }: { data: TradePlanResponse }) {
  const ps = data.price_structure
  const kp = data.key_pivots
  const alignment = getPivotAlignment(ps, kp)

  // Build ordered pivot pairs for coloring: each pair checks higher >= lower TF
  const pivotPairs: { value: number; nextValue: number | null }[] = []
  const orderedPivots: (number | null | undefined)[] = [
    ps.pdc, kp?.pwc, kp?.pmoc, kp?.pqc, kp?.pyc,
  ]
  for (let i = 0; i < orderedPivots.length; i++) {
    const v = orderedPivots[i]
    if (v == null) continue
    const next = orderedPivots.slice(i + 1).find((n): n is number => n != null) ?? null
    pivotPairs.push({ value: v, nextValue: next })
  }

  // Map each pivot value to green/red based on stacking with next lower TF
  const pivotColor = (value: number | null | undefined): string => {
    if (value == null) return "text-amber-400"
    const pair = pivotPairs.find((p) => p.value === value)
    if (!pair || pair.nextValue == null) return "text-emerald-400" // lowest TF or only pivot
    return pair.value >= pair.nextValue ? "text-emerald-400" : "text-red-400"
  }

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Price Structure</CardTitle>
          <div className="flex items-center gap-1.5">
            <Badge className={cn("text-[10px]", structuralBiasColor(ps.structural_bias))}>
              {formatLabel(ps.structural_bias).toUpperCase()}
            </Badge>
            <Badge className={cn("text-[10px]", alignment.color)}>
              {alignment.label}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow label="PDH" value={`$${fmt(ps.pdh)}`} />
        <DataRow label="PDL" value={`$${fmt(ps.pdl)}`} />
        <PivotRow label="PDC Pivot" value={ps.pdc} color={pivotColor(ps.pdc)} />
        <div className="my-2 h-px bg-border/50" />
        {kp?.pwh != null && <DataRow label="PWH" value={`$${fmt(kp.pwh)}`} />}
        {kp?.pwl != null && <DataRow label="PWL" value={`$${fmt(kp.pwl)}`} />}
        {kp?.pwc != null && <PivotRow label="PWC Pivot" value={kp.pwc} color={pivotColor(kp.pwc)} />}
        <div className="my-2 h-px bg-border/50" />
        {kp?.pmoh != null && <DataRow label="Prev Mo High" value={`$${fmt(kp.pmoh)}`} />}
        {kp?.pmol != null && <DataRow label="Prev Mo Low" value={`$${fmt(kp.pmol)}`} />}
        {kp?.pmoc != null && <PivotRow label="Prev Mo Pivot" value={kp.pmoc} color={pivotColor(kp.pmoc)} />}
        <div className="my-2 h-px bg-border/50" />
        {kp?.pqc != null && <PivotRow label="Prev Qtr Pivot" value={kp.pqc} color={pivotColor(kp.pqc)} />}
        {kp?.pyc != null && <PivotRow label="Prev Yr Pivot" value={kp.pyc} color={pivotColor(kp.pyc)} />}
        <div className="my-2 h-px bg-border/50" />
        <DataRow label="Gap" value={formatLabel(ps.gap_scenario)} />
        {data.open_gaps && data.open_gaps.length > 0 && (
          <>
            <div className="my-2 h-px bg-border/50" />
            <OpenGapsSection gaps={data.open_gaps} currentPrice={ps.current_price} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

function OpenGapsSection({ gaps, currentPrice }: { gaps: OpenGap[]; currentPrice: number }) {
  // Split into gaps above and below current price
  const above = gaps.filter((g) => g.gap_low > currentPrice)
  const below = gaps.filter((g) => g.gap_high < currentPrice)
  const nearest = gaps.reduce<OpenGap | null>((best, g) => {
    const dist = Math.min(Math.abs(g.gap_high - currentPrice), Math.abs(g.gap_low - currentPrice))
    if (!best) return g
    const bestDist = Math.min(Math.abs(best.gap_high - currentPrice), Math.abs(best.gap_low - currentPrice))
    return dist < bestDist ? g : best
  }, null)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Open Gaps (6mo)</span>
        <div className="flex items-center gap-1.5">
          {above.length > 0 && (
            <Badge className="text-[10px] bg-emerald-600/20 text-emerald-400 border-emerald-600/30">
              {above.length}↑
            </Badge>
          )}
          {below.length > 0 && (
            <Badge className="text-[10px] bg-red-600/20 text-red-400 border-red-600/30">
              {below.length}↓
            </Badge>
          )}
        </div>
      </div>
      {gaps.map((g) => {
        const isNearest = g === nearest
        const isAbove = g.gap_low > currentPrice
        const color = g.type === "gap_up" ? "text-emerald-400" : "text-red-400"
        return (
          <div
            key={`${g.date}-${g.type}`}
            className={cn(
              "flex items-center justify-between text-xs",
              isNearest && "bg-primary/5 rounded px-1 -mx-1"
            )}
          >
            <span className="text-muted-foreground flex items-center gap-1">
              {isNearest && <span className="text-primary text-[10px]">→</span>}
              {g.date.slice(5)}
              <span className={cn("text-[10px]", color)}>
                {g.type === "gap_up" ? "↑" : "↓"}
              </span>
            </span>
            <span className={cn("font-mono", color)}>
              ${fmt(g.gap_low)}–${fmt(g.gap_high)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function PivotRow({ label, value, color }: { label: string; value: number | null; color?: string }) {
  if (value == null) return null
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono font-medium", color ?? "text-amber-400")}>${fmt(value)}</span>
    </div>
  )
}

// --- Main Panel ---

interface IndicatorPanelProps {
  data: TradePlanResponse
}

export function IndicatorPanel({ data }: IndicatorPanelProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <AtrCard data={data} />
      <RibbonCard data={data} />
      <PhaseCard data={data} />
      <PriceStructureCard data={data} />
    </div>
  )
}
