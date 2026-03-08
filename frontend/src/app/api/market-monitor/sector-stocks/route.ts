import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const sector = request.nextUrl.searchParams.get("sector")
  if (!sector) {
    return NextResponse.json(
      { error: "Missing required query parameter: sector" },
      { status: 400 },
    )
  }

  const date = request.nextUrl.searchParams.get("date") ?? new Date().toISOString().slice(0, 10)
  const supabase = createServerClient()

  // Get all stocks in this sector from monitor_universe
  const { data: univData } = await supabase
    .from("monitor_universe")
    .select("symbol, name, market_cap, sector")
    .eq("sector", sector)
    .order("market_cap", { ascending: false })

  // Get breadth snapshot for scan cross-reference (price data not available in DB)
  const { data: snapData } = await supabase
    .from("breadth_snapshots")
    .select("scans")
    .eq("date", date)
    .limit(1)

  const scans = (snapData?.[0]?.scans ?? {}) as Record<string, { tickers?: string[] }>

  const stocks = (univData || []).map((r) => {
    const activeScanKeys = Object.entries(scans)
      .filter(([, val]) => val?.tickers?.includes(r.symbol))
      .map(([key]) => key)

    return {
      symbol: r.symbol,
      sector: r.sector ?? sector,
      close: 0,
      pct_change: 0,
      active_scans: activeScanKeys,
    }
  })

  return NextResponse.json({
    date,
    sector,
    stocks,
  })
}
