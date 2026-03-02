import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const scanKey = request.nextUrl.searchParams.get("scan_key")
  if (!scanKey) {
    return NextResponse.json(
      { error: "Missing scan_key query parameter" },
      { status: 400 },
    )
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from("cached_scans")
    .select("results, scanned_at")
    .eq("scan_key", scanKey)
    .single()

  if (error || !data) {
    return NextResponse.json(
      { results: null, scanned_at: null },
      {
        headers: {
          "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
        },
      },
    )
  }

  return NextResponse.json(
    { results: data.results, scanned_at: data.scanned_at },
    {
      headers: {
        "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
      },
    },
  )
}
