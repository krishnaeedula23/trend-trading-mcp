import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

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

  let computeOk = false
  let computeError: string | undefined
  let computeResult: unknown = null

  try {
    const res = await railwayFetch("/api/market-monitor/compute")
    computeResult = await res.json()
    computeOk = res.ok
    if (!res.ok) {
      computeError = `HTTP ${res.status}: ${(computeResult as Record<string, unknown>)?.detail ?? "Unknown error"}`
    }
  } catch (err) {
    computeError = String(err)
  }

  return NextResponse.json({
    success: computeOk,
    compute: { success: computeOk, result: computeResult, error: computeError },
    total_duration_ms: Date.now() - start,
  })
}
