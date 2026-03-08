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

  const supabase = createServerClient()

  // Get all stocks in this sector from monitor_universe
  const { data: univData } = await supabase
    .from("monitor_universe")
    .select("symbol, name, market_cap, sector")
    .eq("sector", sector)
    .order("market_cap", { ascending: false })

  const stocks = (univData || []).map((r) => ({
    symbol: r.symbol,
    sector: r.sector ?? sector,
    close: 0,
    pct_change: 0,
  }))

  return NextResponse.json({
    date: new Date().toISOString().slice(0, 10),
    sector,
    stocks,
  })
}
