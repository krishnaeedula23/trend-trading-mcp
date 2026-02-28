import { NextResponse } from "next/server"
import { generateDailyPlan } from "@/lib/generate-daily-plan"

export async function POST() {
  try {
    const { data, errors } = await generateDailyPlan("manual")

    if (data.instruments.length === 0) {
      return NextResponse.json(
        { error: "Failed to fetch any instruments", errors },
        { status: 502 },
      )
    }

    return NextResponse.json({ ...data, errors: errors.length > 0 ? errors : undefined })
  } catch (error) {
    console.error("Trade plan generate error:", error)
    return NextResponse.json(
      { error: "Generation failed" },
      { status: 500 },
    )
  }
}
