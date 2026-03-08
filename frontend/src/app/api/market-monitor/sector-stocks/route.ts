import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

interface ScanTickers {
  tickers?: string[]
  count?: number
}

interface TickerInfo {
  symbol: string
  sector: string
  pct_change?: number
}

export async function GET(request: NextRequest) {
  const sector = request.nextUrl.searchParams.get("sector")
  if (!sector) {
    return NextResponse.json(
      { error: "Missing required query parameter: sector" },
      { status: 400 },
    )
  }

  const dateParam = request.nextUrl.searchParams.get("date")

  const supabase = createServerClient()

  // Get snapshot — if no date specified, get the latest
  let snapshotQuery = supabase
    .from("breadth_snapshots")
    .select("date, scans, theme_tracker")

  if (dateParam) {
    snapshotQuery = snapshotQuery.eq("date", dateParam)
  } else {
    snapshotQuery = snapshotQuery.order("date", { ascending: false }).limit(1)
  }

  const { data: snapData, error: snapError } = await snapshotQuery.single()

  if (snapError || !snapData) {
    return NextResponse.json(
      { error: "No snapshot found" },
      { status: 404 },
    )
  }

  const scans = snapData.scans as Record<string, ScanTickers> | null
  const themeTracker = snapData.theme_tracker as Record<
    string,
    Array<{ sector: string; gainers: number; losers: number; net: number }>
  > | null

  // Collect all tickers with matching sector across all scans, deduplicated
  const seen = new Map<string, { scans: string[]; pct_change: number }>()

  if (scans) {
    for (const [scanKey, scanVal] of Object.entries(scans)) {
      const tickerList = scanVal?.tickers ?? []
      for (const ticker of tickerList) {
        if (!seen.has(ticker)) {
          seen.set(ticker, { scans: [], pct_change: 0 })
        }
        seen.get(ticker)!.scans.push(scanKey)
      }
    }
  }

  // We need to filter to only tickers in the requested sector.
  // Query monitor_universe for sector membership.
  const symbols = Array.from(seen.keys())
  if (symbols.length === 0) {
    return NextResponse.json({
      date: snapData.date,
      sector,
      stocks: [],
    })
  }

  const { data: univData } = await supabase
    .from("monitor_universe")
    .select("symbol, name, market_cap, industry, sector")
    .eq("sector", sector)
    .in("symbol", symbols)

  const sectorSymbols = new Set((univData || []).map((r) => r.symbol))
  const univMap = new Map((univData || []).map((r) => [r.symbol, r]))

  // Build result: only sector stocks, sorted by number of active scans desc
  const stocks = Array.from(seen.entries())
    .filter(([symbol]) => sectorSymbols.has(symbol))
    .map(([symbol, info]) => ({
      symbol,
      name: univMap.get(symbol)?.name ?? "",
      market_cap: univMap.get(symbol)?.market_cap ?? null,
      industry: univMap.get(symbol)?.industry ?? "",
      active_scans: info.scans,
    }))
    .sort((a, b) => b.active_scans.length - a.active_scans.length)

  return NextResponse.json({
    date: snapData.date,
    sector,
    stocks,
  })
}
