"use client"

import { useMemo } from "react"
import { Badge } from "@/components/ui/badge"
import type { ThemeTrackerResponse } from "@/lib/types"

interface ThemeTrackerTableProps {
  data: ThemeTrackerResponse | null
  onSectorClick: (sector: string) => void
  selectedSector: string | null
}

function rankColor(rank: number): string {
  if (rank <= 3) return "text-emerald-400"
  if (rank <= 6) return "text-emerald-700"
  if (rank <= 8) return "text-muted-foreground"
  return "text-red-400"
}

function hasDivergence(data: { rank_1d: number; rank_1w: number; rank_1m: number; rank_3m: number }): boolean {
  const ranks = [data.rank_1d, data.rank_1w, data.rank_1m, data.rank_3m].filter(
    (r): r is number => r != null
  )
  if (ranks.length < 2) return false
  const hasTop = ranks.some((r) => r <= 3)
  const hasBottom = ranks.some((r) => r >= 7)
  return hasTop && hasBottom
}

export function ThemeTrackerTable({ data, onSectorClick, selectedSector }: ThemeTrackerTableProps) {
  const sortedSectors = useMemo(() => {
    if (!data?.sectors) return []
    return Object.entries(data.sectors)
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => (a.rank_1d ?? 99) - (b.rank_1d ?? 99))
  }, [data])

  if (!data || sortedSectors.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">
        No theme tracker data available.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs">
            <th className="text-left py-2 px-3 font-medium">Sector</th>
            <th className="text-center py-2 px-2 font-medium">1D</th>
            <th className="text-center py-2 px-2 font-medium">1W</th>
            <th className="text-center py-2 px-2 font-medium">1M</th>
            <th className="text-center py-2 px-2 font-medium">3M</th>
            <th className="text-center py-2 px-2 font-medium">Stocks</th>
          </tr>
        </thead>
        <tbody>
          {sortedSectors.map((sector) => (
            <tr
              key={sector.name}
              onClick={() => onSectorClick(sector.name)}
              className={`border-b border-border/50 cursor-pointer transition-colors
                ${selectedSector === sector.name ? "bg-accent" : "hover:bg-muted/50"}`}
            >
              <td className="py-2 px-3 font-medium flex items-center gap-2">
                {sector.name}
                {hasDivergence(sector) && (
                  <Badge variant="outline" className="text-[9px] text-yellow-500 border-yellow-500/30">
                    Rotation
                  </Badge>
                )}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1d)}`}>
                #{sector.rank_1d}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1w)}`}>
                #{sector.rank_1w}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_1m)}`}>
                #{sector.rank_1m}
              </td>
              <td className={`text-center py-2 px-2 font-mono ${rankColor(sector.rank_3m)}`}>
                #{sector.rank_3m}
              </td>
              <td className="text-center py-2 px-2 text-muted-foreground">
                {sector.stock_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
