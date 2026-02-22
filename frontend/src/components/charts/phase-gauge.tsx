import { cn } from "@/lib/utils"
import type { Phase } from "@/lib/types"

/**
 * Phase oscillator gauge: a horizontal bar from -100 to +100 with colored zones
 * and a marker for the current value.
 *
 * Zones (left to right):
 *   extreme_down  (-100 to -61.8)  red
 *   accumulation  (-61.8 to -23.6) orange
 *   neutral_down  (-23.6 to 0)     gray
 *   neutral_up    (0 to 23.6)      gray
 *   distribution  (23.6 to 61.8)   orange
 *   extreme_up    (61.8 to 100)    red
 */

interface PhaseGaugeProps {
  oscillator: number
  phase: Phase
}

function phaseLabel(phase: Phase): string {
  switch (phase) {
    case "green":
      return "Firing Up"
    case "red":
      return "Firing Down"
    case "compression":
      return "Compression"
  }
}

function phaseLabelColor(phase: Phase): string {
  switch (phase) {
    case "green":
      return "text-emerald-400"
    case "red":
      return "text-red-400"
    case "compression":
      return "text-zinc-400"
  }
}

// Convert oscillator value (-100..100) to percentage position (0..100%)
function valueToPercent(value: number): number {
  const clamped = Math.max(-100, Math.min(100, value))
  return ((clamped + 100) / 200) * 100
}

// Zone boundaries as percentages of the 0-100% bar
const ZONES = [
  { from: 0, to: 19.1, color: "bg-red-600/60", label: "Extreme Down" },          // -100 to -61.8
  { from: 19.1, to: 38.2, color: "bg-orange-500/50", label: "Accumulation" },     // -61.8 to -23.6
  { from: 38.2, to: 50, color: "bg-zinc-600/40", label: "Neutral Down" },         // -23.6 to 0
  { from: 50, to: 61.8, color: "bg-zinc-600/40", label: "Neutral Up" },           // 0 to 23.6
  { from: 61.8, to: 80.9, color: "bg-orange-500/50", label: "Distribution" },     // 23.6 to 61.8
  { from: 80.9, to: 100, color: "bg-red-600/60", label: "Extreme Up" },           // 61.8 to 100
]

export function PhaseGauge({ oscillator, phase }: PhaseGaugeProps) {
  const markerPct = valueToPercent(oscillator)

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className={cn("text-sm font-medium", phaseLabelColor(phase))}>
          {phaseLabel(phase)}
        </span>
        <span
          className={cn(
            "text-sm font-mono font-semibold",
            oscillator > 0 ? "text-emerald-400" : oscillator < 0 ? "text-red-400" : "text-zinc-400"
          )}
        >
          {oscillator > 0 ? "+" : ""}
          {oscillator.toFixed(1)}
        </span>
      </div>

      {/* Gauge bar */}
      <div className="relative h-6 w-full rounded-md overflow-hidden flex">
        {ZONES.map((zone) => (
          <div
            key={zone.label}
            className={cn("h-full", zone.color)}
            style={{ width: `${zone.to - zone.from}%` }}
          />
        ))}

        {/* Marker */}
        <div
          className="absolute top-0 h-full w-0.5 bg-white shadow-[0_0_6px_rgba(255,255,255,0.6)]"
          style={{ left: `${markerPct}%` }}
        >
          {/* Marker head */}
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 size-2 rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.8)]" />
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 size-2 rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.8)]" />
        </div>
      </div>

      {/* Scale labels */}
      <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
        <span>-100</span>
        <span>-61.8</span>
        <span>-23.6</span>
        <span>0</span>
        <span>+23.6</span>
        <span>+61.8</span>
        <span>+100</span>
      </div>
    </div>
  )
}
