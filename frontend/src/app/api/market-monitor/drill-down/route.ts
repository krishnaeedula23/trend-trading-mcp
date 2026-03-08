import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const scan = request.nextUrl.searchParams.get("scan")
  const date = request.nextUrl.searchParams.get("date")

  if (!scan || !date) {
    return NextResponse.json(
      { error: "Missing required query parameters: scan, date" },
      { status: 400 },
    )
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from("breadth_snapshots")
    .select("scans")
    .eq("date", date)
    .single()

  if (error || !data) {
    return NextResponse.json(
      { error: `No snapshot found for date ${date}` },
      { status: 404 },
    )
  }

  const scans = data.scans as Record<string, { tickers?: string[] }> | null
  const scanData = scans?.[scan]
  const tickers = scanData?.tickers ?? []

  return NextResponse.json({
    scan,
    date,
    count: tickers.length,
    tickers,
  })
}
