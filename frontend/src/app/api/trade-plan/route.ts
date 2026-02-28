import { NextResponse } from "next/server"
import { readDailyPlan } from "@/lib/generate-daily-plan"

export async function GET() {
  try {
    const data = await readDailyPlan()

    if (!data) {
      return NextResponse.json(null, {
        headers: { "Cache-Control": "no-cache" },
      })
    }

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
      },
    })
  } catch (error) {
    console.error("Trade plan GET error:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    )
  }
}
