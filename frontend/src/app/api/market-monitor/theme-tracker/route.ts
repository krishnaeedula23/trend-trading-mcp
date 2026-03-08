import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

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

  return NextResponse.json({
    date: data.date,
    sectors: data.theme_tracker ?? {},
  })
}
