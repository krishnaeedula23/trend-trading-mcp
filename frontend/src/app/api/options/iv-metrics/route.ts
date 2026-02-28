import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"
import { RailwayError } from "@/lib/errors"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { ticker } = body

    if (!ticker || typeof ticker !== "string") {
      return NextResponse.json(
        { error: "ticker is required", code: "BAD_REQUEST" },
        { status: 400 },
      )
    }

    const response = await railwayFetch("/api/options/iv-metrics", { ticker })

    const data = await response.json()

    return NextResponse.json(data, {
      headers: {
        // VIX doesn't change fast — cache 5 min, stale for 10
        "Cache-Control": "s-maxage=300, stale-while-revalidate=600",
      },
    })
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json(
        { error: error.detail, code: error.code },
        { status: error.status },
      )
    }
    console.error("IV metrics error:", error)
    return NextResponse.json(
      { error: "Backend unavailable", code: "NETWORK_ERROR" },
      { status: 502 },
    )
  }
}
