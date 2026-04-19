/**
 * Vercel cron: Sundays 23:30 UTC (= 4:30pm PT winter / 3:30pm PT summer).
 * Runs BEFORE /swing-weekly-synth (5pm PT on Mac) so weekly synth sees
 * a refreshed backend-generated universe when Deepvue is stale.
 */
import { NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export const runtime = "nodejs"
export const maxDuration = 300   // universe generator can take minutes

export async function GET(request: Request) {
  const cronSecret = process.env.CRON_SECRET
  if (!cronSecret) {
    return NextResponse.json({ error: "CRON_SECRET not configured" }, { status: 500 })
  }
  const authHeader = request.headers.get("authorization")
  if (authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const res = await railwayFetch("/api/swing/pipeline/universe-refresh", undefined, { authToken: cronSecret })
    const body = await res.json()
    return NextResponse.json({ ok: res.ok, upstream: body })
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 })
  }
}
