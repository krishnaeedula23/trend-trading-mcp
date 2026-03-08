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

  const scans = data.scans as Record<string, { count?: number; tickers?: string[] }> | null
  const scanData = scans?.[scan]
  const tickerSymbols = scanData?.tickers ?? []

  // Enrich with sector data from monitor_universe
  let sectorMap: Record<string, string> = {}
  if (tickerSymbols.length > 0) {
    const { data: univData } = await supabase
      .from("monitor_universe")
      .select("symbol, sector")
      .in("symbol", tickerSymbols)

    if (univData) {
      sectorMap = Object.fromEntries(univData.map((r) => [r.symbol, r.sector ?? "Unknown"]))
    }
  }

  const tickers = tickerSymbols.map((symbol) => ({
    symbol,
    sector: sectorMap[symbol] ?? "Unknown",
    close: 0,
    pct_change: 0,
  }))

  return NextResponse.json({
    scan_key: scan,
    date,
    count: tickers.length,
    tickers,
  })
}
