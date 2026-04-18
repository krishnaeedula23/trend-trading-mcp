import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const status = url.searchParams.get("status")
  const limit = url.searchParams.get("limit") ?? "50"
  const qs = new URLSearchParams({ limit })
  if (status) qs.set("status", status)

  try {
    const backendUrl = `${getBaseUrl()}/api/swing/ideas?${qs.toString()}`
    const response = await fetch(backendUrl, { method: "GET", cache: "no-store" })
    const data = await response.json()
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status: 502 })
  }
}
