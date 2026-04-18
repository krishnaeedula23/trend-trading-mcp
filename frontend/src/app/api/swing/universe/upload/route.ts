import { NextRequest, NextResponse } from "next/server"

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL
  if (!url) throw new Error("RAILWAY_API_URL not set")
  return url.replace(/\/+$/, "")
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const url = `${getBaseUrl()}/api/swing/universe/upload`
    const response = await fetch(url, { method: "POST", body: formData })
    const data = await response.json().catch(() => ({ error: "invalid response" }))
    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Failed" }, { status: 502 })
  }
}
