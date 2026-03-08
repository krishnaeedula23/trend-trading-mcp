import { NextRequest, NextResponse } from "next/server"
import { runAllScans } from "@/lib/run-screener-scans"
import { generateDailyPlan } from "@/lib/generate-daily-plan"

export const maxDuration = 300 // 5 min — scans are slow

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

  // 1. Daily trade plan first — this is what the user sees at 6:00 AM
  let tradePlanOk = false
  let tradePlanError: string | undefined
  try {
    await generateDailyPlan("premarket")
    tradePlanOk = true
  } catch (err) {
    tradePlanError = String(err)
  }

  // 2. Run all screener scans in parallel
  const scanResults = await runAllScans()

  const totalMs = Date.now() - start
  const succeeded = scanResults.filter((r) => r.success).length
  const failed = scanResults.filter((r) => !r.success).length

  return NextResponse.json({
    success: failed === 0 && tradePlanOk,
    scans: { succeeded, failed, details: scanResults },
    trade_plan: { success: tradePlanOk, error: tradePlanError },
    total_duration_ms: totalMs,
  })
}
