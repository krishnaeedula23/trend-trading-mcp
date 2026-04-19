import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"
import { runAllScans } from "@/lib/run-screener-scans"
import { generateDailyPlan } from "@/lib/generate-daily-plan"

export const maxDuration = 300

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET
  if (!cronSecret) {
    return NextResponse.json({ error: "CRON_SECRET not configured" }, { status: 500 })
  }

  const authHeader = request.headers.get("authorization")
  if (authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const start = Date.now()
  const utcHour = new Date().getUTCHours()

  if (utcHour === 13) {
    // Pre-market slot: swing detection + existing daily-screeners work
    const results: Record<string, unknown> = { dispatched: "premarket", utc_hour: utcHour }
    try {
      const swingRes = await railwayFetch("/api/swing/pipeline/premarket", undefined, { authToken: cronSecret })
      results.swing = await swingRes.json()
    } catch (err) {
      results.swing = { error: String(err) }
    }
    try {
      await generateDailyPlan("premarket")
      results.trade_plan = { success: true }
    } catch (err) {
      results.trade_plan = { error: String(err) }
    }
    try {
      results.screener_scans = await runAllScans()
    } catch (err) {
      results.screener_scans = { error: String(err) }
    }
    results.total_duration_ms = Date.now() - start
    return NextResponse.json(results)
  }

  if (utcHour === 21) {
    // Post-market slot: swing postmarket + market-monitor
    const results: Record<string, unknown> = { dispatched: "postmarket", utc_hour: utcHour }
    try {
      const swingRes = await railwayFetch("/api/swing/pipeline/postmarket", undefined, { authToken: cronSecret })
      results.swing_postmarket = await swingRes.json()
    } catch (err) {
      results.swing_postmarket = { error: String(err) }
    }
    try {
      const mmRes = await railwayFetch("/api/market-monitor/compute")
      results.market_monitor = await mmRes.json()
    } catch (err) {
      results.market_monitor = { error: String(err) }
    }
    results.total_duration_ms = Date.now() - start
    return NextResponse.json(results)
  }

  return NextResponse.json({ dispatched: "none", utc_hour: utcHour, total_duration_ms: Date.now() - start })
}
