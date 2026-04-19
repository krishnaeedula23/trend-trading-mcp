import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const response = await fetch(`${getBaseUrl()}/api/swing/ideas/${id}/snapshots`, { method: "GET", cache: "no-store" })
  const data = await response.json().catch(() => ({ error: "invalid response" }))
  return NextResponse.json(data, { status: response.status })
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const body = await request.json()
  const response = await fetch(`${getBaseUrl()}/api/swing/ideas/${id}/snapshots`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.SWING_API_TOKEN ?? ""}`,
    },
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({ error: "invalid response" }))
  return NextResponse.json(data, { status: response.status })
}
