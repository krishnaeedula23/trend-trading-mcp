"use client"
import Link from "next/link"
import type { SwingModelBookEntry } from "@/lib/types"

export function ModelBookCard({
  entry,
  previewChartUrl,
}: {
  entry: SwingModelBookEntry
  previewChartUrl?: string | null
}) {
  return (
    <Link
      href={`/swing-ideas/model-book/${entry.id}`}
      className="block overflow-hidden rounded border hover:shadow"
    >
      {previewChartUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={previewChartUrl}
          alt={entry.title}
          className="h-40 w-full object-cover"
        />
      )}
      <div className="p-3">
        <div className="text-sm font-semibold">{entry.ticker} · {entry.setup_kell}</div>
        <div className="line-clamp-2 text-sm text-muted-foreground">{entry.title}</div>
        <div className="mt-1 flex gap-2 text-xs">
          <span
            className={`rounded px-2 py-0.5 ${
              entry.outcome === "winner" ? "bg-green-100" :
              entry.outcome === "loser" ? "bg-red-100" : "bg-muted"
            }`}
          >
            {entry.outcome}
          </span>
          {entry.r_multiple != null && <span>{entry.r_multiple.toFixed(2)}R</span>}
        </div>
      </div>
    </Link>
  )
}
