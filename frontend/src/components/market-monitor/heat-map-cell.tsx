"use client"

import { cn } from "@/lib/utils"

interface HeatMapCellProps {
  count: number
  date: string
  direction: "up" | "down"
  min: number
  max: number
  selected: boolean
  onClick: () => void
}

function intensityColor(count: number, min: number, max: number, direction: "up" | "down"): string {
  if (max === min) return "bg-muted"
  const ratio = Math.min((count - min) / (max - min), 1)

  if (direction === "up") {
    if (ratio < 0.2) return "bg-muted"
    if (ratio < 0.4) return "bg-emerald-950"
    if (ratio < 0.6) return "bg-emerald-900"
    if (ratio < 0.8) return "bg-emerald-700"
    return "bg-emerald-500"
  } else {
    if (ratio < 0.2) return "bg-muted"
    if (ratio < 0.4) return "bg-red-950"
    if (ratio < 0.6) return "bg-red-900"
    if (ratio < 0.8) return "bg-red-700"
    return "bg-red-500"
  }
}

export function HeatMapCell({ count, date, direction, min, max, selected, onClick }: HeatMapCellProps) {
  return (
    <button
      onClick={onClick}
      title={`${date}: ${count} stocks`}
      className={cn(
        "w-10 h-8 text-xs font-mono rounded-sm transition-all cursor-pointer",
        "hover:ring-1 hover:ring-white/30",
        intensityColor(count, min, max, direction),
        selected && "ring-2 ring-white"
      )}
    >
      {count}
    </button>
  )
}
