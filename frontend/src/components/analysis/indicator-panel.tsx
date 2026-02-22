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

function AtrCard({ data }: { data: TradePlanResponse }) {
  const atr = data.atr_levels
  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">ATR Levels</CardTitle>
          <Badge className={cn("text-[10px]", atrStatusColor(atr.atr_status))}>
            {atr.atr_status.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow label="Price" value={`$${fmt(atr.current_price)}`} />
        <DataRow label="PDC" value={`$${fmt(atr.pdc)}`} />
        <DataRow label="ATR(14)" value={fmt(atr.atr)} />
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
      </CardContent>
    </Card>
  )
}

function PhaseCard({ data }: { data: TradePlanResponse }) {
  const phase = data.phase_oscillator
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
      </CardContent>
    </Card>
  )
}

function PriceStructureCard({ data }: { data: TradePlanResponse }) {
  const ps = data.price_structure
  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Price Structure</CardTitle>
          <Badge
            className={cn(
              "text-[10px]",
              structuralBiasColor(ps.structural_bias)
            )}
          >
            {formatLabel(ps.structural_bias).toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRow label="PDH" value={`$${fmt(ps.pdh)}`} />
        <DataRow label="PDL" value={`$${fmt(ps.pdl)}`} />
        <DataRow label="PDC" value={`$${fmt(ps.pdc)}`} />
        <div className="my-2 h-px bg-border/50" />
        {ps.pmh != null && <DataRow label="PMH" value={`$${fmt(ps.pmh)}`} />}
        {ps.pml != null && <DataRow label="PML" value={`$${fmt(ps.pml)}`} />}
        <div className="my-2 h-px bg-border/50" />
        <DataRow label="Gap" value={formatLabel(ps.gap_scenario)} />
      </CardContent>
    </Card>
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
