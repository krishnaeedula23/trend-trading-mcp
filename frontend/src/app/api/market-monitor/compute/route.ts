import { NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"
import { RailwayError } from "@/lib/errors"

export const maxDuration = 300

export async function POST() {
  try {
    const res = await railwayFetch("/api/market-monitor/compute")
    const data = await res.json()
    return NextResponse.json(data)
  } catch (err) {
    if (err instanceof RailwayError) {
      return NextResponse.json(
        { error: err.detail, code: err.code },
        { status: err.status },
      )
    }
    return NextResponse.json(
      { error: String(err) },
      { status: 500 },
    )
  }
}
