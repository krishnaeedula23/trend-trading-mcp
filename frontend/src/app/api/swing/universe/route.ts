import { NextRequest, NextResponse } from "next/server"
import { railwayFetch } from "@/lib/railway"

export async function GET() {
  try {
    const response = await railwayFetch("/api/swing/universe")
    const data = await response.json()
    return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const response = await railwayFetch("/api/swing/universe", body)
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    const status = err instanceof Error && "status" in err ? (err as { status: number }).status : 502
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status })
  }
}
