import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

/**
 * Transform backend period-keyed theme tracker data into frontend sector-keyed format.
 *
 * Backend format (per period):
 *   { "1d": [{ sector, gainers, losers, net }, ...], "1w": [...], ... }
 *
 * Frontend format (per sector):
 *   { "Technology": { rank_1d: 1, gainers_1d: 10, losers_1d: 3, net_1d: 7, ... stock_count: 30 }, ... }
 */
function pivotThemeTracker(
  raw: Record<string, Array<{ sector: string; gainers: number; losers: number; net: number }>>,
  sectorCounts: Record<string, number>,
) {
  const sectors: Record<string, Record<string, number>> = {}
  const periods = ["1d", "1w", "1m", "3m"] as const

  for (const period of periods) {
    const ranked = raw[period]
    if (!Array.isArray(ranked)) continue

    ranked.forEach((entry, idx) => {
      if (!sectors[entry.sector]) sectors[entry.sector] = {}
      const s = sectors[entry.sector]
      s[`rank_${period}`] = idx + 1
      s[`gainers_${period}`] = entry.gainers
      s[`losers_${period}`] = entry.losers
      s[`net_${period}`] = entry.net
      s.stock_count = sectorCounts[entry.sector] ?? (entry.gainers + entry.losers)
    })
  }

  return sectors
}

export async function GET(request: NextRequest) {
  const dateParam = request.nextUrl.searchParams.get("date")

  const supabase = createServerClient()

  let query = supabase
    .from("breadth_snapshots")
    .select("date, theme_tracker")

  if (dateParam) {
    query = query.eq("date", dateParam)
  } else {
    query = query.order("date", { ascending: false }).limit(1)
  }

  const { data, error } = await query.single()

  if (error || !data) {
    return NextResponse.json(
      { error: "No snapshot found" },
      { status: 404 },
    )
  }

  // Get actual stock counts per sector from monitor_universe
  const { data: univRows } = await supabase
    .from("monitor_universe")
    .select("sector")

  const sectorCounts: Record<string, number> = {}
  let universeSize = 0
  for (const row of univRows ?? []) {
    const s = row.sector ?? "Unknown"
    sectorCounts[s] = (sectorCounts[s] ?? 0) + 1
    universeSize++
  }

  const raw = data.theme_tracker ?? {}
  const sectors = pivotThemeTracker(raw, sectorCounts)

  return NextResponse.json({
    date: data.date,
    sectors,
    universe_size: universeSize,
  })
}
