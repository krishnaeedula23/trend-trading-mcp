import { NextRequest, NextResponse } from "next/server"
import { generateDailyPlan } from "@/lib/generate-daily-plan"

export async function GET(request: NextRequest) {
  // Verify cron secret
  const authHeader = request.headers.get("authorization")
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { data, errors } = await generateDailyPlan()

    return NextResponse.json({
      success: true,
      session: data.session,
      instruments: data.instruments.map((i) => i.displayName),
      vixPrice: data.vix.price,
      errors: errors.length > 0 ? errors : undefined,
    })
  } catch (error) {
    console.error("Daily plan cron error:", error)
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 },
    )
  }
}
