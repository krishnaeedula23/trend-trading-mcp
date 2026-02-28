import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"
import { RailwayError } from "@/lib/errors"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { ticker, strike_count } = body

    if (!ticker || typeof ticker !== "string") {
      return NextResponse.json(
        { error: "ticker is required", code: "BAD_REQUEST" },
        { status: 400 },
      )
    }

    const response = await railwayFetch("/api/options/atm-straddle", {
      ticker,
      strike_count: strike_count ?? 10,
    })

    const data = await response.json()

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "s-maxage=30, stale-while-revalidate=120",
      },
    })
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json(
        { error: error.detail, code: error.code },
        { status: error.status },
      )
    }
    console.error("ATM straddle error:", error)
    return NextResponse.json(
      { error: "Backend unavailable", code: "NETWORK_ERROR" },
      { status: 502 },
    )
  }
}
