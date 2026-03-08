import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const daysParam = request.nextUrl.searchParams.get("days")
  const days = daysParam ? Math.min(Math.max(parseInt(daysParam, 10) || 30, 1), 365) : 30

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from("breadth_snapshots")
    .select("date, universe, scans, computed_at")
    .order("date", { ascending: false })
    .limit(days)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  const snapshots = (data || []).map((row) => {
    const scans = row.scans as Record<string, { count?: number }> | null
    const counts: Record<string, number> = {}
    if (scans) {
      for (const [key, val] of Object.entries(scans)) {
        counts[key] = typeof val === "object" && val !== null ? (val.count ?? 0) : 0
      }
    }
    return {
      date: row.date,
      universe: row.universe ?? "large_cap_1b",
      scans: counts,
      computed_at: row.computed_at,
    }
  })

  // Reverse so oldest is first (chronological order for charting)
  snapshots.reverse()

  return NextResponse.json(
    { snapshots, days, count: snapshots.length },
    {
      headers: {
        "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
      },
    },
  )
}
