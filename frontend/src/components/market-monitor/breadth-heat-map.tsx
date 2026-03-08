"use client"

import { useMemo } from "react"
import type { BreadthSnapshotSummary } from "@/lib/types"
import { HeatMapCell } from "./heat-map-cell"

interface SelectedCell {
  scanKey: string
  date: string
}

interface BreadthHeatMapProps {
  snapshots: BreadthSnapshotSummary[]
  selectedCell: SelectedCell | null
  onCellClick: (scanKey: string, date: string) => void
}

const SCAN_GROUPS = [
  {
    label: "Daily",
    rows: [
      { key: "4pct_up_1d", label: "\u25B2 4%", direction: "up" as const },
      { key: "4pct_down_1d", label: "\u25BC 4%", direction: "down" as const },
    ],
  },
  {
    label: "Monthly (20d)",
    rows: [
      { key: "25pct_up_20d", label: "\u25B2 25%", direction: "up" as const },
      { key: "25pct_down_20d", label: "\u25BC 25%", direction: "down" as const },
      { key: "50pct_up_20d", label: "\u25B2 50%", direction: "up" as const },
      { key: "50pct_down_20d", label: "\u25BC 50%", direction: "down" as const },
    ],
  },
  {
    label: "Intermediate (34d)",
    rows: [
      { key: "13pct_up_34d", label: "\u25B2 13%", direction: "up" as const },
      { key: "13pct_down_34d", label: "\u25BC 13%", direction: "down" as const },
    ],
  },
  {
    label: "Quarterly (65d)",
    rows: [
      { key: "25pct_up_65d", label: "\u25B2 25%", direction: "up" as const },
      { key: "25pct_down_65d", label: "\u25BC 25%", direction: "down" as const },
    ],
  },
]

export function BreadthHeatMap({ snapshots, selectedCell, onCellClick }: BreadthHeatMapProps) {
  // Precompute min/max per scan row for color scaling
  const ranges = useMemo(() => {
    const r: Record<string, { min: number; max: number }> = {}
    for (const group of SCAN_GROUPS) {
      for (const row of group.rows) {
        const values = snapshots.map((s) => s.scans[row.key] ?? 0)
        r[row.key] = {
          min: Math.min(...values),
          max: Math.max(...values),
        }
      }
    }
    return r
  }, [snapshots])

  if (snapshots.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-8 text-center">
        No breadth data available. Run a compute or backfill first.
      </div>
    )
  }

  return (
    <div className="space-y-1 overflow-x-auto">
      {SCAN_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium px-1 py-0.5">
            {group.label}
          </div>
          {group.rows.map((row) => (
            <div key={row.key} className="flex items-center gap-0.5">
              <div className="w-16 text-xs text-muted-foreground font-mono shrink-0">
                {row.label}
              </div>
              <div className="flex gap-0.5">
                {snapshots.map((snap) => (
                  <HeatMapCell
                    key={`${row.key}-${snap.date}`}
                    count={snap.scans[row.key] ?? 0}
                    date={snap.date}
                    direction={row.direction}
                    min={ranges[row.key]?.min ?? 0}
                    max={ranges[row.key]?.max ?? 1}
                    selected={
                      selectedCell?.scanKey === row.key && selectedCell?.date === snap.date
                    }
                    onClick={() => onCellClick(row.key, snap.date)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
