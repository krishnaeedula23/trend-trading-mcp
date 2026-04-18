import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const backendUrl = `${getBaseUrl()}/api/swing/ideas/${encodeURIComponent(id)}`
    const response = await fetch(backendUrl, { method: "GET", cache: "no-store" })
    if (response.status === 404) {
      return NextResponse.json({ error: "Not found" }, { status: 404 })
    }
    const data = await response.json()
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status: 502 })
  }
}
